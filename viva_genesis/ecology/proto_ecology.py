"""Phase 8 — biochemical ecology: real reaction networks per protocell on the
Phase-4 fields, coupled by matter exchange (Model Upgrade plan, Phase 8).

og-07's ``CrossFeedingMetacommunityProcess`` spreads *capabilities* between
compartments symbolically (a neighbour that has a function "supplies the
byproduct"). This module replaces the symbol with the chemistry:

* :class:`ProtocellNetworkProcess` — the ``reaction_universe`` class on the
  ``proto_ecology`` face. Every agent carries the **Phase-3 rule-generated
  C/H/O universe** (``viva_genesis.protometabolism.universe``: 413 reversible
  reactions with eQuilibrator ΔG′, catalyst-site saturation, degradation)
  integrated by its own real libRoadRunner instance — but *masked* to the
  agent's **lineage repertoire**, the subset of reaction rules its catalysts
  carry (``REPERTOIRES``: a ``fixer`` carries the carboxylation / CO2-reduction
  rules, a ``reducer`` the hydrogenation rules, a ``condenser`` the aldol /
  formose rules, a ``generalist`` everything; the uncatalysed decarboxylations
  belong to all). The rule mask is a set of SBML parameters, so every agent
  shares one JIT-compiled model and differs only in which rules it can run.
  The process reads the agent's dissolved pool from the bigraph, advances the
  chemistry over the tick, writes the concentration deltas back, and publishes
  which product classes it **produced** itself this tick (internal net
  production, not presence) together with the Phase-3 witnesses (element
  residual, dissipation, carbon degraded to tar).
* :class:`ProtocellNullNetworkProcess` — the ``null_network`` class: the same
  machinery on the Phase-3 matched null (rewired chemistry), the adversarial
  control for the community-function gate.
* :class:`SpatialCouplingStep` — points every agent at a cell of the pore
  field (positions from the ``lineages`` map; **no motion this phase**, the
  recorded decision), shapes each cell's background from the feed and the
  Phase-4 localization class's per-species ``enrichment`` (the Soret profile
  along the pore), and fires the exchange rules of
  :class:`~viva_genesis.ecology.reactive_system.BigraphicalReactiveSystem`
  (uptake / secretion through a species-specific permeability, pore
  diffusion between cells, the pore's feed / washout). Publishes the firing
  counts and the **cross-lineage flux** of every species (moles secreted by
  one lineage and taken up by another in the same tick — the real-metabolite
  witness of the gate).
* :class:`EcologyReducerStep` — recomputes og-07's gate readouts
  (``metacommunity_robustness``, ``isolated_robustness``, ``robustness_gain``,
  ``capability_diversity``, ``luca_capability_overlap``, ``mean_capability``)
  **from the agents map**: a capability is now a product class
  (``FUNCTIONS``: chain length × carboxylation × oxidation state, derived from
  the universe's skeletons), *present* when the agent holds it above the
  floor and *intrinsic* when the agent's own network produced it this tick;
  the isolated counterfactual is therefore the intrinsic matrix and the gain
  is what real flux delivered. It also publishes the community union and each
  agent's completeness relative to it, the quantities the Phase-8 gate reads.
"""

from __future__ import annotations

import math

import numpy as np
from process_bigraph import Process, Step

from ..protometabolism import universe as U
from ..protometabolism.universe_process import _kin_schema

_MOLAR = {"_type": "float", "_units": "molar"}
_OW_MOLAR = {"_type": "overwrite[float]", "_units": "molar"}
_OW_DIMLESS = {"_type": "overwrite[float]", "_units": "dimensionless"}
_OW_MOLS = {"_type": "overwrite[float]", "_units": "mole/second"}
_OW_MOL = {"_type": "overwrite[float]", "_units": "mole"}
_OW_W = {"_type": "overwrite[float]", "_units": "watt"}

# --------------------------------------------------------------------------- #
# Lineage repertoires: which reaction RULES an agent's catalysts carry.
# --------------------------------------------------------------------------- #
# The uncatalysed (thermal) decarboxylations belong to every lineage; the
# catalysed rules are partitioned by catalyst chemistry. A lineage is a set of
# rule names; the universe's reactions keep their rule label, so a mask is a
# vector of 0/1 multipliers on the rules' rate constants.
FREE_RULES = frozenset({"decarboxylate_alpha", "decarboxylate_beta"})
REPERTOIRES: dict[str, frozenset] = {
    "fixer": frozenset({"co2_reduction", "carboxylate_alpha", "carboxylate_reductive"}) | FREE_RULES,
    "reducer": frozenset({"reduce_carbonyl", "reduce_carboxyl", "deoxygenate"}) | FREE_RULES,
    "condenser": frozenset({"aldol", "formose_initiation", "isomerize", "cannizzaro"}) | FREE_RULES,
    "generalist": frozenset(U.RULES),
}

# Extra field species the C/H/O universe does not transform but the community
# takes up and the ledger conserves (the N and P budgets of cnp_resources).
EXTRA_SPECIES: dict[str, dict[str, int]] = {"ammonium": {"N": 1}, "phosphate": {"P": 1}}
# canonical dissolved names -> universe ids (the Phase-4 enrichment map keys)
CANONICAL_TO_UNIVERSE = {"formate": "X_A", "acetate": "X_AM", "pyruvate": "X_AKM", "formaldehyde": "X_D",
                         "CO2": U.CO2, "H2": U.H2, "ammonium": "ammonium", "phosphate": "phosphate"}
PERMEABILITY_CLASSES = ("p_gas", "p_small_neutral", "p_large_neutral", "p_monoacid", "p_diacid", "p_ion")
DEFAULT_PERMEABILITY = {"p_gas": 1.0e-5, "p_small_neutral": 1.0e-7, "p_large_neutral": 3.0e-8,
                        "p_monoacid": 1.0e-9, "p_diacid": 1.0e-10, "p_ion": 1.0e-10}
_PERM_PROVENANCE = {"p_gas": "extrapolated", "p_small_neutral": "extrapolated", "p_large_neutral": "extrapolated",
                    "p_monoacid": "extrapolated", "p_diacid": "hypothetical", "p_ion": "extrapolated"}


def permeability_class(sid: str) -> str:
    """Which permeability class a species falls in (size / charge rule)."""
    if sid in (U.CO2, U.H2):
        return "p_gas"
    if sid in EXTRA_SPECIES:
        return "p_ion"
    skel = U.skeleton_of(sid)
    if skel is None:
        return "p_ion"
    n_acid = sum(1 for u in skel if u == "A")
    if n_acid >= 2:
        return "p_diacid"
    if n_acid == 1:
        return "p_monoacid"
    return "p_small_neutral" if len(skel) <= 2 else "p_large_neutral"


# --------------------------------------------------------------------------- #
# Functions: product classes derived from the skeletons
# --------------------------------------------------------------------------- #
def function_of(sid: str) -> str | None:
    """The product class of an organic species: chain length x carboxylation
    (nonacid / monoacid / diacid) x oxidation state of the non-acid carbons
    (oxo / hydroxy / reduced); C1 species by name. ``None`` for currency
    species (CO2, H2, H2O, tar) and the extra inorganic solutes."""
    skel = U.skeleton_of(sid)
    if skel is None or skel == ("Q",):
        return None
    n = len(skel)
    if n == 1:
        return {"A": "c1_formate", "D": "c1_formaldehyde", "H": "c1_methanol"}[skel[0]]
    a = skel.count("A")
    rest = [u for u in skel if u != "A"]
    desc = ("oxo" if any(u in ("K", "D") for u in rest)
            else "hydroxy" if any(u in ("O", "H") for u in rest) else "reduced")
    acid = "diacid" if a >= 2 else ("monoacid" if a == 1 else "nonacid")
    return f"c{n}_{acid}_{desc}"


def function_names(max_carbons: int = 4) -> list[str]:
    """The function vocabulary of a universe (sorted)."""
    names = set()
    for skel in U.enumerate_skeletons(max_carbons):
        f = function_of(U.species_id(skel))
        if f:
            names.add(f)
    return sorted(names)


FUNCTIONS = tuple(function_names(4))

# og-07's anaerobic LUCA core, read off the chemistry: which agent-level
# witnesses realise each capability. ion_pumping has no counterpart in a
# C/H/O network and is reported as unreachable (the overlap's ceiling is 0.8).
LUCA_CORE = ("h2_oxidation", "co2_fixation", "fes_catalysis", "acetyl_coa", "ion_pumping")
MINERAL_RULES = frozenset(r for r, (cat, _) in U.RULES.items() if cat == "mineral")


def field_species(max_carbons: int = 4) -> list[str]:
    """Every species a field cell / agent pool carries (the universe's floating
    species plus the extra inorganic solutes) — pre-populated at build so the
    typed maps accept additive deltas on every key."""
    out = [U.CO2, U.H2] + [U.species_id(s) for s in U.enumerate_skeletons(max_carbons) if s != ("Q",)]
    return out + list(EXTRA_SPECIES)


def species_elements(max_carbons: int = 4) -> dict[str, dict[str, int]]:
    """Element counts (C, N, P) per field species: the universe's formulas plus the extras."""
    out = {}
    for skel in U.enumerate_skeletons(max_carbons):
        sid = U.species_id(skel)
        f = U.formula(skel)
        out[sid] = {"C": f["C"], "N": 0, "P": 0}
    out[U.H2] = {"C": 0, "N": 0, "P": 0}
    for s, e in EXTRA_SPECIES.items():
        out[s] = {"C": e.get("C", 0), "N": e.get("N", 0), "P": e.get("P", 0)}
    return out


# --------------------------------------------------------------------------- #
# The protocell model: the universe closed inside a membrane, rules masked
# --------------------------------------------------------------------------- #
def protocell_antimony(u: U.Universe, kin: dict | None = None) -> str:
    """Emit the universe as a CLOSED protocell reactor: internal reactions with
    per-rule mask parameters ``m_<rule>`` (0/1 — the lineage repertoire),
    catalyst-pool crowding factors, degradation to tar, and the carbon
    integrators ``Cfix`` / ``Cdeg``. No feed, no washout: exchange with the
    outside is the reactive system's job (operator splitting per tick)."""
    kin = {**U.DEFAULT_KINETICS, **(kin or {})}
    RT = U.R_KJ * u.conditions.temperature_K
    organics = u.organics()
    floating = [s for s in u.species if s != U.H2O]
    lines = ["model protocell()", "  species " + ", ".join(floating + [U.TAR]) + ";",
             f"  species ${U.H2O};", "  species Cfix, Cdeg;"]
    for k, v in kin.items():
        lines.append(f"  {k} = {v!r};")
    for rule in U.RULES:
        lines.append(f"  m_{rule} = 1.0;")
    for cls in ("mineral", "base"):
        lines.append(f"  f_{cls} = {kin['sites_' + cls]!r};")
    fix_terms = []
    for r in u.reactions:
        lhs = " + ".join(f"{n} {s}" if n > 1 else s for s, n in r.reactants.items())
        rhs = " + ".join(f"{n} {s}" if n > 1 else s for s, n in r.products.items())
        fwd = "*".join(f"{s}^{n}" if n > 1 else s for s, n in r.reactants.items() if s != U.H2O) or "1"
        rev = "*".join(f"{s}^{n}" if n > 1 else s for s, n in r.products.items() if s != U.H2O) or "1"
        x = r.dg0 / RT
        if x <= 0.0:
            f_fac, r_fac = 1.0, math.exp(max(x, -700.0))
        else:
            f_fac, r_fac = math.exp(-min(x, 700.0)), 1.0
        cat = f"f_{r.catalyst}*" if r.catalyst in ("mineral", "base") else ""
        lines.append(f"  {r.id}: {lhs} -> {rhs}; m_{r.rule}*{cat}{r.rate_param}*({f_fac!r}*{fwd} - {r_fac!r}*{rev});")
        nu = r.products.get(U.CO2, 0) - r.reactants.get(U.CO2, 0)
        if nu:
            fix_terms.append(f"({-nu})*{r.id}")
    deg_terms = []
    for sid in organics:
        skel = U.skeleton_of(sid)
        fac = kin["aldehyde_degradation_factor"] if "D" in skel else 1.0
        lines.append(f"  G_{sid}: {sid} -> {U.TAR}; {fac!r}*k_deg*{sid};")
        deg_terms.append(f"{U.n_carbons(sid)}*G_{sid}")
    lines.append("  Cfix' = " + (" + ".join(fix_terms) or "0") + ";")
    lines.append("  Cdeg' = " + (" + ".join(deg_terms) or "0") + ";")
    for sid in floating:
        lines.append(f"  {sid} = 0.0;")
    lines.append(f"  {U.TAR} = 0; {U.H2O} = 1; Cfix = 0; Cdeg = 0;")
    lines.append("end")
    return "\n".join(lines)


# one compiled model per (universe, kinetics) per worker process; every agent
# instantiates its own RoadRunner from the cached SBML (roadrunner caches the
# JIT by SBML hash, so the N-th agent costs ~0.1 s, not ~2 s).
_ENGINE_CACHE: dict = {}


def _engine_bundle(max_carbons: int, kin: dict, null_seed: int | None, thermo_source: str):
    key = (int(max_carbons), tuple(sorted((k, float(v)) for k, v in kin.items())), null_seed, thermo_source)
    if key in _ENGINE_CACHE:
        return _ENGINE_CACHE[key]
    import tellurium as te   # real libRoadRunner / Antimony bridge (lazy)
    thermo = None
    if thermo_source == "equilibrator":
        cond = U.ThermoConditions(**U.load_thermo_table()["conditions"])
        thermo = U.build_thermo_table(U.enumerate_skeletons(max_carbons), cond)
    u = U.build_universe(max_carbons, thermo=thermo)
    if null_seed is not None:
        u = U.null_network(u, null_seed)
    rr = te.loada(protocell_antimony(u, kin))
    floating = [s for s in u.species if s != U.H2O]
    rids = list(rr.getReactionIds())
    rid_to_r = {r.id: r for r in u.reactions}
    # net stoichiometry per species over the internal reactions, for the
    # per-tick "produced" witness and the H2 / CO2 flux sensors
    stoich: dict[str, list[tuple[int, float]]] = {}
    rule_of: list[str | None] = []
    for j, rid in enumerate(rids):
        r = rid_to_r.get(rid)
        rule_of.append(r.rule if r else None)
        if r is None:
            continue
        for s, n in r.products.items():
            stoich.setdefault(s, []).append((j, float(n)))
        for s, n in r.reactants.items():
            stoich.setdefault(s, []).append((j, -float(n)))
    # per-reaction forward / reverse kinetic terms (the Antimony rate law split in
    # two) so the per-tick GROSS production of a species can be computed: the
    # engine reports net rates, which vanish for an intermediate at steady state
    RT = U.R_KJ * u.conditions.temperature_K
    rxn_terms = []
    for r in u.reactions:
        x = r.dg0 / RT
        f_fac, r_fac = (1.0, math.exp(max(x, -700.0))) if x <= 0.0 else (math.exp(-min(x, 700.0)), 1.0)
        rxn_terms.append((r.rule, r.rate_param, r.catalyst, f_fac, r_fac,
                          tuple((sp, n) for sp, n in r.reactants.items() if sp != U.H2O),
                          tuple((sp, n) for sp, n in r.products.items() if sp != U.H2O),
                          tuple(r.reactants.items()), tuple(r.products.items())))
    bundle = {"universe": u, "sbml": rr.getSBML(), "floating": floating, "rids": rids, "rule_of": rule_of,
              "rxn_terms": rxn_terms,
              "stoich": stoich, "subs": U.catalyst_substrates(u),
              "element_residual": float(u.element_residual()["max_abs"]),
              "rt": U.R_KJ * u.conditions.temperature_K,
              "function_of": {s: function_of(s) for s in floating},
              "functions": tuple(function_names(max_carbons))}
    _ENGINE_CACHE[key] = bundle
    return bundle


class ProtocellNetworkProcess(Process):
    """The Phase-3 reaction universe inside ONE protocell, masked to a lineage
    repertoire, integrated by its own libRoadRunner instance each tick."""

    contract = {
        "summary": "A protocell's real reaction network: the Phase-3 rule-generated C/H/O universe (libRoadRunner) masked to the lineage's catalyst repertoire, closed inside the membrane; publishes what it produced itself.",
        "description": (
            "Reads the agent's dissolved pool from the agents map, loads it into the agent's own "
            "libRoadRunner model of the Phase-3 universe (413 reversible reactions, eQuilibrator dG', "
            "catalyst-site saturation, degradation to tar) with the lineage's rule mask applied as 0/1 "
            "rate multipliers, advances the chemistry over the tick with no exchange term (exchange is the "
            "SpatialCouplingStep's reactive system), and writes the concentration deltas back. Publishes "
            "the product classes the agent PRODUCED this tick (net internal production above the flux "
            "floor — not presence, which may come from uptake), the per-rule flux, the H2 consumption and "
            "CO2 fixation rates, the Phase-3 witnesses (exact element residual, dissipation, carbon "
            "degraded) and the agent's organic carbon."
        ),
        "inputs": {"internal": "the agent's dissolved pool (molar, keyed by universe species id)"},
        "outputs": {
            "internal": "concentration deltas after the tick's chemistry (molar)",
            "functions_produced": "product classes with gross internal production above flux_floor this tick (1/0)",
            "rule_flux": "sum of |v_r| over the reactions of each rule (molar/second)",
            "net_carbon_flux": "net CO2 fixed into organics (mole/second, per agent)",
            "h2_consumption": "net H2 consumed by internal reactions (mole/second)",
            "co2_fixation": "net CO2 consumed by internal reactions (mole/second)",
            "dissipation": "-sum_r v_r dG_r (watt, per agent; >= 0 for consistent kinetics)",
            "element_residual": "max |E S| over the agent's reactions (exact; 0 for the universe)",
            "carbon_degraded": "cumulative carbon lost to tar (mole)",
            "total_organic_carbon": "organic carbon inside the agent (molar C)",
            "n_persistent_species": "organic species above conc_floor",
            "catalyst_saturation": "1 - f_mineral / sites_mineral",
        },
        "assumptions": [
            "Operator splitting per tick: chemistry inside the agent, then exchange through the membrane (the reactive system).",
            "A lineage is a set of reaction rules its catalysts carry; uncatalysed decarboxylations belong to every lineage.",
            "The agent's volume is fixed this phase (no growth / division); positions are fixed (no motion).",
        ],
        "references": ["wolos2020synthetic", "beber2022equilibrator", "jordan2019promotion"],
    }

    config_schema = {
        "lineage": {"_type": "string", "_default": "generalist", "_provenance": "hypothetical"},
        "rules": {"_type": "string", "_default": "", "_provenance": "hypothetical"},
        "max_carbons": {"_type": "integer", "_default": 4, "_units": "dimensionless", "_provenance": "hypothetical"},
        **_kin_schema(),
        "null_seed": {"_type": "integer", "_default": -1, "_units": "dimensionless", "_provenance": "inferred"},
        "thermo_source": {"_type": "string", "_default": "package", "_provenance": "inferred"},
        "volume": {"_type": "float", "_default": 1.0e-18, "_units": "liter", "_provenance": "inferred"},
        "conc_floor": {"_type": "float", "_default": 1.0e-9, "_units": "molar", "_provenance": "inferred"},
        "flux_floor": {"_type": "float", "_default": 1.0e-12, "_units": "molar/second", "_provenance": "inferred"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._rr = None
        self._b = None
        self._kin = {k: float(self.config[k]) for k in U.DEFAULT_KINETICS}
        self._f = {"mineral": 1.0, "base": 1.0}
        self._cdeg_prev = 0.0
        self._conc: dict[str, float] = {}
        self._rates: dict[str, float] = {}

    # -- face ---------------------------------------------------------------
    def inputs(self):
        return {"internal": "map[vg_concentration]"}

    def outputs(self):
        return {
            "internal": "map[vg_concentration]",
            "functions_produced": "tree", "rule_flux": "tree",
            "net_carbon_flux": _OW_MOLS, "h2_consumption": _OW_MOLS, "co2_fixation": _OW_MOLS,
            "dissipation": _OW_W, "element_residual": _OW_DIMLESS, "carbon_degraded": _OW_MOL,
            "total_organic_carbon": _OW_MOLAR, "n_persistent_species": _OW_DIMLESS,
            "catalyst_saturation": _OW_DIMLESS,
        }

    def initial_state(self):
        return {"internal": {}}

    # -- repertoire ---------------------------------------------------------
    def repertoire(self) -> frozenset:
        explicit = str(self.config.get("rules", "") or "").strip()
        if explicit:
            rules = frozenset(r.strip() for r in explicit.split(",") if r.strip())
            unknown = rules - set(U.RULES)
            if unknown:
                raise KeyError(f"unknown reaction rules {sorted(unknown)}; have {sorted(U.RULES)}")
            return rules | FREE_RULES
        name = str(self.config.get("lineage", "generalist"))
        if name not in REPERTOIRES:
            raise KeyError(f"unknown lineage {name!r}; have {sorted(REPERTOIRES)}")
        return REPERTOIRES[name]

    def null_seed(self):
        return None

    def bundle(self) -> dict:
        if self._b is None:
            self._b = _engine_bundle(int(self.config["max_carbons"]), self._kin, self.null_seed(),
                                     str(self.config.get("thermo_source", "package")))
        return self._b

    def universe(self) -> U.Universe:
        return self.bundle()["universe"]

    def _engine(self):
        if self._rr is None:
            import roadrunner
            b = self.bundle()
            rr = roadrunner.RoadRunner(b["sbml"])
            mask = self.repertoire()
            for rule in U.RULES:
                rr[f"m_{rule}"] = 1.0 if rule in mask else 0.0
            self._rr = rr
        return self._rr

    # -- witnesses ------------------------------------------------------------
    def _dissipation(self, conc: dict[str, float], rates: dict[str, float]) -> float:
        b = self.bundle()
        floor = float(self.config["conc_floor"])
        total = 0.0
        for r in b["universe"].reactions:
            v = rates.get(r.id, 0.0)
            if v == 0.0:
                continue
            lnq = 0.0
            for s, n in r.products.items():
                if s != U.H2O:
                    lnq += n * math.log(max(conc.get(s, 0.0), floor))
            for s, n in r.reactants.items():
                if s != U.H2O:
                    lnq -= n * math.log(max(conc.get(s, 0.0), floor))
            total -= v * (r.dg0 + b["rt"] * lnq)
        return total

    def _gross_production(self, conc: dict[str, float]) -> dict[str, float]:
        """GROSS production rate per species (molar/s): the forward flux of every
        reaction making it plus the reverse flux of every reaction consuming it.
        The engine's net rates vanish for an intermediate at steady state although
        the agent makes it continuously; this is what "produced" means."""
        mask = self.repertoire()
        out: dict[str, float] = {}
        for rule, kp, cat, f_fac, r_fac, react, prod, react_all, prod_all in self.bundle()["rxn_terms"]:
            if rule not in mask:
                continue
            pre = self._kin[kp] * (self._f[cat] if cat in self._f else 1.0)
            fwd = pre * f_fac
            for sp, n in react:
                fwd *= conc.get(sp, 0.0) ** n
            rev = pre * r_fac
            for sp, n in prod:
                rev *= conc.get(sp, 0.0) ** n
            if fwd > 0.0:
                for sp, n in prod_all:
                    out[sp] = out.get(sp, 0.0) + n * fwd
            if rev > 0.0:
                for sp, n in react_all:
                    out[sp] = out.get(sp, 0.0) + n * rev
        return out

    def update(self, state, interval):
        rr = self._engine()
        b = self.bundle()
        internal = state.get("internal", {}) or {}
        floating = b["floating"]
        conc_in = {s: max(float(internal.get(s, 0.0)), 0.0) for s in floating}
        for s, c in conc_in.items():
            rr.setValue(f"[{s}]", c)
        self._f = U.catalyst_factors(b["subs"], conc_in, self._kin)
        rr.f_mineral = self._f["mineral"]
        rr.f_base = self._f["base"]
        dt = max(float(interval), 1e-6)
        cdeg0 = float(rr["Cdeg"])
        # the model has no explicit time dependence: integrate [0, dt] each tick
        # (an absolute-time restart makes CVODE's step underflow at large t)
        rr.simulate(0.0, dt, 2)
        conc = {s: float(rr.getValue(f"[{s}]")) for s in floating}
        rate_vec = np.asarray(rr.getReactionRates(), dtype=float)
        rates = dict(zip(b["rids"], (float(x) for x in rate_vec)))
        self._conc, self._rates = conc, rates
        vol = float(self.config["volume"])
        # net internal production per species (molar/s) -> produced functions
        floor_v = float(self.config["flux_floor"])
        # the full vocabulary every tick (the store is a deep-merged tree: a
        # function produced last tick but not this one must be cleared to 0)
        produced: dict[str, float] = {f: 0.0 for f in b["functions"]}
        gross = self._gross_production(conc)
        for s, g in gross.items():
            f = b["function_of"].get(s)
            if f is not None and g > floor_v:
                produced[f] = 1.0
        rule_flux: dict[str, float] = {r: 0.0 for r in U.RULES}
        for j, rule in enumerate(b["rule_of"]):
            if rule is not None:
                rule_flux[rule] = rule_flux.get(rule, 0.0) + abs(float(rate_vec[j]))
        h2_net = -sum(n * rate_vec[j] for j, n in b["stoich"].get(U.H2, []))
        co2_net = -sum(n * rate_vec[j] for j, n in b["stoich"].get(U.CO2, []))
        floor_c = float(self.config["conc_floor"])
        u = b["universe"]
        toc = float(sum(U.n_carbons(s) * conc.get(s, 0.0) for s in u.organics()))
        deltas = {s: conc[s] - float(internal.get(s, 0.0)) for s in floating}
        cdeg = float(rr["Cdeg"])
        return {
            "internal": deltas,
            "functions_produced": produced,
            "rule_flux": rule_flux,
            "net_carbon_flux": float(co2_net) * vol,
            "h2_consumption": float(h2_net) * vol,
            "co2_fixation": float(co2_net) * vol,
            "dissipation": self._dissipation(conc, rates) * 1.0e3 * vol,
            "element_residual": b["element_residual"],
            "carbon_degraded": cdeg * vol,
            "total_organic_carbon": toc,
            "n_persistent_species": float(sum(1 for s in u.organics() if conc.get(s, 0.0) > floor_c)),
            "catalyst_saturation": float(1.0 - self._f["mineral"] / max(self._kin["sites_mineral"], 1e-30)),
        }


class ProtocellNullNetworkProcess(ProtocellNetworkProcess):
    """The ``null_network`` class of the proto_ecology face: the Phase-3 matched
    null (degree-preserving, (C,O)-matched rewiring) inside each agent, with
    the same lineage masks — the adversarial control of the community-function
    gate (does rewired chemistry also 'divide labour'?)."""

    contract = {
        **ProtocellNetworkProcess.contract,
        "summary": "Matched null network inside each protocell: the Phase-3 rewired universe with the same lineage rule masks, on the same engine.",
        "references": ["maslov2002specificity", "wolos2020synthetic"],
    }

    def null_seed(self):
        seed = int(self.config.get("null_seed", -1))
        return seed if seed >= 0 else 0


# --------------------------------------------------------------------------- #
# Spatial coupling: agents on the Phase-4 field + the exchange rules
# --------------------------------------------------------------------------- #
def _cell_of(position, n_cells: int) -> int:
    try:
        x = float(position[0])
    except Exception:
        x = 0.0
    return int(min(max(x, 0.0) * n_cells, n_cells - 1))


class SpatialCouplingStep(Step):
    """Couple the agents onto the pore field and fire the exchange rules."""

    contract = {
        "summary": "Points each agent at a pore-field cell (fixed positions), shapes the cells' background from the Phase-4 enrichment, and fires the matter-exchange rules (uptake, secretion, diffusion, feed/washout) with firing counts.",
        "description": (
            "Every tick after the agents' chemistry: builds the reactive-system context from the agents map "
            "(interior pools, volumes, per-species membrane rate constants P A / V from the permeability "
            "classes), the field cells and each cell's background — the feed scaled by the localization class's "
            "per-species enrichment raised to the cell's fractional position along the pore (the Soret profile) — "
            "and applies the BigraphicalReactiveSystem's rules. Writes the exchange deltas back to the agents' "
            "pools and the cells, and publishes per-rule firing counts and moles, the cross-lineage flux of every "
            "species (moles secreted by one lineage and taken up by another this tick), the per-element inflow / "
            "outflow across the pore boundary (for the element ledger) and each agent's uptake / secretion."
        ),
        "inputs": {"agents": "agents map (vg_individual: volume, internal.dissolved)",
                   "lineages": "per-agent lineage id and position along the pore",
                   "field": "pore field cells (map of dissolved pools)",
                   "enrichment": "Phase-4 per-species enrichment at the trap end (dimensionless)",
                   "global_time": "tick clock (fires once per tick)"},
        "outputs": {"agents": "exchange deltas on internal.dissolved", "field": "exchange deltas on the cells",
                    "firings": "cumulative firing count per rule", "firing_moles": "cumulative |moles| per rule",
                    "cross_lineage_flux": "per species, moles moved between lineages this tick",
                    "cross_lineage_flux_total": "cumulative cross-lineage moles (all species)",
                    "inflow": "cumulative moles of C / N / P fed into the pore", "outflow": "cumulative moles washed out",
                    "exchange": "per-agent uptake / secretion this tick (moles) and lineage"},
        "assumptions": ["Agents do not move (Phase-8 decision: point agents on the fields first; motion deferred).",
                        "Exchange is linear permeation; the tick's transfer is the exact two-compartment relaxation."],
        "references": ["jordan2019promotion", "sojo2014bioenergetic", "mast2010thermal"],
    }

    config_schema = {
        "n_cells": {"_type": "integer", "_default": 4, "_units": "dimensionless", "_provenance": "hypothetical"},
        "cell_volume": {"_type": "float", "_default": 2.0e-17, "_units": "liter", "_provenance": "hypothetical"},
        "dt": {"_type": "float", "_default": 1.0, "_units": "second", "_provenance": "inferred"},
        "k_wash": {"_type": "float", "_default": 0.05, "_units": "1/second", "_provenance": "inferred"},
        "k_diffusion": {"_type": "float", "_default": 0.1, "_units": "1/second", "_provenance": "hypothetical"},
        "coupling": {"_type": "string", "_default": "shared", "_provenance": "inferred"},
        "area_per_volume": {"_type": "float", "_default": 4.84e6, "_units": "1/meter", "_provenance": "inferred"},
        **{p: {"_type": "float", "_default": DEFAULT_PERMEABILITY[p], "_units": "meter/second",
               "_provenance": _PERM_PROVENANCE[p]} for p in PERMEABILITY_CLASSES},
        "feed": {"_type": "tree", "_default": {}, "_provenance": "calibrated"},
        "max_carbons": {"_type": "integer", "_default": 4, "_units": "dimensionless", "_provenance": "hypothetical"},
        "flux_floor_moles": {"_type": "float", "_default": 1.0e-32, "_units": "mole", "_provenance": "inferred"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        from .reactive_system import BigraphicalReactiveSystem
        self.system = BigraphicalReactiveSystem()
        self._elements = species_elements(int(self.config["max_carbons"]))
        self._inflow = {"C": 0.0, "N": 0.0, "P": 0.0}
        self._outflow = {"C": 0.0, "N": 0.0, "P": 0.0}
        self._cross_total = 0.0
        self._last_time = None

    def inputs(self):
        return {"agents": "map[vg_individual]", "lineages": "map[vg_lineage]",
                "field": "map[map[vg_concentration]]", "enrichment": "tree", "global_time": "float"}

    def outputs(self):
        return {"agents": "map[vg_individual]", "field": "map[map[vg_concentration]]",
                "firings": "tree", "firing_moles": "tree", "cross_lineage_flux": "tree",
                "cross_lineage_flux_total": _OW_MOL, "inflow": "tree", "outflow": "tree", "exchange": "tree"}

    def perform_update(self, state) -> bool:
        t = state.get("global_time")
        if t == self._last_time:
            return False
        self._last_time = t
        return True

    def permeability_rates(self) -> dict[str, float]:
        """Per-species membrane rate constant k = P A / V (1/s)."""
        av = float(self.config["area_per_volume"])
        out = {}
        for s in self._elements:
            if s == U.H2O:
                continue
            out[s] = float(self.config[permeability_class(s)]) * av
        return out

    def background(self, enrichment: dict, n_cells: int) -> dict:
        """Per cell: feed x enrichment^(x) with x the cell's fractional position."""
        feed = dict(self.config.get("feed") or {})
        enr = {}
        for canon, sid in CANONICAL_TO_UNIVERSE.items():
            if canon in (enrichment or {}):
                enr[sid] = max(float(enrichment[canon]), 1e-30)
        bg = {}
        for i in range(n_cells):
            x = (i + 0.5) / n_cells
            bg[f"c{i}"] = {s: float(v) * (enr.get(s, 1.0) ** x) for s, v in feed.items()}
        return bg

    def update(self, state):
        from .reactive_system import RuleContext
        n_cells = int(self.config["n_cells"])
        agents_in = state.get("agents", {}) or {}
        lineages = state.get("lineages", {}) or {}
        field_in = state.get("field", {}) or {}
        k = self.permeability_rates()
        private = str(self.config.get("coupling", "shared")) == "private"
        cells = {f"c{i}": dict(field_in.get(f"c{i}", {}) or {}) for i in range(n_cells)}
        bg = self.background(state.get("enrichment", {}) or {}, n_cells)
        agents = {}
        for aid, a in agents_in.items():
            lin = lineages.get(aid, {}) or {}
            internal = dict((a.get("internal") or {}).get("dissolved") or {})
            agents[aid] = {"volume": float(a.get("volume", 1.0e-18)), "cell": f"c{_cell_of(lin.get('position', (0.0, 0.0)), n_cells)}",
                           "internal": internal, "k": k, "lineage": str(lin.get("lineage_id", "?"))}
        before = {aid: dict(a["internal"]) for aid, a in agents.items()}
        cells_before = {ck: dict(c) for ck, c in cells.items()}
        nbrs = {f"c{i}": [f"c{j}" for j in (i - 1, i + 1) if 0 <= j < n_cells] for i in range(n_cells)}
        ctx = RuleContext(agents=agents, cells=cells, cell_volume=float(self.config["cell_volume"]), background=bg,
                          elements=self._elements, dt=float(self.config["dt"]), k_diffusion=float(self.config["k_diffusion"]),
                          k_wash=float(self.config["k_wash"]), private=private, neighbours=nbrs)
        self.system.fire(ctx)
        for el in self._inflow:
            self._inflow[el] += ctx.inflow[el]
            self._outflow[el] += ctx.outflow[el]
        # per-agent uptake / secretion and the cross-lineage flux witness
        secreted: dict[str, dict[str, float]] = {}
        taken: dict[str, dict[str, float]] = {}
        exchange = {}
        mfloor = float(self.config["flux_floor_moles"])
        for aid, a in agents.items():
            up, sec = {}, {}
            for s, c in a["internal"].items():
                d = (c - before[aid].get(s, 0.0)) * a["volume"]
                if d > mfloor:
                    up[s] = d
                elif d < -mfloor:
                    sec[s] = -d
            exchange[aid] = {"lineage": a["lineage"], "uptake": up, "secretion": sec}
            secreted.setdefault(a["lineage"], {})
            taken.setdefault(a["lineage"], {})
            for s, v in sec.items():
                secreted[a["lineage"]][s] = secreted[a["lineage"]].get(s, 0.0) + v
            for s, v in up.items():
                taken[a["lineage"]][s] = taken[a["lineage"]].get(s, 0.0) + v
        # every species every tick (the store is a deep-merged tree: a species
        # exchanged last tick but not this one must read 0, not stale)
        cross: dict[str, float] = {s: 0.0 for s in self._elements if s != U.H2O}
        if not private:
            # the moles of a species one lineage secreted into the shared field
            # and another lineage took up from it in the same tick (an upper
            # bound on the transfer, exact when the field carries it straight
            # across); zero by construction when nothing is shared
            for lx, sx in secreted.items():
                for ly, ty in taken.items():
                    if lx == ly:
                        continue
                    for s, v in sx.items():
                        if s in ty:
                            cross[s] = cross.get(s, 0.0) + min(v, ty[s])
        self._cross_total += sum(cross.values())
        agent_deltas = {aid: {"internal": {"dissolved": {s: a["internal"][s] - before[aid].get(s, 0.0)
                                                          for s in a["internal"] if a["internal"][s] != before[aid].get(s, 0.0)}}}
                        for aid, a in agents.items()}
        field_deltas = {ck: {s: c[s] - cells_before[ck].get(s, 0.0) for s in c if c[s] != cells_before[ck].get(s, 0.0)}
                        for ck, c in cells.items()}
        return {
            "agents": agent_deltas, "field": field_deltas,
            "firings": {r: float(v) for r, v in self.system.counts.items()},
            "firing_moles": dict(self.system.moles),
            "cross_lineage_flux": cross, "cross_lineage_flux_total": self._cross_total,
            "inflow": dict(self._inflow), "outflow": dict(self._outflow), "exchange": exchange,
        }


# --------------------------------------------------------------------------- #
# Reducer: og-07's gate readouts from the agents map
# --------------------------------------------------------------------------- #
class EcologyReducerStep(Step):
    """Recompute og-07's gate readouts from the agents map, with capabilities
    = product classes, present = held above the floor, intrinsic = produced by
    the agent's own network this tick."""

    contract = {
        "summary": "og-07's gate readouts (metacommunity_robustness, isolated_robustness, robustness_gain, capability_diversity, luca_capability_overlap, mean_capability) recomputed from real agents; plus the community union and each cell's completeness.",
        "description": (
            "Capabilities are the universe's product classes (chain length x carboxylation x oxidation state). An "
            "agent HOLDS a function when some species of that class sits above function_floor in its pool; it "
            "PRODUCES it when its own network's net internal production of such a species exceeded the flux "
            "floor this tick (published by the ProtocellNetworkProcess). metacommunity_robustness = fraction of "
            "functions held by >= redundancy_target agents; isolated_robustness = the same on the produced "
            "(intrinsic) matrix — og-07's no-exchange counterfactual, now within the run; robustness_gain = their "
            "difference, i.e. what real metabolite flux delivered. capability_diversity = mean fraction of the "
            "vocabulary each agent holds; mean_capability = mean completeness of an agent relative to the community "
            "UNION (the 'cell completeness' of the Phase-8 gate); luca_capability_overlap reads og-07's anaerobic "
            "LUCA core off the chemistry (H2 consumed, CO2 fixed, mineral-class flux, acetate held; ion pumping "
            "unreachable in a C/H/O network)."
        ),
        "inputs": {"agents": "agents map", "lineages": "lineage ids", "metabolism": "per-agent produced functions + rule fluxes",
                   "rates": "per-agent H2 consumption / CO2 fixation rates", "global_time": "tick clock"},
        "outputs": {
            "metacommunity_robustness": "fraction of functions held by >= R agents",
            "isolated_robustness": "fraction of functions PRODUCED by >= R agents (intrinsic)",
            "robustness_gain": "held minus produced robustness (what flux delivered)",
            "capability_diversity": "mean fraction of the function vocabulary an agent holds",
            "mean_capability": "mean completeness of an agent relative to the community union",
            "luca_capability_overlap": "fraction of og-07's LUCA core realised by the community",
            "n_functions_union": "functions held somewhere in the community",
            "n_functions_produced_union": "functions produced by some agent",
            "n_functions_acquired": "mean per-agent functions held but not produced",
            "max_cell_completeness": "max over agents of |held| / |union|",
            "functions_union": "per function: max concentration, the lineages holding it and the lineages producing it",
            "functions_by_lineage": "per lineage: held and produced function sets (1/0)",
        },
        "assumptions": ["Presence is graded on a concentration floor (function_floor); production on a flux floor."],
        "references": ["weiss2016physiology", "moody2024nature"],
    }

    config_schema = {
        "function_floor": {"_type": "float", "_default": 1.0e-9, "_units": "molar", "_provenance": "inferred"},
        "flux_floor": {"_type": "float", "_default": 1.0e-30, "_units": "mole/second", "_provenance": "inferred"},
        "redundancy_target": {"_type": "integer", "_default": 2, "_units": "dimensionless", "_provenance": "inferred"},
        "max_carbons": {"_type": "integer", "_default": 4, "_units": "dimensionless", "_provenance": "hypothetical"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._functions = tuple(function_names(int(self.config["max_carbons"])))
        self._fn_of: dict[str, str | None] = {}
        self._last_time = None

    def inputs(self):
        return {"agents": "map[vg_individual]", "lineages": "map[vg_lineage]", "metabolism": "tree",
                "rates": "map[map[float]]", "global_time": "float"}

    def outputs(self):
        return {k: _OW_DIMLESS for k in ("metacommunity_robustness", "isolated_robustness", "robustness_gain",
                                         "capability_diversity", "mean_capability", "luca_capability_overlap",
                                         "n_functions_union", "n_functions_produced_union", "n_functions_acquired",
                                         "max_cell_completeness")} | {"functions_union": "tree", "functions_by_lineage": "tree"}

    def perform_update(self, state) -> bool:
        t = state.get("global_time")
        if t == self._last_time:
            return False
        self._last_time = t
        return True

    def _function(self, sid: str):
        if sid not in self._fn_of:
            self._fn_of[sid] = function_of(sid)
        return self._fn_of[sid]

    def update(self, state):
        agents = state.get("agents", {}) or {}
        lineages = state.get("lineages", {}) or {}
        metab = state.get("metabolism", {}) or {}
        rates = state.get("rates", {}) or {}
        floor = float(self.config["function_floor"])
        r_target = int(self.config["redundancy_target"])
        vocab = self._functions
        held: dict[str, set] = {}
        produced: dict[str, set] = {}
        conc_max: dict[str, float] = {}
        lineage_of = {}
        for aid, a in agents.items():
            lineage_of[aid] = str((lineages.get(aid) or {}).get("lineage_id", "?"))
            h = set()
            for s, c in ((a.get("internal") or {}).get("dissolved") or {}).items():
                f = self._function(s)
                if f and float(c) >= floor:
                    h.add(f)
                    conc_max[f] = max(conc_max.get(f, 0.0), float(c))
            produced[aid] = {f for f, v in ((metab.get(aid) or {}).get("functions_produced") or {}).items() if float(v) > 0}
            # an agent HOLDS a function when it carries the product above the
            # floor or makes it itself this tick (og-07: intrinsic is always held)
            held[aid] = h | produced[aid]
        n = max(len(agents), 1)
        union = set().union(*held.values()) if held else set()
        prod_union = set().union(*produced.values()) if produced else set()
        cov_h = {f: sum(1 for h in held.values() if f in h) for f in vocab}
        cov_p = {f: sum(1 for p in produced.values() if f in p) for f in vocab}
        rob = float(np.mean([1.0 if cov_h[f] >= r_target else 0.0 for f in vocab])) if vocab else 0.0
        iso = float(np.mean([1.0 if cov_p[f] >= r_target else 0.0 for f in vocab])) if vocab else 0.0
        diversity = float(np.mean([len(h) / len(vocab) for h in held.values()])) if held and vocab else 0.0
        completeness = [len(h & union) / len(union) if union else 0.0 for h in held.values()]
        acquired = float(np.mean([len(held[a] - produced[a]) for a in held])) if held else 0.0
        # LUCA core off the chemistry
        fl = float(self.config["flux_floor"])
        h2 = any(float((rates.get(a) or {}).get("h2_consumption", 0.0)) > fl for a in agents)
        co2 = any(float((rates.get(a) or {}).get("co2_fixation", 0.0)) > fl for a in agents)
        fes = any(sum(float(v) for r, v in ((metab.get(a) or {}).get("rule_flux") or {}).items() if r in MINERAL_RULES) > fl
                  for a in agents)
        acetyl = "c2_monoacid_reduced" in union
        luca = {"h2_oxidation": h2, "co2_fixation": co2, "fes_catalysis": fes, "acetyl_coa": acetyl, "ion_pumping": False}
        by_lineage: dict[str, dict] = {}
        for aid in agents:
            d = by_lineage.setdefault(lineage_of[aid], {"held": {}, "produced": {}})
            for f in held[aid]:
                d["held"][f] = 1.0
            for f in produced[aid]:
                d["produced"][f] = 1.0
        fu = {f: {"max_conc": conc_max.get(f, 0.0),
                  "held_by": sorted({lineage_of[a] for a in agents if f in held[a]}),
                  "produced_by": sorted({lineage_of[a] for a in agents if f in produced[a]})} for f in sorted(union)}
        return {
            "metacommunity_robustness": rob, "isolated_robustness": iso, "robustness_gain": rob - iso,
            "capability_diversity": diversity,
            "mean_capability": float(np.mean(completeness)) if completeness else 0.0,
            "luca_capability_overlap": float(sum(luca.values()) / len(LUCA_CORE)),
            "n_functions_union": float(len(union)), "n_functions_produced_union": float(len(prod_union)),
            "n_functions_acquired": acquired,
            "max_cell_completeness": float(max(completeness)) if completeness else 0.0,
            "functions_union": fu, "functions_by_lineage": by_lineage,
        }


__all__ = ["REPERTOIRES", "FREE_RULES", "FUNCTIONS", "LUCA_CORE", "EXTRA_SPECIES", "CANONICAL_TO_UNIVERSE",
           "PERMEABILITY_CLASSES", "DEFAULT_PERMEABILITY", "permeability_class", "function_of", "function_names",
           "field_species", "species_elements", "protocell_antimony", "ProtocellNetworkProcess", "ProtocellNullNetworkProcess",
           "SpatialCouplingStep", "EcologyReducerStep"]
