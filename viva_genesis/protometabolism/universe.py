"""Reaction universe — a rule-generated open C/H/O network (Model Upgrade Phase 3).

The Phase-3 ``proto_metabolism`` class ``reaction_universe``: instead of a
hand-curated reaction graph (og-02's rTCA fragment), the network is *generated*
by applying a small set of prebiotic reaction rules (Wołos et al. 2020 style —
``wolos2020synthetic``) exhaustively to a C1–C3 reduced-carbon feedstock, bounded
by a maximum carbon count. Every generated reaction is reversible with
thermodynamically consistent kinetics (``k_r = k_f exp(ΔG'°/RT)``), carries a
catalyst-class requirement with a shared, saturating site pool, and every
species degrades to a tar sink and washes out. Nothing in the rule set names a
cycle: autocatalytic motifs, if any, are detected *post hoc*
(``viva_genesis.protometabolism.motifs``).

Molecular representation
------------------------
Molecules are **linear carbon skeletons**: a tuple of carbon-unit codes read
along the chain (canonicalised up to reversal)::

    terminal units   A = carboxyl (COOH)   D = aldehyde (CHO)
                     H = hydroxymethyl (CH2OH)   M = methyl (CH3)
    internal units   K = ketone (C=O)   O = hydroxyl (CHOH)   C = methylene (CH2)
    C1 specials      Q = CO2;  (A,) formate, (D,) formaldehyde, (H,) methanol

The formula (C, H, O) follows from the unit counts; element balance of every
generated reaction is therefore *exact by construction* and the element ledger
(``element_residual``) witnesses it. Branched skeletons (citrate, isobutyrate)
and alkenes are outside the v1 representation — a recorded limitation.

Thermodynamics
--------------
A potential ``G'(X)`` (kJ/mol at the package's pH / ionic strength / T) is the
transformed ΔG'° of the formation reaction ``c CO2 + m H2 → X + k H2O`` from the
real eQuilibrator component-contribution engine (``beber2022equilibrator``,
``noor2013consistent``) when the skeleton resolves to a KEGG compound whose
formula matches; reaction ΔG'° = Σ ν G'(X) is then *identical* to eQuilibrator's
own reaction estimate for catalogued compounds (tested). Skeletons without a
catalogue entry get a group-additivity estimate fitted to the catalogued ones
(provenance ``inferred``, method recorded, fit RMSE reported). The committed
vg-data package ``reaction_universe`` carries the table so the universe builds
without eQuilibrator; ``build_thermo_table`` recomputes it live.

Null networks
-------------
``null_network(universe, seed)`` rewires the species–reaction bipartite graph by
degree-preserving swaps restricted to species of equal carbon count
(``maslov2002specificity``): the null keeps the compound set, the reaction
count, each reaction's arity, each species' participation count, the catalyst
class of every reaction and carbon balance; it loses H/O balance and chemical
meaning. Its reaction energies are recomputed from the same compound potentials
(so the null is thermodynamically consistent) and its energetic span is
reported beside the universe's.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from itertools import product as iproduct
from pathlib import Path
from typing import Iterable

import numpy as np

R_KJ = 8.314462618e-3  # kJ/mol/K

# --------------------------------------------------------------------------- #
# Carbon units and skeletons
# --------------------------------------------------------------------------- #
UNIT_FORMULA: dict[str, tuple[int, int, int]] = {   # (C, H, O) per unit in a chain
    "Q": (1, 0, 2),  # CO2
    "A": (1, 1, 2),  # -COOH
    "D": (1, 1, 1),  # -CHO
    "H": (1, 3, 1),  # -CH2OH
    "M": (1, 3, 0),  # -CH3
    "K": (1, 0, 1),  # >C=O
    "O": (1, 2, 1),  # >CHOH
    "C": (1, 2, 0),  # >CH2
}
TERMINAL = ("A", "D", "H", "M")
INTERNAL = ("K", "O", "C")
CARBONYL = ("D", "K")

CO2, H2, H2O, TAR = "CO2", "H2", "H2O", "tar"
SPECIAL_FORMULAS = {CO2: {"C": 1, "O": 2}, H2: {"H": 2}, H2O: {"H": 2, "O": 1}}

# Skeleton -> (KEGG id, common name). Every id is verified against the
# eQuilibrator compound formula (C and O counts; H up to the charge) before
# use; a mismatch raises, so a wrong id can never silently supply a ΔG'.
CATALOG: dict[tuple[str, ...], tuple[str, str]] = {
    ("Q",): ("kegg:C00011", "CO2"),
    ("A",): ("kegg:C00058", "formate"),
    ("D",): ("kegg:C00067", "formaldehyde"),
    ("H",): ("kegg:C00132", "methanol"),
    ("A", "A"): ("kegg:C00209", "oxalate"),
    ("A", "D"): ("kegg:C00048", "glyoxylate"),
    ("A", "H"): ("kegg:C00160", "glycolate"),
    ("A", "M"): ("kegg:C00033", "acetate"),
    ("D", "H"): ("kegg:C00266", "glycolaldehyde"),
    ("D", "M"): ("kegg:C00084", "acetaldehyde"),
    ("H", "H"): ("kegg:C01380", "ethylene_glycol"),
    ("H", "M"): ("kegg:C00469", "ethanol"),
    ("A", "K", "M"): ("kegg:C00022", "pyruvate"),
    ("A", "O", "M"): ("kegg:C00186", "lactate"),
    ("D", "O", "H"): ("kegg:C00577", "glyceraldehyde"),
    ("H", "K", "H"): ("kegg:C00184", "dihydroxyacetone"),
    ("A", "O", "H"): ("kegg:C00258", "glycerate"),
    ("H", "O", "H"): ("kegg:C00116", "glycerol"),
    ("A", "C", "A"): ("kegg:C00383", "malonate"),
    ("A", "C", "M"): ("kegg:C00163", "propionate"),
    ("A", "K", "H"): ("kegg:C00168", "hydroxypyruvate"),
    ("A", "O", "A"): ("kegg:C02287", "tartronate"),
    ("D", "K", "M"): ("kegg:C00546", "methylglyoxal"),
    ("A", "C", "D"): ("kegg:C00222", "malonate_semialdehyde"),
    ("D", "O", "M"): ("kegg:C00424", "lactaldehyde"),
    ("A", "C", "H"): ("kegg:C01013", "3_hydroxypropionate"),
    ("H", "K", "M"): ("kegg:C05235", "hydroxyacetone"),
    ("H", "O", "M"): ("kegg:C00583", "propane_1_2_diol"),
    ("D", "C", "M"): ("kegg:C00479", "propanal"),
    ("H", "C", "M"): ("kegg:C05979", "propan_1_ol"),
    ("M", "K", "M"): ("kegg:C00207", "acetone"),
    ("H", "C", "H"): ("kegg:C02457", "propane_1_3_diol"),
    ("A", "C", "K", "A"): ("kegg:C00036", "oxaloacetate"),
    ("A", "C", "O", "A"): ("kegg:C00149", "malate"),
    ("A", "C", "C", "A"): ("kegg:C00042", "succinate"),
    ("D", "O", "O", "H"): ("kegg:C01796", "erythrose"),
    ("H", "K", "O", "H"): ("kegg:C02022", "erythrulose"),
    ("A", "C", "K", "M"): ("kegg:C00164", "acetoacetate"),
    ("A", "K", "C", "M"): ("kegg:C00109", "2_oxobutanoate"),
    ("A", "C", "O", "M"): ("kegg:C01089", "3_hydroxybutyrate"),
    ("A", "C", "C", "D"): ("kegg:C00232", "succinate_semialdehyde"),
    ("H", "O", "O", "H"): ("kegg:C00503", "erythritol"),
    ("A", "O", "C", "M"): ("kegg:C05984", "2_hydroxybutyrate"),
    ("A", "O", "O", "A"): ("kegg:C00898", "tartrate"),
    ("M", "K", "K", "M"): ("kegg:C00741", "butane_2_3_dione"),
    ("M", "K", "O", "M"): ("kegg:C00810", "acetoin"),
    ("M", "O", "O", "M"): ("kegg:C03044", "butane_2_3_diol"),
    ("A", "C", "C", "M"): ("kegg:C00246", "butyrate"),
    ("D", "C", "C", "M"): ("kegg:C01412", "butanal"),
    ("H", "C", "C", "M"): ("kegg:C06142", "butan_1_ol"),
    ("A", "K", "O", "A"): ("kegg:C03459", "2_hydroxy_3_oxosuccinate"),
}


def canon(skel: Iterable[str]) -> tuple[str, ...]:
    t = tuple(skel)
    return min(t, t[::-1])


def species_id(skel: tuple[str, ...]) -> str:
    return CO2 if skel == ("Q",) else "X_" + "".join(canon(skel))


def skeleton_of(sid: str) -> tuple[str, ...] | None:
    if sid == CO2:
        return ("Q",)
    return tuple(sid[2:]) if sid.startswith("X_") else None


def formula(skel: tuple[str, ...]) -> dict[str, int]:
    c = h = o = 0
    for u in skel:
        dc, dh, do = UNIT_FORMULA[u]
        c += dc; h += dh; o += do
    if len(skel) == 1 and skel[0] != "Q":
        h += 1   # the lone carbon carries the chain bond's hydrogen
    return {"C": c, "H": h, "O": o}


def n_carbons(sid: str) -> int:
    """Organic carbon count of a species (0 for CO2, H2, H2O, tar)."""
    if sid == CO2:
        return 0
    skel = skeleton_of(sid)
    return len(skel) if skel else 0


def common_name(skel: tuple[str, ...]) -> str:
    entry = CATALOG.get(canon(skel))
    return entry[1] if entry else "s_" + "".join(canon(skel))


def enumerate_skeletons(max_carbons: int) -> list[tuple[str, ...]]:
    """Every linear C/H/O skeleton up to ``max_carbons`` (canonical, sorted)."""
    out = {("Q",), ("A",), ("D",), ("H",)}
    for n in range(2, max_carbons + 1):
        for t1 in TERMINAL:
            for inner in iproduct(INTERNAL, repeat=n - 2):
                for t2 in TERMINAL:
                    out.add(canon((t1, *inner, t2)))
    return sorted(out, key=lambda s: (len(s), s))


# --------------------------------------------------------------------------- #
# Reactions and rules
# --------------------------------------------------------------------------- #
@dataclass
class Reaction:
    id: str
    reactants: dict[str, int]
    products: dict[str, int]
    rule: str
    catalyst: str              # "mineral" | "base" | "none"
    rate_param: str            # package parameter id of the forward rate constant
    reversible: bool = True
    kind: str = "internal"     # internal | feed | wash | degradation
    dg0: float = 0.0           # kJ/mol, forward direction

    def key(self) -> tuple:
        r = tuple(sorted(self.reactants.items())); p = tuple(sorted(self.products.items()))
        return (r, p) if r <= p else (p, r)


# rule name -> (catalyst class, forward-rate parameter id)
RULES: dict[str, tuple[str, str]] = {
    "co2_reduction": ("mineral", "k_co2_reduction"),
    "reduce_carbonyl": ("mineral", "k_reduce"),
    "reduce_carboxyl": ("mineral", "k_reduce_carboxyl"),
    "formose_initiation": ("base", "k_formose_init"),
    "deoxygenate": ("mineral", "k_deoxygenate"),
    "carboxylate_alpha": ("mineral", "k_carboxylate"),
    "carboxylate_reductive": ("mineral", "k_carboxylate_reductive"),
    "aldol": ("base", "k_aldol"),
    "isomerize": ("base", "k_isomerize"),
    "decarboxylate_alpha": ("none", "k_decarboxylate"),
    "decarboxylate_beta": ("none", "k_decarboxylate"),
    "cannizzaro": ("base", "k_cannizzaro"),
}


def _orientations(skel):
    yield tuple(skel)
    if tuple(skel) != tuple(skel)[::-1]:
        yield tuple(skel)[::-1]


def _rxn(rule, reactants: dict, products: dict) -> Reaction:
    cat, kp = RULES[rule]
    return Reaction(id="", reactants=dict(reactants), products=dict(products), rule=rule,
                    catalyst=cat, rate_param=kp)


def _add(counter: dict, sid: str, n: int = 1):
    counter[sid] = counter.get(sid, 0) + n
    return counter


def generate_reactions(skeletons: list[tuple[str, ...]], max_carbons: int) -> list[Reaction]:
    """Apply every rule to every skeleton (pair); products beyond ``max_carbons``
    or outside the linear representation are dropped. Deduplicated by
    (reactants, products) irrespective of direction."""
    allowed = set(skeletons)
    rxns: list[Reaction] = []

    def ok(skel) -> bool:
        return 1 <= len(skel) <= max_carbons and canon(skel) in allowed

    for s in skeletons:
        X = species_id(s)
        if s == ("Q",):
            rxns.append(_rxn("co2_reduction", {CO2: 1, H2: 1}, {species_id(("A",)): 1}))
            continue
        if s == ("D",):   # formose initiation (Breslow 1959): 2 CH2O -> glycolaldehyde
            if ok(("D", "H")):
                rxns.append(_rxn("formose_initiation", {X: 2}, {species_id(("D", "H")): 1}))
        for o in _orientations(s):
            n = len(o)
            # 1. carbonyl reduction: D -> H, K -> O   (X + H2 -> Y)
            for i, u in enumerate(o):
                if u in ("D", "K"):
                    y = list(o); y[i] = "H" if u == "D" else "O"
                    if ok(y):
                        rxns.append(_rxn("reduce_carbonyl", {X: 1, H2: 1}, {species_id(tuple(y)): 1}))
            # 2. carboxyl reduction: A -> D  (X + H2 -> Y + H2O)
            if o[0] == "A":
                y = ("D",) + o[1:]
                if ok(y):
                    rxns.append(_rxn("reduce_carboxyl", {X: 1, H2: 1}, {species_id(y): 1, H2O: 1}))
            # 3. deoxygenation: H -> M, O -> C  (X + H2 -> Y + H2O); methane excluded
            for i, u in enumerate(o):
                if u in ("H", "O") and not (n == 1):
                    y = list(o); y[i] = "M" if u == "H" else "C"
                    if ok(y):
                        rxns.append(_rxn("deoxygenate", {X: 1, H2: 1}, {species_id(tuple(y)): 1, H2O: 1}))
            # 4. enol carboxylation at a terminal M/H alpha to a carbonyl (X + CO2 -> Y)
            if n >= 2 and o[0] in ("M", "H") and o[1] in CARBONYL:
                y = ("A", "C" if o[0] == "M" else "O") + o[1:]
                if ok(y):
                    rxns.append(_rxn("carboxylate_alpha", {X: 1, CO2: 1}, {species_id(y): 1}))
            # 5. reductive carboxylation of a carboxyl (X + CO2 + H2 -> Y + H2O)
            if o[0] == "A":
                y = ("A", "D") if n == 1 else ("A", "K") + o[1:]
                if ok(y):
                    rxns.append(_rxn("carboxylate_reductive", {X: 1, CO2: 1, H2: 1},
                                     {species_id(y): 1, H2O: 1}))
            # 7. aldose-ketose isomerisation (terminal D,O <-> H,K ; internal K,O <-> O,K)
            if n >= 2 and o[0] == "D" and o[1] == "O":
                y = ("H", "K") + o[2:]
                if ok(y):
                    rxns.append(_rxn("isomerize", {X: 1}, {species_id(y): 1}))
            for i in range(1, n - 2):
                if o[i] == "K" and o[i + 1] == "O":
                    y = list(o); y[i], y[i + 1] = "O", "K"
                    if ok(y) and canon(tuple(y)) != canon(o):
                        rxns.append(_rxn("isomerize", {X: 1}, {species_id(tuple(y)): 1}))
            # 8. decarboxylation: alpha (A,K.. -> D.. + CO2 ; A,D -> D + CO2) and beta (A,C,K.. -> M,K.. + CO2)
            if n >= 2 and o[0] == "A" and o[1] in CARBONYL:
                y = ("D",) + o[2:] if o[1] == "K" else ("D",)
                if ok(y):
                    rxns.append(_rxn("decarboxylate_alpha", {X: 1}, {species_id(y): 1, CO2: 1}))
            if n >= 3 and o[0] == "A" and o[1] == "C" and o[2] in CARBONYL:
                y = ("M",) + o[2:]
                if ok(y):
                    rxns.append(_rxn("decarboxylate_beta", {X: 1}, {species_id(y): 1, CO2: 1}))
            # 10. Cannizzaro disproportionation: 2 R-CHO + H2O -> R-COOH + R-CH2OH
            if o[0] == "D":
                ya = ("A",) + o[1:]; yh = ("H",) + o[1:]
                if ok(ya) and ok(yh):
                    rxns.append(_rxn("cannizzaro", {X: 2, H2O: 1}, {species_id(ya): 1, species_id(yh): 1}))
    # 6. aldol addition (electrophile R-CHO + nucleophile with terminal M/H alpha to a carbonyl)
    electrophiles = [o for s in skeletons if s != ("Q",) for o in _orientations(s) if o[-1] == "D"]
    nucleophiles = [o for s in skeletons if s != ("Q",) for o in _orientations(s)
                    if len(o) >= 2 and o[0] in ("M", "H") and o[1] in CARBONYL]
    for e in electrophiles:
        for nuc in nucleophiles:
            if len(e) + len(nuc) > max_carbons:
                continue
            e_part = (e[:-1] + ("O",)) if len(e) > 1 else ("H",)
            n_part = ("C" if nuc[0] == "M" else "O",) + nuc[1:]
            y = e_part + n_part
            if not ok(y):
                continue
            reactants: dict[str, int] = {}
            _add(reactants, species_id(e)); _add(reactants, species_id(nuc))
            rxns.append(_rxn("aldol", reactants, {species_id(y): 1}))
    # dedupe (direction-agnostic) and number
    seen, out = set(), []
    for r in rxns:
        k = r.key()
        if k in seen or r.reactants == r.products:
            continue
        seen.add(k)
        r.id = f"r{len(out)}"
        out.append(r)
    return out


def element_matrix(species: list[str], formulas: dict[str, dict[str, int]]) -> np.ndarray:
    """Rows C, H, O; columns ``species``. Species without a formula (tar) -> zeros."""
    E = np.zeros((3, len(species)))
    for j, s in enumerate(species):
        f = formulas.get(s) or {}
        E[0, j] = f.get("C", 0); E[1, j] = f.get("H", 0); E[2, j] = f.get("O", 0)
    return E


def stoichiometric_matrix(species: list[str], reactions: list[Reaction]) -> np.ndarray:
    idx = {s: i for i, s in enumerate(species)}
    S = np.zeros((len(species), len(reactions)))
    for j, r in enumerate(reactions):
        for s, n in r.reactants.items():
            S[idx[s], j] -= n
        for s, n in r.products.items():
            S[idx[s], j] += n
    return S


# --------------------------------------------------------------------------- #
# Thermodynamics: eQuilibrator potentials + group-additivity fallback
# --------------------------------------------------------------------------- #
@dataclass
class ThermoConditions:
    p_h: float = 9.38
    ionic_strength_M: float = 0.25
    temperature_K: float = 322.35

    def to_dict(self) -> dict:
        return {"p_h": self.p_h, "ionic_strength_M": self.ionic_strength_M, "temperature_K": self.temperature_K}


def formation_formula(skel: tuple[str, ...]) -> tuple[int, int, int]:
    """(c, m, k) in ``c CO2 + m H2 -> X + k H2O``; k = 2c - o, m = (h + 2k) / 2."""
    f = formula(skel)
    c, h, o = f["C"], f["H"], f["O"]
    k = 2 * c - o
    m2 = h + 2 * k
    if m2 % 2:
        raise ValueError(f"odd hydrogen count for {skel}: {f}")
    return c, m2 // 2, k


def _check_kegg_formula(cc, kegg: str, skel: tuple[str, ...]) -> None:
    comp = cc.get_compound(kegg)
    if comp is None or not getattr(comp, "formula", None):
        raise LookupError(f"{kegg} ({common_name(skel)}) not found in the eQuilibrator cache")
    import re
    counts = {el: int(n or 1) for el, n in re.findall(r"([A-Z][a-z]?)(\d*)", comp.formula)}
    f = formula(skel)
    if counts.get("C", 0) != f["C"] or counts.get("O", 0) != f["O"] or set(counts) - {"C", "H", "O"}:
        raise ValueError(f"{kegg} formula {comp.formula} does not match skeleton {skel} {f}")
    if not (f["H"] - 2 <= counts.get("H", 0) <= f["H"]):   # major microspecies may be de-protonated
        raise ValueError(f"{kegg} hydrogen count {comp.formula} inconsistent with {skel} {f}")


def _group_features(skel: tuple[str, ...]) -> np.ndarray:
    cnt = Counter(skel)
    feats = [cnt.get(u, 0) for u in ("A", "D", "H", "M", "K", "O", "C")]
    feats.append(max(len(skel) - 1, 0))                      # chain C-C bonds
    feats.append(sum(1 for a, b in zip(skel, skel[1:]) if {a, b} <= {"K", "O", "A", "D"}))  # vicinal O-bearing pairs
    return np.array(feats, dtype=float)


def build_thermo_table(skeletons: list[tuple[str, ...]], cond: ThermoConditions,
                       *, progress=None) -> dict:
    """Compute ``G'(X)`` for every skeleton: eQuilibrator for catalogued compounds
    (formula-verified), group-additivity (fitted to those) for the rest.

    Returns ``{"conditions", "engine", "compounds": {species_id: {...}}, "fit": {...}}``.
    Requires ``equilibrator_api`` (raises ImportError otherwise — callers that
    only need the committed table use :func:`load_thermo_table`).
    """
    from equilibrator_api import Q_
    import equilibrator_api
    from viva_equilibrator import get_component_contribution  # imported engine (shared cache)
    cc = get_component_contribution()
    cc.p_h = Q_(float(cond.p_h))
    cc.ionic_strength = Q_(f"{float(cond.ionic_strength_M)} M")
    cc.temperature = Q_(f"{float(cond.temperature_K)} K")
    compounds: dict[str, dict] = {}
    resolved: list[tuple[np.ndarray, float]] = []
    for skel in skeletons:
        sid = species_id(skel)
        entry = {"skeleton": "".join(skel), "name": common_name(skel), "formula": formula(skel)}
        if skel == ("Q",):
            entry.update(dg_prime_kj_mol=0.0, sigma_kj_mol=0.0, provenance="inferred",
                         method="reference (CO2 / H2 / H2O potentials are zero by construction)",
                         kegg="kegg:C00011")
            compounds[sid] = entry
            continue
        cat = CATALOG.get(canon(skel))
        if cat is not None:
            kegg, _ = cat
            _check_kegg_formula(cc, kegg, skel)
            c, m, k = formation_formula(skel)
            lhs = " + ".join(x for x in ((f"{c} kegg:C00011" if c else ""), (f"{m} kegg:C00282" if m else "")) if x)
            rhs = kegg + (f" + {k} kegg:C00001" if k > 0 else "")
            if k < 0:
                lhs += f" + {-k} kegg:C00001"
            rxn = cc.parse_reaction_formula(f"{lhs} = {rhs}")
            dg = cc.standard_dg_prime(rxn)
            val = float(dg.value.to("kJ/mol").magnitude); sig = float(dg.error.to("kJ/mol").magnitude)
            entry.update(dg_prime_kj_mol=val, sigma_kj_mol=sig, provenance="inferred", kegg=kegg,
                         method="eQuilibrator component contribution: transformed dG'° of "
                                f"{c} CO2 + {m} H2 -> X + {k} H2O")
            resolved.append((_group_features(skel), val))
            if progress:
                progress(f"  {sid:12s} {common_name(skel):24s} {val:9.1f} ± {sig:4.1f} kJ/mol")
        compounds[sid] = entry
    # group-additivity fit on the resolved set
    A = np.array([f for f, _ in resolved]); y = np.array([v for _, v in resolved])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ beta
    rmse = float(np.sqrt(np.mean(resid ** 2)))
    # leave-one-out RMSE (honest predictive error of the fallback)
    loo = []
    for i in range(len(y)):
        m = np.ones(len(y), bool); m[i] = False
        b, *_ = np.linalg.lstsq(A[m], y[m], rcond=None)
        loo.append(float(y[i] - A[i] @ b))
    loo_rmse = float(np.sqrt(np.mean(np.square(loo))))
    n_est = 0
    for skel in skeletons:
        sid = species_id(skel)
        if "dg_prime_kj_mol" in compounds[sid]:
            continue
        val = float(_group_features(skel) @ beta)
        compounds[sid].update(dg_prime_kj_mol=val, sigma_kj_mol=loo_rmse, provenance="inferred",
                              kegg=None,
                              method="group additivity fitted to the eQuilibrator-resolved catalogue "
                                     f"(LOO RMSE {loo_rmse:.1f} kJ/mol)")
        n_est += 1
    return {
        "conditions": cond.to_dict(),
        "engine": {"name": "equilibrator_api", "version": getattr(equilibrator_api, "__version__", "?"),
                   "method": "component contribution (Noor 2013), transformed dG'° (Beber 2022)"},
        "compounds": compounds,
        "fit": {"n_resolved": len(resolved), "n_estimated": n_est, "rmse_kj_mol": rmse,
                "loo_rmse_kj_mol": loo_rmse,
                "features": ["A", "D", "H", "M", "K", "O", "C", "chain_bonds", "vicinal_oxygenated"],
                "coefficients": [float(b) for b in beta]},
    }


def reaction_dg0(r: Reaction, potentials: dict[str, float]) -> float:
    g = 0.0
    for s, n in r.products.items():
        g += n * potentials.get(s, 0.0)
    for s, n in r.reactants.items():
        g -= n * potentials.get(s, 0.0)
    return g


# --------------------------------------------------------------------------- #
# The universe
# --------------------------------------------------------------------------- #
@dataclass
class Universe:
    species: list[str]                 # CO2 + H2 + organic skeleton species (floating) + H2O (boundary, last)
    reactions: list[Reaction]          # internal reactions only (exchange added at emission)
    potentials: dict[str, float]       # G'(X) kJ/mol
    formulas: dict[str, dict[str, int]]
    conditions: ThermoConditions
    max_carbons: int
    label: str = "reaction_universe"
    null_seed: int | None = None
    meta: dict = field(default_factory=dict)

    # -- summaries -----------------------------------------------------------
    def organics(self) -> list[str]:
        return [s for s in self.species if s.startswith("X_")]

    def energetic_span(self) -> dict:
        dg = np.array([r.dg0 for r in self.reactions])
        return {"min": float(dg.min()), "max": float(dg.max()), "span": float(dg.max() - dg.min()),
                "mean": float(dg.mean()), "sd": float(dg.std())}

    def catalyst_density(self) -> dict[str, int]:
        return dict(Counter(r.catalyst for r in self.reactions))

    def rule_counts(self) -> dict[str, int]:
        return dict(Counter(r.rule for r in self.reactions))

    def element_residual(self) -> dict:
        """max |E S| over internal reactions (exact 0 for a generated universe)."""
        E = element_matrix(self.species, self.formulas)
        S = stoichiometric_matrix(self.species, self.reactions)
        res = E @ S
        worst = np.abs(res).max(axis=0)
        offenders = [self.reactions[j].id for j in np.argsort(-worst)[:5] if worst[j] > 0]
        return {"max_abs": float(np.abs(res).max()) if res.size else 0.0,
                "per_element": {"C": float(np.abs(res[0]).max()), "H": float(np.abs(res[1]).max()),
                                "O": float(np.abs(res[2]).max())} if res.size else {},
                "n_unbalanced": int((worst > 1e-12).sum()), "offenders": offenders}

    def summary(self) -> dict:
        return {"label": self.label, "n_species": len(self.organics()), "n_reactions": len(self.reactions),
                "max_carbons": self.max_carbons, "rule_counts": self.rule_counts(),
                "catalyst_density": self.catalyst_density(), "energetic_span_kj_mol": self.energetic_span(),
                "element_residual": self.element_residual(), "null_seed": self.null_seed, **self.meta}

    def doubling_reactions(self) -> list[str]:
        """Reactions with a product coefficient > 1 in either direction (the only
        edges that can carry stoichiometric autocatalytic gain)."""
        return [r.id for r in self.reactions
                if any(n > 1 for n in r.products.values()) or any(n > 1 for n in r.reactants.values())]


def build_universe(max_carbons: int = 4, thermo: dict | None = None, cond: ThermoConditions | None = None,
                   *, label: str = "reaction_universe") -> Universe:
    """Generate the universe. ``thermo`` is a thermo table (committed package or
    :func:`build_thermo_table`); when omitted the committed package table is used."""
    skeletons = enumerate_skeletons(max_carbons)
    if thermo is None:
        thermo = load_thermo_table()
    cond = cond or ThermoConditions(**thermo["conditions"])
    comps = thermo["compounds"]
    missing = [species_id(s) for s in skeletons if species_id(s) not in comps]
    if missing:
        raise KeyError(f"thermo table lacks {len(missing)} skeletons (max_carbons={max_carbons}); "
                       f"rebuild the package: {missing[:5]}")
    potentials = {sid: float(comps[sid]["dg_prime_kj_mol"]) for sid in (species_id(s) for s in skeletons)}
    potentials[H2] = 0.0; potentials[H2O] = 0.0; potentials[CO2] = 0.0
    formulas = {species_id(s): formula(s) for s in skeletons}
    formulas.update(SPECIAL_FORMULAS)
    reactions = generate_reactions(skeletons, max_carbons)
    for r in reactions:
        r.dg0 = reaction_dg0(r, potentials)
    species = [CO2, H2] + [species_id(s) for s in skeletons if s != ("Q",)] + [H2O]
    return Universe(species=species, reactions=reactions, potentials=potentials, formulas=formulas,
                    conditions=cond, max_carbons=max_carbons, label=label)


# --------------------------------------------------------------------------- #
# Matched null networks
# --------------------------------------------------------------------------- #
def null_network(universe: Universe, seed: int, *, swaps_per_slot: int = 10) -> Universe:
    """Degree-preserving rewiring of the species-reaction graph, swapping only
    species of equal carbon AND oxygen count (C and O balance kept; H balance and
    chemical meaning lost). Reaction ids, rules, catalyst classes and rate parameters stay
    with their reaction; ΔG'° is recomputed from the same compound potentials."""
    rng = np.random.default_rng(seed)
    organics = universe.organics()
    # slots: (reaction index, side, position) holding an organic species
    slots: list[list] = []
    rxns = [Reaction(id=r.id, reactants=dict(r.reactants), products=dict(r.products), rule=r.rule,
                     catalyst=r.catalyst, rate_param=r.rate_param, reversible=r.reversible, kind=r.kind)
            for r in universe.reactions]
    for j, r in enumerate(rxns):
        for side in ("reactants", "products"):
            for s, n in getattr(r, side).items():
                if s in organics:
                    for _ in range(n):
                        slots.append([j, side, s])
    # swap only within (carbon count, oxygen count) classes: C and O balance are
    # kept, H balance and functional-group logic are destroyed
    by_c: dict[tuple, list[int]] = {}
    for i, (_, _, s) in enumerate(slots):
        f = universe.formulas[s]
        by_c.setdefault((f["C"], f["O"]), []).append(i)
    n_swaps = swaps_per_slot * len(slots)
    done = 0
    for _ in range(n_swaps * 5):
        if done >= n_swaps:
            break
        group = by_c[list(by_c)[int(rng.integers(len(by_c)))]]
        if len(group) < 2:
            continue
        a, b = rng.choice(group, 2, replace=False)
        if slots[a][0] == slots[b][0] or slots[a][2] == slots[b][2]:
            continue
        slots[a][2], slots[b][2] = slots[b][2], slots[a][2]
        done += 1
    # rebuild stoichiometries
    for r in rxns:
        r.reactants = {s: n for s, n in r.reactants.items() if s not in organics}
        r.products = {s: n for s, n in r.products.items() if s not in organics}
    for j, side, s in slots:
        d = getattr(rxns[j], side)
        d[s] = d.get(s, 0) + 1
    # drop degenerate reactions (same species both sides cancel) and recompute dG
    kept = []
    for r in rxns:
        common = set(r.reactants) & set(r.products)
        for s in common:
            n = min(r.reactants[s], r.products[s])
            r.reactants[s] -= n; r.products[s] -= n
            if r.reactants[s] == 0: del r.reactants[s]
            if r.products[s] == 0: del r.products[s]
        if not r.reactants or not r.products:
            continue
        r.dg0 = reaction_dg0(r, universe.potentials)
        kept.append(r)
    nu = Universe(species=list(universe.species), reactions=kept, potentials=dict(universe.potentials),
                  formulas=dict(universe.formulas), conditions=universe.conditions,
                  max_carbons=universe.max_carbons, label="null_network", null_seed=int(seed),
                  meta={"n_swaps": done, "n_dropped_degenerate": len(rxns) - len(kept)})
    return nu


# --------------------------------------------------------------------------- #
# Antimony emission (the SBML the libRoadRunner engine integrates)
# --------------------------------------------------------------------------- #
# Rate constant of each rule's EXERGONIC direction (see to_antimony): the
# catalyst sets the downhill turnover; the uphill direction follows from
# detailed balance and is never faster than k0.
DEFAULT_KINETICS = {
    "k_co2_reduction": 2.0, "k_reduce": 10.0, "k_reduce_carboxyl": 1.0e-2, "k_deoxygenate": 0.5,
    "k_carboxylate": 50.0, "k_carboxylate_reductive": 0.02,
    "k_aldol": 100.0, "k_formose_init": 1.0e-2, "k_isomerize": 0.05, "k_decarboxylate": 0.02,
    "k_cannizzaro": 1.0,
    "sites_mineral": 1.0, "sites_base": 1.0, "K_sat": 1.0e-2,
    "k_deg": 1.0e-3, "aldehyde_degradation_factor": 5.0,
    "k_wash": 0.05, "k_feed": 0.5,
}
FEED_SPECIES = {"CO2": "feed_CO2", "H2": "feed_H2", "X_AKM": "feed_pyruvate", "X_D": "feed_formaldehyde",
                "X_A": "feed_formate", "X_AM": "feed_acetate"}


def _sid(s: str) -> str:
    return s


def to_antimony(u: Universe, kin: dict | None = None, feeds: dict[str, float] | None = None,
                *, initial: dict[str, float] | None = None) -> str:
    """Emit the universe (or a null) as an Antimony model with exchange reactions,
    catalyst-pool saturation, thermodynamically consistent reverse rates and the
    carbon-ledger integrator species."""
    kin = {**DEFAULT_KINETICS, **(kin or {})}
    feeds = dict(feeds or {})
    RT = R_KJ * u.conditions.temperature_K
    organics = u.organics()
    lines = ["model reaction_universe()"]
    floating = [s for s in u.species if s != H2O]
    lines.append("  species " + ", ".join(floating + [TAR]) + ";")
    lines.append(f"  species ${H2O};")
    lines.append("  species Cfeed, Cfix, Cwash, Cdeg;")
    for k, v in kin.items():
        lines.append(f"  {k} = {v!r};")
    for sid, pid in FEED_SPECIES.items():
        lines.append(f"  {pid} = {feeds.get(pid, 0.0)!r};")
    # Catalyst-pool crowding factors f_<class> are plain parameters: the process
    # recomputes them every tick from the current organic load
    # (:func:`catalyst_factors`) rather than as assignment rules, which
    # libRoadRunner would inline into every rate law (quadratic JIT cost).
    loads = {"mineral": None, "base": None}
    for cls in loads:
        lines.append(f"  f_{cls} = {kin['sites_' + cls]!r};")
    # internal reactions
    fix_terms = []
    for r in u.reactions:
        lhs = " + ".join(f"{n} {s}" if n > 1 else s for s, n in r.reactants.items())
        rhs = " + ".join(f"{n} {s}" if n > 1 else s for s, n in r.products.items())
        fwd = "*".join(f"{s}^{n}" if n > 1 else s for s, n in r.reactants.items() if s != H2O) or "1"
        rev = "*".join(f"{s}^{n}" if n > 1 else s for s, n in r.products.items() if s != H2O) or "1"
        # Exergonic-direction class rate: the downhill direction runs at the rule's
        # k0, the uphill one at k0 exp(-|dG0|/RT) (detailed balance k_r/k_f =
        # exp(dG0/RT) holds exactly; no rate ever exceeds k0, so a rewired null
        # with a huge |dG0| simply becomes irreversible instead of overflowing).
        x = r.dg0 / RT
        if x <= 0.0:
            f_fac, r_fac = 1.0, math.exp(max(x, -700.0))
        else:
            f_fac, r_fac = math.exp(-min(x, 700.0)), 1.0
        cat = f"f_{r.catalyst}*" if r.catalyst in loads else ""
        lines.append(f"  {r.id}: {lhs} -> {rhs}; {cat}{r.rate_param}*({f_fac!r}*{fwd} - {r_fac!r}*{rev});")
        nu_co2 = r.products.get(CO2, 0) - r.reactants.get(CO2, 0)
        if nu_co2:
            fix_terms.append(f"({-nu_co2})*{r.id}")
    # exchange. Inorganic feeds (CO2, H2) are vent-buffered: relaxation to the
    # set-point at k_feed (og-02's convention). Organic feeds are CSTR inflow at
    # the dilution rate (k_wash * feed_X), so with no reaction X settles at feed_X.
    # Washout of every floating species at k_wash.
    feed_terms = []
    for sid, pid in FEED_SPECIES.items():
        if sid not in u.species:
            continue
        if sid in (CO2, H2):
            lines.append(f"  J_{sid}: -> {sid}; k_feed*({pid} - {sid});")
        else:
            lines.append(f"  J_{sid}: -> {sid}; k_wash*{pid};")
            feed_terms.append(f"{n_carbons(sid)}*J_{sid}")
    wash_terms, deg_terms = [], []
    for sid in floating:
        lines.append(f"  W_{sid}: {sid} -> ; k_wash*{sid};")
        nc = n_carbons(sid)
        if nc:
            wash_terms.append(f"{nc}*W_{sid}")
    for sid in organics:
        skel = skeleton_of(sid)
        fac = kin["aldehyde_degradation_factor"] if "D" in skel else 1.0
        lines.append(f"  G_{sid}: {sid} -> {TAR}; {fac!r}*k_deg*{sid};")
        deg_terms.append(f"{n_carbons(sid)}*G_{sid}")
    lines.append("  Cfeed' = " + (" + ".join(feed_terms) or "0") + ";")
    lines.append("  Cfix' = " + (" + ".join(fix_terms) or "0") + ";")
    lines.append("  Cwash' = " + (" + ".join(wash_terms) or "0") + ";")
    lines.append("  Cdeg' = " + (" + ".join(deg_terms) or "0") + ";")
    init = dict(initial or {})
    for sid in floating:
        lines.append(f"  {sid} = {init.get(sid, 0.0)!r};")
    lines.append(f"  {TAR} = 0; {H2O} = 1; Cfeed = 0; Cfix = 0; Cwash = 0; Cdeg = 0;")
    lines.append("end")
    return "\n".join(lines)


def catalyst_substrates(u: Universe) -> dict[str, list[str]]:
    """Distinct organic species that are reactants of at least one reaction of
    each catalyst class (the species competing for that class's sites)."""
    out: dict[str, set] = {"mineral": set(), "base": set()}
    for r in u.reactions:
        if r.catalyst in out:
            out[r.catalyst].update(s for s in r.reactants if s.startswith("X_"))
    return {k: sorted(v) for k, v in out.items()}


def catalyst_factors(substrates: dict[str, list[str]], conc, kin: dict) -> dict[str, float]:
    """``f_X = sites_X / (1 + load_X / K_sat)`` with ``load_X`` the summed
    concentration of the distinct organic substrates of class X — a shared,
    finite site pool that saturates as organic load grows (catalyst limit)."""
    out = {}
    for cls, species in substrates.items():
        load = float(sum(max(float(conc.get(s, 0.0)), 0.0) for s in species))
        out[cls] = float(kin[f"sites_{cls}"]) / (1.0 + load / float(kin["K_sat"]))
    return out


# --------------------------------------------------------------------------- #
# The committed thermo table / package
# --------------------------------------------------------------------------- #
def package_path() -> Path:
    from ..provenance import data_dir
    return data_dir() / "reaction_universe.yaml"


def load_package_dict() -> dict:
    import yaml
    with open(package_path(), encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_thermo_table() -> dict:
    """The committed ΔG' table (eQuilibrator-derived, provenance per compound)."""
    pkg = load_package_dict()
    thermo = pkg.get("thermo")
    if not thermo:
        raise KeyError("reaction_universe package has no thermo table; run build_package()")
    return thermo


def kinetics_from_package(pkg: dict | None = None) -> dict:
    pkg = pkg or load_package_dict()
    out = dict(DEFAULT_KINETICS)
    for p in pkg.get("parameters") or []:
        if p["id"] in out and p.get("value") is not None:
            out[p["id"]] = float(p["value"])
    return out


PACKAGE_PARAMETERS = [
    # id, units, provenance, value, distribution, context, sources, how_to_use
    ("max_carbons", "dimensionless", "hypothetical", 4, None,
     {"scope": "C1-C3 feedstock; rule products capped at C4"}, ["wolos2020synthetic"],
     "Rule-set scope (expert decision open): C<=4 lets the formose (C4 retro-aldol) and reductive-carboxylation "
     "chemistry close while keeping the network ~400 reactions. N/P-bearing rules are NOT in this package."),
    ("k_co2_reduction", "1/molar/second", "extrapolated", 2.0, {"kind": "loguniform", "low": 0.2, "high": 20.0},
     {"rule": "co2_reduction", "catalyst": "mineral"}, ["preiner2020hydrogen"],
     "CO2 + H2 -> formate on awaruite / magnetite (Preiner 2020 yields are the anchor), carried to the og-02 tick scale."),
    ("k_reduce", "1/molar/second", "hypothetical", 10.0, {"kind": "loguniform", "low": 1.0, "high": 100.0},
     {"rule": "reduce_carbonyl", "catalyst": "mineral"}, ["muchowska2017metals", "muchowska2019synthesis"],
     "Second-order H2 reduction of aldehydes/ketones on Fe/Ni mineral surfaces; order-of-magnitude on the og-02 tick scale."),
    ("k_reduce_carboxyl", "1/second", "hypothetical", 1.0e-2, {"kind": "loguniform", "low": 1.0e-3, "high": 1.0e-1},
     {"rule": "reduce_carboxyl", "catalyst": "mineral", "note": "rate of the EXERGONIC direction (aldehyde + H2O -> acid + H2)"}, [],
     "Carboxyl <-> aldehyde is the hardest reductive step: the downhill aldehyde oxidation is slow (aldehydes are kinetically metastable) and the uphill acid reduction follows from detailed balance — formaldehyde is reachable only by feed, the known C1 bottleneck."),
    ("k_formose_init", "1/molar/second", "extrapolated", 1.0e-2, {"kind": "loguniform", "low": 1.0e-3, "high": 1.0e-1},
     {"rule": "formose_initiation", "catalyst": "base"}, ["breslow1959mechanism"],
     "The slow umpolung initiation 2 CH2O -> glycolaldehyde that seeds the formose cycle (orders slower than the aldol propagation)."),
    ("k_deoxygenate", "1/molar/second", "hypothetical", 0.5, {"kind": "loguniform", "low": 0.05, "high": 5.0},
     {"rule": "deoxygenate", "catalyst": "mineral"}, ["muchowska2017metals"],
     "Alcohol -> alkane with H2 (the slowest reductive step)."),
    ("k_carboxylate", "1/molar/second", "extrapolated", 50.0, {"kind": "loguniform", "low": 5.0, "high": 500.0},
     {"rule": "carboxylate_alpha", "catalyst": "mineral"}, ["muchowska2019synthesis"],
     "Enol carboxylation (pyruvate + CO2 -> OAA); og-02 used k_carb = 50 for the same step — carried over."),
    ("k_carboxylate_reductive", "1/second", "hypothetical", 0.02, {"kind": "loguniform", "low": 2.0e-3, "high": 0.2},
     {"rule": "carboxylate_reductive", "catalyst": "mineral", "note": "rate of the EXERGONIC direction (oxidative decarboxylation of the 2-oxo acid)"},
     ["muchowska2019synthesis"],
     "Reductive carboxylation of a carboxylate with CO2 + H2 (ferredoxin-type chemistry) is uphill at vent concentrations; its rate follows from the downhill oxidative-decarboxylation rate by detailed balance."),
    ("k_aldol", "1/molar/second", "extrapolated", 100.0, {"kind": "loguniform", "low": 10.0, "high": 1000.0},
     {"rule": "aldol", "catalyst": "base"}, ["breslow1959mechanism", "wolos2020synthetic"],
     "Base-catalysed aldol addition (formose chemistry); the 1959 Breslow mechanism, rates extrapolated to the tick scale."),
    ("k_isomerize", "1/second", "extrapolated", 0.05, {"kind": "loguniform", "low": 0.005, "high": 0.5},
     {"rule": "isomerize", "catalyst": "base"}, ["breslow1959mechanism"],
     "Aldose-ketose (enediol) isomerisation; first order."),
    ("k_decarboxylate", "1/second", "extrapolated", 0.02, {"kind": "loguniform", "low": 0.002, "high": 0.2},
     {"rule": "decarboxylate_alpha / decarboxylate_beta", "catalyst": "none"}, ["muchowska2019synthesis"],
     "Thermal alpha-/beta-keto-acid decarboxylation; first order."),
    ("k_cannizzaro", "1/molar/second", "hypothetical", 1.0, {"kind": "loguniform", "low": 0.1, "high": 10.0},
     {"rule": "cannizzaro", "catalyst": "base"}, ["wolos2020synthetic"],
     "Aldehyde disproportionation (the classic formose side reaction)."),
    ("sites_mineral", "dimensionless", "hypothetical", 1.0, {"kind": "loguniform", "low": 0.1, "high": 10.0},
     {"catalyst": "mineral"}, [], "Relative density of Fe/Ni mineral catalytic sites (multiplies every mineral-class rate)."),
    ("sites_base", "dimensionless", "hypothetical", 1.0, {"kind": "loguniform", "low": 0.1, "high": 10.0},
     {"catalyst": "base"}, [], "Relative density of alkaline (Ca/Mg hydroxide) sites for the base-class rules."),
    ("K_sat", "molar", "hypothetical", 1.0e-2, {"kind": "loguniform", "low": 1.0e-3, "high": 1.0e-1},
     {}, [], "Organic load at which a catalyst class's shared site pool is half saturated (the catalyst limit)."),
    ("k_deg", "1/second", "extrapolated", 1.0e-3, {"kind": "loguniform", "low": 1.0e-4, "high": 1.0e-2},
     {"note": "lumped tar formation / hydrolysis"}, ["wolos2020synthetic"],
     "First-order degradation of every organic species to a tar sink (side-reaction loss not captured by the rules)."),
    ("aldehyde_degradation_factor", "dimensionless", "hypothetical", 5.0, None,
     {}, ["breslow1959mechanism"], "Aldehydes degrade faster (polymerisation / caramelisation)."),
    ("k_wash", "1/second", "inferred", 0.05, {"kind": "loguniform", "low": 2.0e-3, "high": 1.0},
     {"model": "CSTR dilution"}, [], "og-02's washout rate; the feed-vs-washout axis of the ignition map."),
    ("k_feed", "1/second", "inferred", 0.5, None, {"model": "vent-buffered CO2 / H2 relaxation"}, [],
     "og-02's feed relaxation rate for the vent-buffered inorganic species."),
    ("feed_CO2", "molar", "calibrated", 1.4e-3, {"kind": "loguniform", "low": 1.2e-3, "high": 2.9e-3},
     {"source": "og-cal-vent-environment posterior example point (DIC)"}, ["kelley2005serpentinite"],
     "The Phase-1 posterior supplies this feed: DIC posterior q05-q95 1.2-2.9 mM; example point 1.4 mM."),
    ("feed_H2", "molar", "calibrated", 1.08e-2, {"kind": "loguniform", "low": 1.0e-3, "high": 1.5e-2},
     {"source": "og-cal-vent-environment posterior example point (dissolved H2 10.8 mmol/kg)"},
     ["kelley2005serpentinite", "proskurowski2008abiogenic"],
     "The Phase-1 posterior supplies this feed: Lost City window 1-15 mmol/kg; example point 10.8."),
    ("feed_pyruvate", "molar", "inferred", 1.0e-4, {"kind": "loguniform", "low": 1.0e-6, "high": 1.0e-3},
     {"source": "og-01 reduced-carbon products (og-02 convention)"}, ["muchowska2019synthesis"],
     "og-01/og-02 pyruvate set-point carried over as the organic CSTR inflow."),
    ("feed_formaldehyde", "molar", "hypothetical", 0.0, {"kind": "loguniform", "low": 1.0e-5, "high": 1.0e-2},
     {"arm": "formose feedstock variant"}, ["breslow1959mechanism"],
     "0 in the canonical arm (the vent makes none at this feed); the formose-arm variant feeds 1 mM to test whether bypassing the C1 bottleneck lets motifs emerge."),
]


def build_package(path: Path | None = None, *, max_carbons: int = 4,
                  cond: ThermoConditions | None = None, progress=None) -> dict:
    """Write the vg-data package ``reaction_universe.yaml``: kinetic / catalyst /
    feed parameters with provenance, the rule table, and the eQuilibrator ΔG'
    table (requires ``equilibrator_api``)."""
    import datetime as _dt
    import yaml
    cond = cond or ThermoConditions()
    skeletons = enumerate_skeletons(max_carbons)
    thermo = build_thermo_table(skeletons, cond, progress=progress)
    u = build_universe(max_carbons, thermo=thermo, cond=cond)
    params = []
    for pid, units, prov, value, dist, ctx, srcs, how in PACKAGE_PARAMETERS:
        d = {"id": pid, "units": units, "provenance": prov, "value": value, "context": ctx,
             "sources": srcs, "how_to_use": how}
        if dist:
            d["distribution"] = dist
        if pid.startswith("feed_"):
            d["consumed_by"] = f"open_chemical_network.{pid}"
        elif pid in DEFAULT_KINETICS or pid == "max_carbons":
            d["consumed_by"] = f"ReactionUniverseProcess.{pid}"
        params.append(d)
    rules = [{"rule": name, "catalyst": cat, "rate_parameter": kp, "n_reactions": u.rule_counts().get(name, 0),
              "reversible": True} for name, (cat, kp) in RULES.items()]
    doc = {
        "name": "reaction_universe", "version": "1",
        "description": (
            "Phase-3 open chemical network: Wolos-2020-style reaction rules over linear C/H/O skeletons "
            f"(C1-C3 feedstock, products capped at C{max_carbons}), eQuilibrator component-contribution "
            "dG' potentials at the Phase-1 posterior vent condition, catalyst-class requirements with a "
            "saturating site pool, degradation and washout. Generated by "
            "viva_genesis.protometabolism.universe.build_package on "
            + _dt.date.today().isoformat() + "."),
        "sources": ["wolos2020synthetic", "blokhuis2020universal", "beber2022equilibrator", "noor2013consistent",
                    "breslow1959mechanism", "muchowska2017metals", "muchowska2019synthesis", "maslov2002specificity"],
        "parameters": params,
        "observations": {},
        "rules": rules,
        "universe_summary": {k: v for k, v in u.summary().items() if k != "element_residual"},
        "thermo": thermo,
        "honesty_notes": [
            "Every rate constant is hypothetical or extrapolated: the rules are real chemistry, the numbers are "
            "order-of-magnitude on the og-02 tick scale and are swept, never fitted.",
            f"{thermo['fit']['n_resolved']} of {len(skeletons)} skeletons resolve to a formula-verified KEGG compound "
            f"and carry the live eQuilibrator dG' (component contribution); the other {thermo['fit']['n_estimated']} "
            f"carry a group-additivity estimate fitted to those (leave-one-out RMSE {thermo['fit']['loo_rmse_kj_mol']:.1f} kJ/mol).",
            "Linear skeletons only: branched acids (citrate) and alkenes are outside the representation, so the "
            "full rTCA cannot close here; what the universe CAN contain is formose-type and reductive-carboxylation chemistry.",
            "N/P-bearing rules deliberately excluded pending the expert's rule-set-scope decision.",
        ],
    }
    path = Path(path) if path else package_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# vg-data package: the Phase-3 REACTION UNIVERSE (generated — do not hand-edit values;\n")
        fh.write("# regenerate with `python -m viva_genesis.protometabolism.universe`).\n")
        yaml.safe_dump(doc, fh, sort_keys=False, width=110, allow_unicode=True)
    return doc


if __name__ == "__main__":   # pragma: no cover
    import sys
    doc = build_package(progress=lambda m: print(m, file=sys.stderr))
    print(f"wrote {package_path()} ({doc['universe_summary']['n_reactions']} reactions)")


__all__ = [
    "UNIT_FORMULA", "CATALOG", "RULES", "Reaction", "Universe", "ThermoConditions",
    "canon", "species_id", "skeleton_of", "formula", "n_carbons", "common_name",
    "enumerate_skeletons", "generate_reactions", "element_matrix", "stoichiometric_matrix",
    "build_thermo_table", "reaction_dg0", "build_universe", "null_network", "to_antimony",
    "catalyst_substrates", "catalyst_factors",
    "DEFAULT_KINETICS", "FEED_SPECIES", "load_thermo_table", "load_package_dict", "kinetics_from_package",
    "CO2", "H2", "H2O", "TAR", "PACKAGE_PARAMETERS", "build_package", "package_path",
]
