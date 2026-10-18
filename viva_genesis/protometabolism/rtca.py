"""Curated **mechanistic** reductive-TCA (rTCA) network — the branched-skeleton
v2 that the linear C≤6 formose universe cannot hold.

og-29 refuted *formose-type* autocatalysis (linear C≤6): the canonical doubling
step r409 (``2 glycolaldehyde ⇌ threose``) is present but ΔG°-condensation-
favored, so no net splitting flux. The reductive TCA cycle is a *different*
candidate, and it is autocatalytic by a *topological* mechanism — citrate is
cleaved into oxaloacetate **and** acetyl (here an acetate surrogate), and the
acetate is re-carboxylated back to a *second* oxaloacetate, so one turn makes
1 OAA → 2 OAA while **every elementary step is 1:1**. There is no coefficient-2
reaction anywhere, so the coefficient-gated detector
(:func:`viva_genesis.protometabolism.motifs.autocatalytic_cycles`) returns
gain 0 *by construction* — a guaranteed false negative. rTCA is exactly why the
coefficient-independent :mod:`functional_autocatalysis` discriminator exists.

**What this network IS and what it tests (the guardrail — read before quoting a
result).** This is a *curated* cycle: the autocatalytic topology is hand-coded,
present by construction. It therefore CANNOT test whether autocatalysis
*emerges* (that was the formose/rule-generated question, and it was refuted). It
tests two different things: **(a) thermodynamic/kinetic feasibility** — does the
canonical rTCA cycle actually turn over and self-amplify under vent feeds
(ignition sweep)? and **(b) topology-specificity** — does the rTCA wiring produce
self-amplification beyond a degree-preserving matched null on the same
compounds/feeds? A positive result means "the canonical rTCA cycle IS viable and
self-amplifying under vent conditions," NEVER "autocatalysis emerges."

**Curation choices (declared, not hidden):**
- acetyl-CoA is represented by its carbon surrogate **acetate** (no CoA/ATP
  cofactors) — the approved acetate-surrogate simplification; the thioester
  (acetyl-CoA / ATP-coupled) variant is the og-12 / study-35 follow-up.
- **fumarate** (a C=C unsaturated C4) is outside the saturated-skeleton
  representation, so malate → succinate is a single reductive step (the
  hydration/reduction is lumped). Declared limitation.
- ATP/CoA energetics of succinyl-CoA and the citrate lyase are omitted; the
  lyase and SCS are treated as rate-processes, not cofactor-coupled. Declared.

Every species' formation potential G'(X) comes from the SAME eQuilibrator
component-contribution engine the rule-generated universe uses (KEGG ids below,
formula-verified), so the rTCA network's thermodynamics are on the same footing
as the rest of the investigation. The three branched C6 intermediates are
registered as curated specials (:data:`BRANCHED`).
"""
from __future__ import annotations

import numpy as np
from process_bigraph import allocate_core  # noqa: F401 — re-exported convenience

from . import universe as U
from .universe import Reaction, Universe, ThermoConditions


# --------------------------------------------------------------------------- #
# Species: linear intermediates reuse the skeleton ids; three branched C6
# intermediates are curated specials (formula + carbon count + KEGG).
# --------------------------------------------------------------------------- #
# linear rTCA intermediates (already expressible as saturated skeletons)
OAA = U.species_id(("A", "C", "K", "A"))        # oxaloacetate  C4  (X_ACKA)
MALATE = U.species_id(("A", "C", "O", "A"))      # malate        C4  (X_ACOA)
SUCCINATE = U.species_id(("A", "C", "C", "A"))   # succinate     C4  (X_ACCA)
AKG = U.species_id(("A", "C", "C", "K", "A"))    # 2-oxoglutarate C5 (X_ACCKA)
PYRUVATE = U.species_id(("A", "K", "M"))         # pyruvate      C3  (X_AKM)
ACETATE = U.species_id(("A", "M"))               # acetate       C2  (X_AM) — acetyl-CoA surrogate

# branched C6 intermediates — curated specials (not linear skeletons)
CITRATE = "X_citrate"
ISOCITRATE = "X_isocitrate"
ACONITATE = "X_aconitate"

# curated specials: id -> (KEGG, name, neutral formula {C,H,O}, carbon count)
BRANCHED: dict[str, tuple[str, str, dict[str, int], int]] = {
    CITRATE: ("kegg:C00158", "citrate", {"C": 6, "H": 8, "O": 7}, 6),
    ISOCITRATE: ("kegg:C00311", "isocitrate", {"C": 6, "H": 8, "O": 7}, 6),
    ACONITATE: ("kegg:C00417", "cis-aconitate", {"C": 6, "H": 6, "O": 6}, 6),
}

# linear intermediates: id -> (KEGG, name) for the shared eQuilibrator path
LINEAR_KEGG: dict[str, tuple[str, str]] = {
    OAA: ("kegg:C00036", "oxaloacetate"), MALATE: ("kegg:C00149", "malate"),
    SUCCINATE: ("kegg:C00042", "succinate"), AKG: ("kegg:C00026", "2-oxoglutarate"),
    PYRUVATE: ("kegg:C00022", "pyruvate"), ACETATE: ("kegg:C00033", "acetate"),
}

ORGANICS = [OAA, MALATE, SUCCINATE, AKG, ISOCITRATE, ACONITATE, CITRATE, ACETATE, PYRUVATE]

# the carrier whose self-amplification the functional discriminator seeds / tracks
CARRIER = OAA


def _register_specials() -> None:
    """Teach the free functions in :mod:`universe` about the branched specials:
    their carbon count (for TOC / matched-null carbon classes) and element
    formula. Idempotent; mirrors the existing ``SPECIAL_FORMULAS`` pattern."""
    if not hasattr(U, "SPECIAL_CARBONS"):
        U.SPECIAL_CARBONS = {}  # type: ignore[attr-defined]
    for sid, (_kegg, _name, form, nc) in BRANCHED.items():
        U.SPECIAL_CARBONS[sid] = nc          # consulted by patched U.n_carbons
        U.SPECIAL_FORMULAS[sid] = dict(form)  # element ledger


_register_specials()


def _formula(sid: str) -> dict[str, int]:
    if sid in BRANCHED:
        return dict(BRANCHED[sid][2])
    skel = U.skeleton_of(sid)
    return U.formula(skel)


def _formation_coeffs(form: dict[str, int]) -> tuple[int, int, int]:
    """(c, m, k) in ``c CO2 + m H2 -> X + k H2O`` for a C/H/O formula."""
    c, h, o = form.get("C", 0), form.get("H", 0), form.get("O", 0)
    k = 2 * c - o
    if (h + 2 * k) % 2:
        raise ValueError(f"odd hydrogen in formation balance for {form}")
    return c, (h + 2 * k) // 2, k


# --------------------------------------------------------------------------- #
# Thermodynamics (shared eQuilibrator engine)
# --------------------------------------------------------------------------- #
def rtca_potentials(cond: ThermoConditions | None = None) -> dict[str, float]:
    """Formation potential G'(X) (kJ/mol) for every rTCA intermediate from the
    eQuilibrator component-contribution engine, at ``cond`` (default: the
    committed package condition). CO2/H2/H2O are 0 by the formation basis."""
    from equilibrator_api import Q_
    from viva_equilibrator import get_component_contribution
    cond = cond or ThermoConditions(**U.load_thermo_table()["conditions"])
    cc = get_component_contribution()
    cc.p_h = Q_(float(cond.p_h))
    cc.ionic_strength = Q_(f"{float(cond.ionic_strength_M)} M")
    cc.temperature = Q_(f"{float(cond.temperature_K)} K")
    kegg = {**{sid: k for sid, (k, _n) in LINEAR_KEGG.items()},
            **{sid: k for sid, (k, _n, _f, _c) in BRANCHED.items()}}
    pot = {U.CO2: 0.0, U.H2: 0.0, U.H2O: 0.0}
    for sid in ORGANICS:
        c, m, k = _formation_coeffs(_formula(sid))
        lhs = " + ".join(x for x in ((f"{c} kegg:C00011" if c else ""), (f"{m} kegg:C00282" if m else "")) if x)
        rhs = kegg[sid] + (f" + {k} kegg:C00001" if k > 0 else "")
        if k < 0:
            lhs += f" + {-k} kegg:C00001"
        rxn = cc.parse_reaction_formula(f"{lhs} = {rhs}")
        pot[sid] = float(cc.standard_dg_prime(rxn).value.to("kJ/mol").magnitude)
    return pot


# --------------------------------------------------------------------------- #
# The reductive-TCA reaction set (reductive / CO2-fixing direction = forward).
# (rate_param, catalyst) reuse the universe's rule classes so to_antimony's
# catalyst-saturation + reversible kinetics apply identically. Every reaction is
# element-balanced; the net turn is 1 OAA + 4 CO2 + 5 H2 -> 2 OAA + 3 H2O.
# --------------------------------------------------------------------------- #
def _r(rid, reactants, products, rule):
    cat, kp = U.RULES[rule]
    return Reaction(id=rid, reactants=dict(reactants), products=dict(products), rule=rule,
                    catalyst=cat, rate_param=kp, reversible=True, kind="internal")


def rtca_reactions() -> list[Reaction]:
    CO2, H2, H2O = U.CO2, U.H2, U.H2O
    return [
        _r("rtca1_mdh",  {OAA: 1, H2: 1}, {MALATE: 1}, "reduce_carbonyl"),                  # OAA + H2 -> malate
        _r("rtca2_fum",  {MALATE: 1, H2: 1}, {SUCCINATE: 1, H2O: 1}, "deoxygenate"),        # malate + H2 -> succinate + H2O (fumarate lumped)
        _r("rtca3_scs",  {SUCCINATE: 1, CO2: 1, H2: 1}, {AKG: 1, H2O: 1}, "carboxylate_reductive"),  # succinate + CO2 + H2 -> aKG + H2O
        _r("rtca4_idh",  {AKG: 1, CO2: 1, H2: 1}, {ISOCITRATE: 1}, "carboxylate_reductive"),         # aKG + CO2 + H2 -> isocitrate
        _r("rtca5_acn1", {ISOCITRATE: 1}, {ACONITATE: 1, H2O: 1}, "isomerize"),             # isocitrate -> cis-aconitate + H2O
        _r("rtca6_acn2", {ACONITATE: 1, H2O: 1}, {CITRATE: 1}, "isomerize"),                # cis-aconitate + H2O -> citrate
        _r("rtca7_acl",  {CITRATE: 1}, {OAA: 1, ACETATE: 1}, "aldol"),                      # citrate -> OAA + acetate  (ATP-citrate lyase; C-C cleavage, the branch)
        _r("rtca8_pfor", {ACETATE: 1, CO2: 1, H2: 1}, {PYRUVATE: 1, H2O: 1}, "carboxylate_reductive"),  # acetate + CO2 + H2 -> pyruvate + H2O
        _r("rtca9_pc",   {PYRUVATE: 1, CO2: 1}, {OAA: 1}, "carboxylate_alpha"),             # pyruvate + CO2 -> OAA  (closes to the 2nd OAA)
    ]


def build_rtca_universe(potentials: dict[str, float] | None = None,
                        cond: ThermoConditions | None = None,
                        carboxylation_drive_kj: float = 0.0) -> Universe:
    """The curated mechanistic rTCA network as a :class:`universe.Universe`, so it
    reuses ``to_antimony``, the matched-null rewiring, the element/energy ledger
    and the functional discriminator unchanged. ``potentials`` may be supplied
    (e.g. a committed table, or a stub for offline structure tests); otherwise
    they are computed from eQuilibrator via :func:`rtca_potentials`.

    ``carboxylation_drive_kj`` is a **labelled counterfactual** (default 0 = the
    real vent-H2 thermodynamics): it subtracts this many kJ/mol from the ΔG° of
    each reductive carboxylation (the CO2-fixing steps), modelling a stronger
    reductant than H2 lowering the fixation barrier. It is NOT a vent-feasibility
    claim — it exists only to separate whether the cycle fails to self-amplify
    because its TOPOLOGY is not autocatalytic (it would still fail at high drive)
    or because the reductive-carboxylation THERMODYNAMICS block it under vent H2
    (it self-amplifies once the barrier is lowered)."""
    _register_specials()
    cond = cond or ThermoConditions(**U.load_thermo_table()["conditions"])
    pot = dict(potentials) if potentials is not None else rtca_potentials(cond)
    reactions = rtca_reactions()
    for r in reactions:
        r.dg0 = U.reaction_dg0(r, pot)
        if carboxylation_drive_kj and r.rule == "carboxylate_reductive":
            r.dg0 -= float(carboxylation_drive_kj)   # counterfactual: stronger reductant lowers the fixation barrier
    species = [U.CO2, U.H2] + list(ORGANICS) + [U.H2O]
    formulas = {U.CO2: U.SPECIAL_FORMULAS[U.CO2], U.H2: U.SPECIAL_FORMULAS[U.H2],
                U.H2O: U.SPECIAL_FORMULAS[U.H2O], **{s: _formula(s) for s in ORGANICS}}
    return Universe(species=species, reactions=reactions, potentials=pot, formulas=formulas,
                    conditions=cond, max_carbons=6, label="curated_rtca_mechanistic",
                    meta={"carrier": CARRIER, "acetyl_surrogate": ACETATE,
                          "curation": ["acetate for acetyl-CoA", "fumarate lumped into malate->succinate",
                                       "no ATP/CoA cofactor energetics"],
                          "doubling_reactions_coeff": [], "autocatalysis": "topological (citrate lyase branch)"})


# --------------------------------------------------------------------------- #
# Process classes — reuse the generated-universe engine verbatim (libRoadRunner
# CSTR, catalyst saturation, ledger witnesses, the post-hoc detector), swapping
# only the universe. ``RTCANetworkProcess`` is the favorable arm;
# ``RTCANullProcess`` is its degree-preserving matched null for topology-
# specificity. ``_RTCA_POTENTIALS`` caches the eQuilibrator table so repeated
# instantiation (sweeps, seeded/unseeded pairs) resolves thermo once.
# --------------------------------------------------------------------------- #
from .universe_process import ReactionUniverseProcess, NullNetworkProcess  # noqa: E402

_RTCA_POTENTIALS: dict[str, float] | None = None


def _cached_potentials() -> dict[str, float]:
    global _RTCA_POTENTIALS
    if _RTCA_POTENTIALS is None:
        _RTCA_POTENTIALS = rtca_potentials()
    return dict(_RTCA_POTENTIALS)


_DRIVE_SCHEMA = {"carboxylation_drive_kj": {"_type": "float", "_default": 0.0, "_units": "kilojoule/mole",
                                            "_provenance": "counterfactual"}}


class RTCANetworkProcess(ReactionUniverseProcess):
    """The curated mechanistic rTCA network on the real libRoadRunner engine —
    identical machinery to the rule-generated universe, only the network is the
    hand-curated reductive-TCA cycle (:func:`build_rtca_universe`).
    ``carboxylation_drive_kj`` (default 0) is the labelled stronger-reductant
    counterfactual, off for the real vent result."""

    config_schema = {**ReactionUniverseProcess.config_schema, **_DRIVE_SCHEMA}

    def build_universe(self):  # type: ignore[override]
        return build_rtca_universe(potentials=_cached_potentials(),
                                   carboxylation_drive_kj=float(self.config.get("carboxylation_drive_kj", 0.0)))


class RTCANullProcess(ReactionUniverseProcess):
    """Degree-preserving matched null of the rTCA network (same compounds,
    reaction count, arity, catalyst density, carbon balance; topology rewired),
    for the topology-specificity arm. ``null_seed`` picks the draw."""

    config_schema = {**ReactionUniverseProcess.config_schema, **_DRIVE_SCHEMA}

    def build_universe(self):  # type: ignore[override]
        base = build_rtca_universe(potentials=_cached_potentials(),
                                   carboxylation_drive_kj=float(self.config.get("carboxylation_drive_kj", 0.0)))
        seed = int(self.config.get("null_seed", 0))
        return U.null_network(base, seed if seed >= 0 else 0)


__all__ = [
    "OAA", "MALATE", "SUCCINATE", "AKG", "PYRUVATE", "ACETATE",
    "CITRATE", "ISOCITRATE", "ACONITATE", "BRANCHED", "ORGANICS", "CARRIER",
    "rtca_potentials", "rtca_reactions", "build_rtca_universe",
    "RTCANetworkProcess", "RTCANullProcess",
]
