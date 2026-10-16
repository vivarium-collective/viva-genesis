"""The ``reaction_universe`` and ``null_network`` classes of the proto_metabolism face.

Both are genuine libRoadRunner bridges, exactly like og-02's
``RoadRunnerNetworkProcess`` (the ``curated_rtca`` class): the generated
network (``viva_genesis.protometabolism.universe``) is emitted as Antimony,
compiled by libRoadRunner, and advanced each tick as a continuous-feed /
washout reactor. What differs is where the chemistry comes from:

* ``ReactionUniverseProcess`` — the rule-generated universe (C1–C3 feedstock,
  products capped at ``max_carbons``), reversible thermodynamically consistent
  kinetics from the vg-data ``reaction_universe`` package (eQuilibrator ΔG'),
  side reactions, degradation to tar, and catalyst-site saturation.
* ``NullNetworkProcess`` — the same machinery on a matched null
  (``universe.null_network``): same compounds, reaction count, arity, catalyst
  density, carbon balance; rewired topology. ``null_seed`` selects the draw.

Every tick both publish the og-02 face observables (``net_carbon_flux``,
``autocatalytic_gain``, ``network_connected``) computed *post hoc* by the
class-agnostic detector in ``viva_genesis.protometabolism.motifs``, plus the
numerical-verification witnesses the Phase-3 ledger audits: the stoichiometric
element residual (exact), the integrated carbon-balance residual (integrator
tolerance) and the free-energy dissipation ``-Σ v_r ΔG_r`` (≥ 0 for consistent
kinetics — the second-law witness).
"""

from __future__ import annotations

import math

import numpy as np
from process_bigraph import Process

from . import universe as U
from . import motifs as M

_MOLAR = {"_type": "float", "_units": "molar"}
_OW_MOLAR = {"_type": "overwrite[float]", "_units": "molar"}
_OW_DIMLESS = {"_type": "overwrite[float]", "_units": "dimensionless"}
_OW_MOLS = {"_type": "overwrite[float]", "_units": "mole/second"}
_OW_W = {"_type": "overwrite[float]", "_units": "watt"}

# face species outputs -> universe species ids
SPECIES_PORTS = {
    "formate": "X_A", "formaldehyde": "X_D", "acetate": "X_AM", "glycolaldehyde": "X_DH",
    "pyruvate": "X_AKM", "OAA": "X_ACKA", "malate": "X_ACOA", "succinate": "X_ACCA",
}
CURRENCY = {U.CO2, U.H2, U.H2O, U.TAR}


def _kin_schema() -> dict:
    prov = {
        "k_co2_reduction": "extrapolated", "k_reduce": "hypothetical", "k_reduce_carboxyl": "hypothetical",
        "k_deoxygenate": "hypothetical", "k_carboxylate": "extrapolated", "k_carboxylate_reductive": "hypothetical",
        "k_aldol": "extrapolated", "k_formose_init": "extrapolated", "k_isomerize": "extrapolated",
        "k_decarboxylate": "extrapolated",
        "k_cannizzaro": "hypothetical", "sites_mineral": "hypothetical", "sites_base": "hypothetical",
        "K_sat": "hypothetical", "k_deg": "extrapolated", "aldehyde_degradation_factor": "hypothetical",
        "k_wash": "inferred", "k_feed": "inferred",
    }
    units = {"k_co2_reduction": "1/molar/second", "k_reduce": "1/molar/second", "k_reduce_carboxyl": "1/second",
             "k_deoxygenate": "1/molar/second", "k_carboxylate": "1/molar/second",
             "k_carboxylate_reductive": "1/second", "k_aldol": "1/molar/second",
             "k_formose_init": "1/molar/second", "k_isomerize": "1/second", "k_decarboxylate": "1/second", "k_cannizzaro": "1/molar/second",
             "sites_mineral": "dimensionless", "sites_base": "dimensionless", "K_sat": "molar",
             "k_deg": "1/second", "aldehyde_degradation_factor": "dimensionless",
             "k_wash": "1/second", "k_feed": "1/second"}
    return {k: {"_type": "float", "_default": float(v), "_units": units[k], "_provenance": prov[k]}
            for k, v in U.DEFAULT_KINETICS.items()}


class ReactionUniverseProcess(Process):
    """Rule-generated open C/H/O reaction universe integrated by the real
    libRoadRunner engine; motifs detected post hoc, never declared."""

    contract = {
        "summary": "Rule-generated C1-C3 reaction universe (Wolos-2020-style rules, eQuilibrator dG', catalyst limits) as a libRoadRunner CSTR; autocatalysis detected post hoc.",
        "description": (
            "Every linear C/H/O skeleton up to max_carbons is enumerated and nine prebiotic "
            "reaction rules (H2 reductions, enol and reductive carboxylation, aldol/retro-aldol, "
            "aldose-ketose isomerisation, alpha/beta decarboxylation, Cannizzaro) are applied "
            "exhaustively; each generated reaction is reversible with k_r = k_f exp(dG'/RT) from "
            "the vg-data reaction_universe potentials (eQuilibrator component contribution), "
            "carries a catalyst class whose shared site pool saturates with organic load, and "
            "every species degrades to tar and washes out. The SBML is compiled and advanced each "
            "tick by libRoadRunner under vent-buffered CO2/H2 and CSTR organic feeds. Emits the "
            "og-02 face observables computed post hoc by a class-agnostic detector (flux-carrying "
            "simple cycles with stoichiometric gain > 1), plus the element residual (exact), the "
            "integrated carbon-balance residual and the free-energy dissipation."
        ),
        "inputs": {
            "feed_CO2": "vent-buffered CO2 set-point (molar)",
            "feed_H2": "vent-buffered H2 set-point (molar)",
            "feed_pyruvate": "pyruvate CSTR inflow concentration (molar)",
            "feed_formaldehyde": "formaldehyde CSTR inflow concentration (molar)",
            "feed_formate": "formate CSTR inflow concentration (molar)",
            "feed_acetate": "acetate CSTR inflow concentration (molar)",
        },
        "outputs": {
            "net_carbon_flux": "net CO2 fixed into organics by internal reactions (mole/second)",
            "autocatalytic_gain": "max over detected motifs of seed production via the cycle / seed loss (dimensionless)",
            "network_connected": "1 if the alive organic species form one flux-connected network (currency species excluded)",
            "total_organic_carbon": "sum of carbon atoms in organic species (molar C)",
            "n_persistent_species": "organic species above conc_floor",
            "n_autocatalytic_motifs": "distinct flux-carrying simple cycles with stoichiometric gain > 1",
            "autocatalytic_core_size": "species participating in >= 1 detected motif",
            "dissipation": "-sum_r v_r dG_r over internal reactions (watt; >= 0 for consistent kinetics)",
            "element_residual": "max |E S| over internal reactions (exact; 0 for a generated universe)",
            "carbon_residual": "|TOC - TOC0 - (fed + fixed - washed - degraded)| / TOC (integrator tolerance)",
            "catalyst_saturation": "fraction of mineral sites occupied, 1 - f_mineral / sites_mineral",
            "formate": "formate (molar)", "formaldehyde": "formaldehyde (molar)", "acetate": "acetate (molar)",
            "glycolaldehyde": "glycolaldehyde (molar)", "pyruvate": "pyruvate (molar)",
            "OAA": "oxaloacetate (molar)", "malate": "malate (molar)", "succinate": "succinate (molar)",
        },
        "math": ["v_r = f_cat k0 (F prod[reactants] - R prod[products]),  (F, R) = (1, e^{dG'/RT}) if dG' <= 0 else (e^{-dG'/RT}, 1)",
                 "f_cat = sites / (1 + load / K_sat)", "sigma = -sum_r v_r (dG'_r + RT ln Q_r) >= 0",
                 "gain(cycle) = prod_i nu_product,i / nu_reactant,i > 1"],
        "assumptions": [
            "Linear carbon skeletons only (no branched acids such as citrate, no alkenes) — rTCA cannot close in this representation; that is a declared v1 limitation.",
            "dG' potentials at the package's pH / ionic strength / temperature (the Phase-1 posterior example point); water activity 1.",
            "Catalyst crowding factors are updated once per tick from the current organic load (operator splitting).",
        ],
        "references": ["wolos2020synthetic", "blokhuis2020universal", "beber2022equilibrator",
                       "noor2013consistent", "breslow1959mechanism", "muchowska2019synthesis"],
    }

    config_schema = {
        "max_carbons": {"_type": "integer", "_default": 4, "_provenance": "hypothetical",
                        "_units": "dimensionless"},
        **_kin_schema(),
        "null_seed": {"_type": "integer", "_default": -1, "_units": "dimensionless", "_provenance": "inferred"},
        "motif_every": {"_type": "integer", "_default": 10, "_units": "dimensionless", "_provenance": "inferred"},
        "conc_floor": {"_type": "float", "_default": 1.0e-9, "_units": "molar", "_provenance": "inferred"},
        "flux_floor": {"_type": "float", "_default": 1.0e-12, "_units": "molar/second", "_provenance": "inferred"},
        "max_cycle_len": {"_type": "integer", "_default": 6, "_units": "dimensionless", "_provenance": "inferred"},
        "reactor_volume_scale": {"_type": "float", "_default": 1.0, "_units": "liter", "_provenance": "inferred"},
        "thermo_source": {"_type": "string", "_default": "package", "_provenance": "inferred"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._rr = None
        self._u: U.Universe | None = None
        self._net: M.Network | None = None
        self._t = 0.0
        self._tick = 0
        self._kin = {k: float(self.config[k]) for k in U.DEFAULT_KINETICS}
        self._motif_summary = {"n_motifs": 0, "core_size": 0, "max_dynamic_gain": 0.0, "motifs": [],
                               "core_species": [], "n_self_amplifying": 0}
        self._fluxes: dict[str, float] = {}
        self._conc: dict[str, float] = {}
        self._element_residual = 0.0
        self._subs = None
        self._nu_co2 = None
        self._rids: list[str] = []
        self._rt = 0.0
        self._toc0 = 0.0
        self._f = {"mineral": 1.0, "base": 1.0}

    # -- face ---------------------------------------------------------------
    def inputs(self):
        return {"feed_CO2": _MOLAR, "feed_H2": _MOLAR, "feed_pyruvate": _MOLAR,
                "feed_formaldehyde": _MOLAR, "feed_formate": _MOLAR, "feed_acetate": _MOLAR}

    def outputs(self):
        out = {
            "net_carbon_flux": _OW_MOLS, "autocatalytic_gain": _OW_DIMLESS, "network_connected": _OW_DIMLESS,
            "total_organic_carbon": _OW_MOLAR, "n_persistent_species": _OW_DIMLESS,
            "n_autocatalytic_motifs": _OW_DIMLESS, "autocatalytic_core_size": _OW_DIMLESS,
            "dissipation": _OW_W, "element_residual": _OW_DIMLESS, "carbon_residual": _OW_DIMLESS,
            "catalyst_saturation": _OW_DIMLESS,
        }
        out.update({p: _OW_MOLAR for p in SPECIES_PORTS})
        return out

    def initial_state(self):
        return {"feed_CO2": 1.4e-3, "feed_H2": 1.08e-2, "feed_pyruvate": 1.0e-4,
                "feed_formaldehyde": 0.0, "feed_formate": 0.0, "feed_acetate": 0.0}

    # -- engine -------------------------------------------------------------
    def build_universe(self) -> U.Universe:
        """The network this class integrates (subclasses swap in the null)."""
        thermo = None
        if str(self.config.get("thermo_source", "package")) == "equilibrator":
            cond = U.ThermoConditions(**U.load_thermo_table()["conditions"])
            thermo = U.build_thermo_table(U.enumerate_skeletons(int(self.config["max_carbons"])), cond)
        return U.build_universe(int(self.config["max_carbons"]), thermo=thermo)

    def universe(self) -> U.Universe:
        if self._u is None:
            self._u = self.build_universe()
        return self._u

    def _engine(self, feeds: dict[str, float]):
        if self._rr is None:
            from viva_tellurium.processes import _load_roadrunner  # genuine engine via the imported wrapper (lazy)
            u = self.universe()
            init = {U.CO2: feeds.get("feed_CO2", 0.0), U.H2: feeds.get("feed_H2", 0.0)}
            self._rr = _load_roadrunner(U.to_antimony(u, self._kin, feeds, initial=init), model_format="antimony")
            self._net = M.network_from_roadrunner(self._rr)
            self._subs = U.catalyst_substrates(u)
            self._rids = list(self._rr.getReactionIds())
            rid_to_r = {r.id: r for r in u.reactions}
            self._nu_co2 = np.array([(rid_to_r[r].products.get(U.CO2, 0) - rid_to_r[r].reactants.get(U.CO2, 0))
                                     if r in rid_to_r else 0.0 for r in self._rids], dtype=float)
            self._element_residual = float(u.element_residual()["max_abs"])
            self._rt = U.R_KJ * u.conditions.temperature_K
            self._toc0 = 0.0
        return self._rr

    def _concentrations(self) -> dict[str, float]:
        rr = self._rr
        ids = list(rr.getFloatingSpeciesIds())
        vals = np.asarray(rr.getFloatingSpeciesConcentrations(), dtype=float)
        return {s: float(v) for s, v in zip(ids, vals)}

    def _dissipation(self, conc: dict[str, float], rates: dict[str, float]) -> float:
        """-sum v_r dG_r (kJ/L/s) with dG_r = dG0 + RT ln Q (floored activities)."""
        u = self.universe()
        floor = float(self.config["conc_floor"])
        total = 0.0
        for r in u.reactions:
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
            total -= v * (r.dg0 + self._rt * lnq)
        return total

    def _connected(self, conc: dict[str, float], rates: dict[str, float]) -> float:
        import networkx as nx
        floor = float(self.config["conc_floor"])
        alive = {s for s, c in conc.items() if s.startswith("X_") and c > floor}
        if len(alive) < 2:
            return 0.0
        g = nx.Graph()
        g.add_nodes_from(alive)
        fl = float(self.config["flux_floor"])
        for r in self._net.internal():
            if abs(rates.get(r.id, 0.0)) <= fl:
                continue
            members = [s for s in list(r.reactants) + list(r.products) if s in alive]
            for a in members:
                for b in members:
                    if a < b:
                        g.add_edge(a, b)
        return 1.0 if nx.is_connected(g) else 0.0

    def update(self, state, interval):
        feeds = {k: max(float(state.get(k, 0.0)), 0.0) for k in self.inputs()}
        rr = self._engine(feeds)
        for pid, val in feeds.items():
            rr[pid] = val
        # catalyst crowding for this tick (operator splitting)
        conc = self._concentrations()
        self._f = U.catalyst_factors(self._subs, conc, self._kin)
        rr.f_mineral = self._f["mineral"]; rr.f_base = self._f["base"]
        dt = max(float(interval), 1e-6)
        rr.simulate(self._t, self._t + dt, 2)
        self._t += dt
        self._tick += 1

        conc = self._concentrations()
        rates = dict(zip(self._rids, (float(x) for x in rr.getReactionRates())))
        self._conc, self._fluxes = conc, rates
        u = self.universe()
        vol = max(float(self.config["reactor_volume_scale"]), 1e-12)
        toc = float(sum(U.n_carbons(s) * conc.get(s, 0.0) for s in u.organics()))
        rate_vec = np.array([rates[r] for r in self._rids], dtype=float)
        net_fix = float(-(self._nu_co2 * rate_vec).sum()) * vol
        ledger = float(rr.Cfeed + rr.Cfix - rr.Cwash - rr.Cdeg)
        carbon_res = abs(toc - self._toc0 - ledger) / max(toc, 1e-30)
        if self._tick % int(self.config["motif_every"]) == 0 or self._tick == 1:
            motifs = M.autocatalytic_cycles(
                self._net, rates, conc, max_len=int(self.config["max_cycle_len"]),
                flux_floor=float(self.config["flux_floor"]), conc_floor=float(self.config["conc_floor"]),
                exclude=CURRENCY)
            self._motif_summary = M.summarize_motifs(motifs, conc, self._kin["k_wash"] + self._kin["k_deg"])
        ms = self._motif_summary
        floor = float(self.config["conc_floor"])
        out = {
            "net_carbon_flux": net_fix,
            "autocatalytic_gain": float(ms["max_dynamic_gain"]),
            "network_connected": self._connected(conc, rates),
            "total_organic_carbon": toc,
            "n_persistent_species": float(sum(1 for s in u.organics() if conc.get(s, 0.0) > floor)),
            "n_autocatalytic_motifs": float(ms["n_motifs"]),
            "autocatalytic_core_size": float(ms["core_size"]),
            "dissipation": self._dissipation(conc, rates) * 1.0e3 * vol,
            "element_residual": self._element_residual,
            "carbon_residual": float(carbon_res),
            "catalyst_saturation": float(1.0 - self._f["mineral"] / max(self._kin["sites_mineral"], 1e-30)),
        }
        for port, sid in SPECIES_PORTS.items():
            out[port] = float(conc.get(sid, 0.0))
        return out


class NullNetworkProcess(ReactionUniverseProcess):
    """Matched null control: the universe's compounds, reaction count, arity,
    catalyst density and carbon balance with the topology rewired
    (degree-preserving swaps within carbon-count classes); ``null_seed`` picks
    the draw. Same engine, same detector, same ledger — H/O balance is lost by
    design and the element residual reports it."""

    contract = {
        **ReactionUniverseProcess.contract,
        "summary": "Matched null network: degree-preserving, carbon-count-matched rewiring of the reaction universe on the same libRoadRunner engine and post-hoc detector.",
        "description": (
            "The adversarial control of the proto_metabolism face. Starting from the generated "
            "universe, organic species are swapped between reaction slots of equal carbon count "
            "(Maslov-Sneppen rewiring), which preserves the compound set, the reaction count, each "
            "reaction's arity, each species' participation count, every reaction's catalyst class and "
            "carbon balance, while destroying the chemistry (H/O balance and functional-group logic). "
            "Reaction dG' are recomputed from the same compound potentials so the null's kinetics are "
            "thermodynamically consistent. Integrated and graded exactly as the universe."
        ),
        "references": ["maslov2002specificity", "blokhuis2020universal"],
    }

    def build_universe(self) -> U.Universe:
        base = super().build_universe()
        seed = int(self.config.get("null_seed", -1))
        return U.null_network(base, seed if seed >= 0 else 0)


def network_state(proc: ReactionUniverseProcess) -> dict:
    """Live snapshot for the figures: concentrations, per-reaction fluxes, motifs."""
    return {"conc": dict(getattr(proc, "_conc", {}) or {}), "fluxes": dict(getattr(proc, "_fluxes", {}) or {}),
            "motifs": dict(getattr(proc, "_motif_summary", {}) or {}),
            "universe": proc.universe().summary() if getattr(proc, "_u", None) is not None else {}}


__all__ = ["ReactionUniverseProcess", "NullNetworkProcess", "SPECIES_PORTS", "CURRENCY", "network_state"]
