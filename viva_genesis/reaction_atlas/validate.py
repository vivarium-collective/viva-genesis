"""Write-time validator for the Prebiotic Reaction Atlas.

Enforces Study 28's decision test — "No unexplained precursor or unbalanced
reaction enters an accepted model" — at the point a record is written. The
balance checks COMPUTE mass + charge from the species formulas and the reaction
stoichiometry; they never trust a record's self-reported ``mass_balanced`` /
``charge_balanced`` flags (a record that claims a balance it does not have is a
violation). This is the dataset-level audit the study-run gate pipeline doesn't
provide (see ``workspace/notes/audit-build-capability-gaps.md`` gaps 1/3/4).
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

_TIERS = {"measured", "inferred", "hypothetical"}
_ROLES = {"reactant", "product", "catalyst"}
_ACQUISITION = {"extracted", "rule-generated", "agent-proposed"}
_REQUIRED_TOP = ["id", "tier", "species", "reaction", "conditions", "kinetics",
                 "evidence", "provenance"]

# One element token: an element symbol (upper + optional lower) + optional count.
_ELEMENT_RE = re.compile(r"([A-Z][a-z]?)(\d*)")
# A parenthesised group with a multiplier, e.g. (OH)2 — single level is enough
# for the C1-C3 / headgroup species the atlas carries.
_GROUP_RE = re.compile(r"\(([A-Za-z0-9]+)\)(\d+)")


def parse_formula(formula: str) -> Dict[str, int]:
    """Parse a molecular formula into element -> count.

    Supports single-level parenthesised groups, e.g. ``Ca(OH)2``. Raises
    ``ValueError`` on a formula that does not fully parse, so the validator can
    flag an unparseable species rather than silently miscount it.
    """
    if not formula or not isinstance(formula, str):
        raise ValueError(f"empty/invalid formula: {formula!r}")

    counts: Dict[str, int] = {}

    def _add(sub: str, mult: int) -> None:
        for sym, num in _ELEMENT_RE.findall(sub):
            if not sym:
                continue
            counts[sym] = counts.get(sym, 0) + (int(num) if num else 1) * mult

    # Expand parenthesised groups first, tracking consumed spans.
    remainder = formula
    for m in _GROUP_RE.finditer(formula):
        _add(m.group(1), int(m.group(2)))
        remainder = remainder.replace(m.group(0), "", 1)

    _add(remainder, 1)

    # Validate: the stripped remainder must be pure element tokens.
    leftover = _ELEMENT_RE.sub("", remainder)
    if leftover.strip():
        raise ValueError(f"unparseable formula {formula!r} (leftover {leftover!r})")
    if not counts:
        raise ValueError(f"no elements parsed from {formula!r}")
    return counts


def reaction_balance(
    reactants: Dict[str, float],
    products: Dict[str, float],
    formulas: Dict[str, Tuple[str, int]],
) -> Dict[str, object]:
    """Compute mass + charge balance from stoichiometry.

    ``reactants``/``products`` map a species ref -> coefficient; ``formulas``
    maps the same ref -> (formula, charge). Returns mass_balanced,
    charge_balanced, the per-element diff (products - reactants) and the charge
    diff. A ref missing from ``formulas`` makes the reaction un-evaluable; it is
    reported via ``unresolved`` and leaves balance False.
    """
    unresolved = [r for r in list(reactants) + list(products) if r not in formulas]
    element_diff: Dict[str, int] = {}
    charge_diff = 0.0

    def _accumulate(side: Dict[str, float], sign: int) -> None:
        nonlocal charge_diff
        for ref, coeff in side.items():
            if ref not in formulas:
                continue
            formula, charge = formulas[ref]
            for sym, n in parse_formula(formula).items():
                element_diff[sym] = element_diff.get(sym, 0) + sign * n * coeff
            charge_diff += sign * charge * coeff

    # products positive, reactants negative -> diff is zero when balanced.
    _accumulate(products, +1)
    _accumulate(reactants, -1)

    element_diff = {k: v for k, v in element_diff.items() if v != 0}
    mass_balanced = (not unresolved) and not element_diff
    charge_balanced = (not unresolved) and (charge_diff == 0)
    return {
        "mass_balanced": mass_balanced,
        "charge_balanced": charge_balanced,
        "element_diff": element_diff,
        "charge_diff": charge_diff,
        "unresolved": unresolved,
    }


def validate_record(record: dict) -> List[str]:
    """Return a list of human-readable violations. Empty list == structurally valid.

    Note: an empty list means the record is well-formed and its claimed balance
    matches reality; use :func:`is_acceptable` to also require that the reaction
    is actually balanced before admitting the record to ``atlas.vN.jsonl``.
    """
    v: List[str] = []

    for key in _REQUIRED_TOP:
        if key not in record:
            v.append(f"missing required field: {key}")
    if v:
        return v  # structural shape too incomplete to check further

    if record.get("tier") not in _TIERS:
        v.append(f"tier {record.get('tier')!r} not in {sorted(_TIERS)}")

    species = record.get("species") or []
    formulas: Dict[str, Tuple[str, int]] = {}
    for i, sp in enumerate(species):
        for k in ("chebi_id", "formula", "charge", "role"):
            if k not in sp:
                v.append(f"species[{i}] missing {k}")
        if sp.get("role") and sp["role"] not in _ROLES:
            v.append(f"species[{i}] role {sp['role']!r} not in {sorted(_ROLES)}")
        if not isinstance(sp.get("charge"), int):
            v.append(f"species[{i}] charge must be an int, got {sp.get('charge')!r}")
        if "chebi_id" in sp and "formula" in sp and isinstance(sp.get("charge"), int):
            try:
                parse_formula(sp["formula"])
                formulas[sp["chebi_id"]] = (sp["formula"], sp["charge"])
            except ValueError as e:
                v.append(f"species[{i}] {e}")

    rxn = record.get("reaction") or {}
    reactants = rxn.get("reactants") or {}
    products = rxn.get("products") or {}
    if not reactants:
        v.append("reaction.reactants is empty")
    if not products:
        v.append("reaction.products is empty")
    for ref in list(reactants) + list(products):
        if ref not in formulas:
            v.append(f"reaction references unknown species {ref!r} (not in species[])")

    if reactants and products:
        bal = reaction_balance(reactants, products, formulas)
        # Verify the record's CLAIMED balance against the computed truth.
        if rxn.get("mass_balanced") is True and not bal["mass_balanced"]:
            v.append(f"claims mass_balanced=True but element imbalance {bal['element_diff']}")
        if rxn.get("charge_balanced") is True and not bal["charge_balanced"]:
            v.append(f"claims charge_balanced=True but charge imbalance {bal['charge_diff']}")

    ev = record.get("evidence") or {}
    if not ev.get("source_doi"):
        v.append("evidence.source_doi is required (a DOI alone is not sufficient, but it is necessary)")
    if record.get("tier") == "measured" and not ev.get("verified_against_source"):
        v.append("tier 'measured' requires evidence.verified_against_source=True")

    prov = record.get("provenance") or {}
    if prov.get("acquisition") not in _ACQUISITION:
        v.append(f"provenance.acquisition {prov.get('acquisition')!r} not in {sorted(_ACQUISITION)}")

    return v


def is_acceptable(record: dict) -> bool:
    """True iff the record is well-formed AND the reaction is actually balanced.

    This is the gate for admitting a record to the accepted network
    (``atlas.vN.jsonl``). A hypothetical/unbalanced candidate may be a valid
    record for ``proposed/`` but is not acceptable into the accepted model.
    """
    if validate_record(record):
        return False
    rxn = record["reaction"]
    formulas = {sp["chebi_id"]: (sp["formula"], sp["charge"]) for sp in record["species"]}
    bal = reaction_balance(rxn.get("reactants", {}), rxn.get("products", {}), formulas)
    return bool(bal["mass_balanced"] and bal["charge_balanced"])
