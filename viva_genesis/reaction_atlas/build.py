"""Builder for the Prebiotic Reaction Atlas (Study 28 asset; reused by 29/31).

Turns *raw* candidate reactions into records the write-time validator
(:mod:`viva_genesis.reaction_atlas.validate`) accepts, then routes validated,
balanced records to the accepted atlas and everything else to ``proposed/``.
The pipeline is ``extract -> feasibility -> validate``:

- :func:`extract_record` normalizes a raw reaction into the schema shape —
  canonical species (formula + formal charge via RDKit when only a SMILES is
  given) and the mass/charge balance **computed** from the stoichiometry
  (reusing :func:`validate.reaction_balance`; this module never duplicates the
  balance arithmetic and never trusts a raw record's self-reported flags).
- :func:`feasibility` attaches an eQuilibrator ΔG'° feasibility flag.
- :func:`build_atlas` runs the pipeline over a batch and splits the output into
  ``accepted`` (passes :func:`validate.is_acceptable`) and ``proposed``.

Both real-tool bridges are **lazy** — imported inside the functions that need
them — so ``import viva_genesis.reaction_atlas.build`` works in a venv without
RDKit or ``viva_equilibrator`` installed (register/lint/scaffold paths stay
import-safe; the bridges raise a clear install hint only when actually invoked).
Both are also injectable, so the pipeline is exercised offline in tests without
either dependency or any network.

General + composable by design: the raw shape, tier, provenance and
kinetic-domain are all parameterized, so the same builder serves Study 28 (atlas
construction), Study 29 (candidate-network generation input) and Study 31
(amphiphile-precursor enumeration) without study-specific branches.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from .validate import reaction_balance, validate_record, is_acceptable

__all__ = [
    "AtlasBuildResult",
    "canonical_formula_charge",
    "extract_record",
    "feasibility",
    "build_atlas",
]

# eQuilibrator estimator contract: {name: formula} + (pH, I, T) -> {name: (dg_kj_mol, sigma_kj_mol)}.
Estimator = Callable[..., Mapping[str, Tuple[float, float]]]


# --------------------------------------------------------------------------- #
# RDKit bridge (lazy) — species canonicalization
# --------------------------------------------------------------------------- #
def _require_rdkit():
    try:
        from rdkit import Chem  # noqa: PLC0415 — lazy on purpose
    except Exception as e:  # pragma: no cover - exercised only without rdkit
        raise RuntimeError(
            "RDKit is required to canonicalize a species from SMILES. Install it "
            "into the workspace venv (a /viva-catalog step), or supply each "
            "species' `formula` + `charge` directly so no SMILES parsing is needed."
        ) from e
    return Chem


def _hill_formula(counts: Mapping[str, int]) -> str:
    """Format an element->count map as a Hill-system formula (C, H, then A–Z).

    With no carbon, every element (hydrogen included) is ordered alphabetically.
    Element ORDER is cosmetic for balance — :func:`validate.parse_formula` only
    counts — but Hill order keeps the stored formula canonical and readable.
    """
    parts: List[str] = []
    if counts.get("C"):
        for sym in ("C", "H"):
            n = counts.get(sym, 0)
            if n:
                parts.append(sym + (str(n) if n > 1 else ""))
        rest = sorted(k for k in counts if k not in ("C", "H") and counts[k])
    else:
        rest = sorted(k for k in counts if counts[k])
    for sym in rest:
        n = counts[sym]
        parts.append(sym + (str(n) if n > 1 else ""))
    return "".join(parts)


def canonical_formula_charge(smiles: str) -> Tuple[str, int]:
    """Return ``(hill_formula, formal_charge)`` for a SMILES string via RDKit.

    Explicit + implicit hydrogens are both counted. Raises ``ValueError`` on a
    SMILES RDKit cannot parse, so a bad structure is surfaced rather than
    silently miscounted.
    """
    Chem = _require_rdkit()
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"RDKit could not parse SMILES {smiles!r}")
    mol_h = Chem.AddHs(mol)
    counts: Dict[str, int] = {}
    for atom in mol_h.GetAtoms():
        counts[atom.GetSymbol()] = counts.get(atom.GetSymbol(), 0) + 1
    return _hill_formula(counts), int(Chem.GetFormalCharge(mol_h))


# --------------------------------------------------------------------------- #
# extract — raw reaction -> normalized schema record
# --------------------------------------------------------------------------- #
def _species_ref(sp: Mapping) -> Optional[str]:
    return sp.get("chebi_id") or sp.get("id")


def _equation_string(
    reactants: Mapping[str, float], products: Mapping[str, float]
) -> str:
    def _side(side: Mapping[str, float]) -> str:
        return " + ".join(
            (f"{coeff:g} {ref}" if coeff != 1 else f"{ref}")
            for ref, coeff in side.items()
        )
    return f"{_side(reactants)} = {_side(products)}"


def extract_record(
    raw: Mapping,
    *,
    default_tier: str = "hypothetical",
    acquisition: str = "extracted",
    added_by: str = "viva_genesis.reaction_atlas.build",
    added_at: Optional[str] = None,
    proton_convention: Optional[str] = None,
) -> dict:
    """Normalize a raw reaction into a schema-shaped atlas record.

    ``raw`` is a loose mapping with:

    - ``species``: list of ``{chebi_id|id, role, [formula], [charge], [smiles], [eq_id]}``.
      When ``formula``/``charge`` are absent and ``smiles`` is present, they are
      derived via RDKit (:func:`canonical_formula_charge`).
    - ``reaction``: ``{reactants: {ref: coeff}, products: {ref: coeff},
      [equation], [proton_convention]}`` — refs key into ``species`` by
      ``chebi_id``/``id``.
    - optional ``tier``, ``conditions``, ``kinetics``, ``evidence``,
      ``provenance`` passthroughs (used verbatim; missing required evidence /
      provenance is left missing so the validator can reject it — never fabricated).

    ``reaction.mass_balanced`` / ``charge_balanced`` are always (re)computed from
    the species formulas, overwriting any raw-reported flags.
    """
    # --- species: canonicalize formula + charge ---
    species_out: List[dict] = []
    for sp in raw.get("species", []) or []:
        formula = sp.get("formula")
        charge = sp.get("charge")
        if (formula is None or charge is None) and sp.get("smiles"):
            f, c = canonical_formula_charge(sp["smiles"])
            if formula is None:
                formula = f
            if charge is None:
                charge = c
        entry = {
            "chebi_id": _species_ref(sp),
            "formula": formula,
            "charge": charge,
            "role": sp.get("role"),
        }
        if sp.get("eq_id"):
            entry["eq_id"] = sp["eq_id"]
        species_out.append(entry)

    # --- reaction: compute balance from the canonical formulas ---
    rxn_in = raw.get("reaction") or {}
    reactants = dict(rxn_in.get("reactants") or {})
    products = dict(rxn_in.get("products") or {})
    formulas: Dict[str, Tuple[str, int]] = {
        s["chebi_id"]: (s["formula"], s["charge"])
        for s in species_out
        if s.get("chebi_id") and s.get("formula") is not None and isinstance(s.get("charge"), int)
    }
    if reactants and products:
        bal = reaction_balance(reactants, products, formulas)
        mass_ok = bool(bal["mass_balanced"])
        charge_ok = bool(bal["charge_balanced"])
    else:
        mass_ok = charge_ok = False

    reaction = {
        "reactants": reactants,
        "products": products,
        "equation": rxn_in.get("equation") or _equation_string(reactants, products),
        "mass_balanced": mass_ok,
        "charge_balanced": charge_ok,
        "proton_convention": rxn_in.get("proton_convention") or proton_convention or "unspecified",
    }

    # --- provenance (merged; raw wins, tool fields fill gaps) ---
    prov = dict(raw.get("provenance") or {})
    prov.setdefault("acquisition", acquisition)
    prov.setdefault("added_by", added_by)
    prov.setdefault("added_at", added_at or date.today().isoformat())

    kinetics = dict(raw.get("kinetics") or {})
    kinetics.setdefault("rate_form", "n/a")
    kinetics.setdefault("parameters", {})
    kinetics.setdefault("is_range", False)
    kinetics.setdefault("uncertainty", {})

    record = {
        "id": raw.get("id"),
        "tier": raw.get("tier") or default_tier,
        "species": species_out,
        "reaction": reaction,
        "conditions": dict(raw.get("conditions") or {}),
        "kinetics": kinetics,
        "evidence": dict(raw.get("evidence") or {}),
        "provenance": prov,
    }
    if raw.get("thermodynamics"):
        record["thermodynamics"] = dict(raw["thermodynamics"])
    if raw.get("competing_reactions"):
        record["competing_reactions"] = list(raw["competing_reactions"])
    return record


# --------------------------------------------------------------------------- #
# feasibility — eQuilibrator ΔG'° screen (lazy bridge / injectable)
# --------------------------------------------------------------------------- #
def _default_estimator() -> Estimator:
    try:
        from viva_equilibrator.processes import standard_dg_primes  # noqa: PLC0415
    except Exception as e:  # pragma: no cover - exercised only without the dep
        raise RuntimeError(
            "viva_equilibrator is required for the ΔG feasibility bridge. Install "
            "it into the workspace venv (a /viva-catalog step) or pass "
            "`estimator=` (a callable {name: formula}, pH, I, T -> {name: (dg, sigma)})."
        ) from e
    return standard_dg_primes


def _eq_reaction_formula(record: Mapping) -> str:
    """Build an eQuilibrator reaction formula ``'a X + b Y = c Z'`` from a record.

    Uses each species' ``eq_id`` (eQuilibrator-parseable id, e.g. ``kegg:C00011``)
    when present, else its ``chebi_id``. Prefers an explicit
    ``reaction.eq_formula`` when the raw record already carries one.
    """
    rxn = record.get("reaction") or {}
    if rxn.get("eq_formula"):
        return rxn["eq_formula"]
    eq_id = {
        s["chebi_id"]: (s.get("eq_id") or s["chebi_id"])
        for s in record.get("species", [])
        if s.get("chebi_id")
    }

    def _side(side: Mapping[str, float]) -> str:
        return " + ".join(
            (f"{coeff:g} {eq_id.get(ref, ref)}" if coeff != 1 else f"{eq_id.get(ref, ref)}")
            for ref, coeff in side.items()
        )

    return f"{_side(rxn.get('reactants') or {})} = {_side(rxn.get('products') or {})}"


def feasibility(
    record: Mapping,
    *,
    estimator: Optional[Estimator] = None,
    p_h: Optional[float] = None,
    ionic_strength_M: float = 0.25,
    temperature_K: float = 298.15,
    threshold_kj_mol: float = 0.0,
    model: str = "eQuilibrator component-contribution",
) -> dict:
    """Attach an eQuilibrator ΔG'° feasibility flag to a record (returns a copy).

    Sets ``thermodynamics = {model, delta_g_kj_mol, sigma_kj_mol, feasible}``,
    where ``feasible`` is ``ΔG'° <= threshold_kj_mol`` (default 0 — a
    thermodynamically allowed step under the given pH/I/T). ``p_h`` defaults to
    the record's ``conditions.pH`` and then to 7.0. With no ``estimator`` the
    real :func:`viva_equilibrator.processes.standard_dg_primes` bridge is used
    (raising a clear install hint if the dep is missing); pass a stub for
    offline use.
    """
    est = estimator or _default_estimator()
    cond = record.get("conditions") or {}
    ph = p_h if p_h is not None else cond.get("pH", 7.0)
    name = record.get("id") or "reaction"
    formula = _eq_reaction_formula(record)

    out = est(
        {name: formula},
        p_h=ph,
        ionic_strength_M=cond.get("ionic_strength_M", ionic_strength_M),
        temperature_K=temperature_K,
    )
    dg, sigma = out[name]

    thermo = dict(record.get("thermodynamics") or {})
    thermo.update(
        model=model,
        delta_g_kj_mol=float(dg),
        sigma_kj_mol=float(sigma),
        feasible=bool(float(dg) <= threshold_kj_mol),
    )
    return {**record, "thermodynamics": thermo}


# --------------------------------------------------------------------------- #
# build_atlas — batch pipeline with accepted / proposed routing
# --------------------------------------------------------------------------- #
@dataclass
class AtlasBuildResult:
    """Outcome of :func:`build_atlas`.

    ``accepted`` holds records that pass :func:`validate.is_acceptable` (balanced
    + well-formed, fit for ``atlas.vN.jsonl``); ``proposed`` holds the rest (the
    ``proposed/`` staging area), each paired with its validator ``violations``.
    """

    accepted: List[dict] = field(default_factory=list)
    proposed: List[dict] = field(default_factory=list)

    def __len__(self) -> int:  # number of accepted records
        return len(self.accepted)

    def __iter__(self):
        return iter(self.accepted)


def build_atlas(
    raw_records: Sequence[Mapping],
    *,
    run_feasibility: bool = False,
    estimator: Optional[Estimator] = None,
    feasibility_kw: Optional[dict] = None,
    **extract_kw,
) -> AtlasBuildResult:
    """Run ``extract -> (feasibility) -> validate`` over a batch of raw reactions.

    Records that pass :func:`validate.is_acceptable` go to ``accepted``; the rest
    go to ``proposed`` (each annotated with ``_violations`` from the validator so
    the caller can see why). Feasibility is advisory metadata (it does not gate
    acceptance — balance + provenance do), so it is **opt-in**: enable it with
    ``run_feasibility=True`` (real bridge) or by passing ``estimator=`` (offline
    stub). A feasibility failure is swallowed so a ΔG hiccup never drops an
    otherwise-valid record. ``extract_kw`` is forwarded to :func:`extract_record`
    (e.g. ``default_tier``, ``acquisition``), keeping the builder reusable across
    studies without hardcoding.
    """
    result = AtlasBuildResult()
    do_feas = run_feasibility or estimator is not None
    fkw = dict(feasibility_kw or {})
    if estimator is not None:
        fkw.setdefault("estimator", estimator)

    for raw in raw_records:
        rec = extract_record(raw, **extract_kw)
        if do_feas:
            try:
                rec = feasibility(rec, **fkw)
            except Exception:  # advisory only — never blocks a valid record
                pass
        if is_acceptable(rec):
            result.accepted.append(rec)
        else:
            # validate_record flags STRUCTURAL faults (missing provenance, a
            # claimed-but-false balance, …). A record that is well-formed and
            # *honestly* reports itself unbalanced has no structural violation —
            # it is rejected by is_acceptable's balance gate. Synthesize a reason
            # in that case so every proposed record says why it was held back.
            violations = validate_record(rec)
            if not violations:
                rxn = rec["reaction"]
                violations = [
                    f"reaction not balanced (mass_balanced={rxn['mass_balanced']}, "
                    f"charge_balanced={rxn['charge_balanced']})"
                ]
            rec = {**rec, "_violations": violations}
            result.proposed.append(rec)
    return result
