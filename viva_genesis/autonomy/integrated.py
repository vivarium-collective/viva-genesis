"""Integrated autonomy — the Phase-9 world (og-08-alt-robust-innovation-set).

Model Upgrade plan, Phase 9 (*integrated autonomy*): og-08's minimum innovation
set ``{pump, importer, heredity}`` was found in a coarse-grained budget where
each innovation was a term of a hand-written co-limited formula. Here the same
question is asked of ONE persistent world assembled from the merged phases, in
which every innovation is a real process of an earlier phase and the budget is
what those processes actually deliver:

* **geology** — the reduced serpentinization class (``serpentinization`` face)
  under the Phase-1 conservation ledger; the vent fluid the lineage sees is the
  Phase-1 *posterior* draw (vg-data ``integrated_autonomy``), not a best fit;
* **interface** — the Butler–Volmer carbon-fixation class (``carbon_fixation``
  face) under the Phase-2 charge ledger makes the organic feed; its net carbon
  flux relative to the in-vent steady state scales what the pore delivers;
* **pore** — a ``localization`` class (the *transport law*) shapes the feed the
  cell sees; the Phase-8 ``SpatialCouplingStep`` fires the exchange rules of
  the bigraphical reactive system (uptake / secretion / feed / washout) under
  the Phase-8 C/N/P ledger, and the Phase-3 network ledger audits the agent;
* **cell** — one protocell of the ``agents`` map running the Phase-3 reaction
  universe (``proto_ecology`` face, generalist repertoire), its mineral rules
  catalysed by the FeS surface while it sits on it and by the lineage's own
  heredity-held machinery once it has left;
* **storage model** — an ``energy_coupling`` class (Phase 6) is the cell's
  power budget under the free-energy ledger: the external tap through the leak
  (needs the gradient) and the internal store charged by the drive the cell's
  live substrate pool sustains (``drive_availability``) — the **pump**
  innovation is ``coupling_activity`` 1 vs 0;
* **permeability assumption** — a ``boundary`` class (Phase 5) sets the
  relative leakiness of the membrane (the energy leak and the exchange
  permeabilities scale with it);
* **inheritance class** — a ``heredity`` class (Phase 7) is the lineage's
  machinery: the function its individuals hold (``mean_function``) *is* the
  catalytic capacity behind the pump and the importer, attached by the
  ``HeredityAttachmentStep`` under the information ledger — the **heredity**
  innovation is attachment allowed vs forced off (og-06's non-heritable
  control);
* **importer** — :class:`ActiveImportProcess` fires the
  :class:`~viva_genesis.ecology.reactive_system.ActiveUptakeRule`: a saturable
  transporter concentrating substrates against their gradient at a
  thermodynamic cost charged to the work budget — the **importer** innovation;
* **maintenance function** — :class:`MaintenanceDemandProcess` prices upkeep
  under one of three laws (``constant`` | ``leak_repair`` | ``turnover``);
* **population** — a map of individuals fed by the lineage's net budget through
  a declared channel, dividing (``_divide``) and going extinct (``_remove``)
  by the Phase-5 structural rewrites under the rewrite ledger: ``survivors``
  is a count of real individuals, not a formula;
* :class:`AblationStep` schedules the withdrawal of the three geological
  drivers (gradient, mineral access, feed) toward their ocean floors and
  :class:`StructuralEventLogStep` records every structural event (ablation
  phases, heredity attachment, store charge / collapse, budget sign changes,
  divisions, extinctions).

:class:`AutonomyBudgetStep` reads what the processes deliver and publishes the
co-limited budget and the **continuous autonomy value**: the fraction of
essential work supplied internally (store vs tap), of material supplied by the
lineage's own machinery (active import + own fixation vs passive delivery) and
of catalysis supplied by heredity-held machinery vs the mineral surface — and
their work-weighted total. Everything is per individual in SI.

The tick is ``tick_seconds`` of world time; the heredity class's Gillespie
clock runs ``heredity_clock_ratio`` lineage-time units per world second (its
rate constants are hypothetical in vg-data ``inheritance_budgets``, so their
absolute scale is a declared assumption, recorded in ``integrated_autonomy``).
"""
from __future__ import annotations

import math

from process_bigraph import Process, Step

from ..ecology.proto_ecology import CANONICAL_TO_UNIVERSE, species_elements
from ..protometabolism import universe as U

_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_W = {"_type": "float", "_units": "watt"}
_MOLS = {"_type": "float", "_units": "mole/second"}
_MOL = {"_type": "float", "_units": "mole"}
_MOLAR = {"_type": "float", "_units": "molar"}
_OW = {"_type": "overwrite[float]", "_units": "dimensionless"}
_OW_W = {"_type": "overwrite[float]", "_units": "watt"}
_OW_MOLS = {"_type": "overwrite[float]", "_units": "mole/second"}
_OW_MOL = {"_type": "overwrite[float]", "_units": "mole"}
_OW_V = {"_type": "overwrite[float]", "_units": "volt"}
_OW_MOLAR = {"_type": "overwrite[float]", "_units": "molar"}

R_J = 8.314462618       # J/mol/K
F_C = 96485.33212       # C/mol
LN10 = math.log(10.0)

INNOVATIONS = ("pump", "importer", "heredity")
MAINTENANCE_LAWS = ("constant", "leak_repair", "turnover")
DRIVERS = ("gradient", "mineral", "feed")


def _p(default, units="dimensionless", prov="hypothetical", typ="float"):
    return {"_type": typ, "_default": default, "_units": units, "_provenance": prov}


def pmf_from_delta_ph(delta_ph: float, temperature_k: float) -> float:
    """The proton-motive force (V) of a pH contrast: ln(10) R T / F per pH unit."""
    return LN10 * R_J * float(temperature_k) / F_C * float(delta_ph)


# --------------------------------------------------------------------------- #
# Ablation — the scheduled withdrawal of geological support
# --------------------------------------------------------------------------- #
class AblationStep(Step):
    """Schedule the withdrawal of the three geological drivers.

    Each driver's support fraction holds at 1 until ``start`` (world seconds),
    relaxes linearly to its ocean floor over ``duration`` and stays there — the
    off-gradient test of og-08 as a scheduled perturbation of ONE persistent
    world rather than a parameter sweep. ``environment = "generic"`` is the
    og-adv reject control: every driver sits at its floor from t = 0 (no
    sustained H2 feed, no mineral catalyst, no gradient). Publishes the three
    fractions, the ablation phase (0 hold, 1 withdrawing, 2 withdrawn) and the
    structural events it causes.
    """

    contract = {
        "summary": "Scheduled withdrawal of the geological drivers (gradient, mineral access, feed) toward their ocean floors — the off-gradient test as a perturbation of one persistent world.",
        "description": (
            "support_X(t) = 1 for t < start; 1 - (1 - floor_X) (t - start) / duration while withdrawing; floor_X "
            "after. environment = 'generic' holds every driver at its floor from t = 0 (the og-adv reject control). "
            "Publishes the fractions, the phase and the ablation events."
        ),
        "inputs": {"global_time": "world clock (second)"},
        "outputs": {"gradient_support": "external pmf fraction (0-1)", "mineral_access": "FeS catalyst access (0-1)",
                    "feed_support": "fraction of vent fluid delivered to the pore (0-1)",
                    "ablation_phase": "0 hold, 1 withdrawing, 2 withdrawn", "events": "structural-event log entries"},
        "assumptions": ["Linear, simultaneous withdrawal of the three drivers (a controlled perturbation, not a cell upgrade)."],
        "references": ["martin2007origin", "sojo2014bioenergetic"],
    }

    config_schema = {
        "start": _p(3600.0, "second"),
        "duration": _p(6000.0, "second"),
        "gradient_floor": _p(0.0),
        "mineral_floor": _p(0.0),
        "feed_floor": _p(1.0e-2),
        "environment": {"_type": "string", "_default": "vent", "_provenance": "inferred"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._last_time = None
        self._phase = -1
        self._n_events = 0

    def inputs(self):
        return {"global_time": "float"}

    def outputs(self):
        return {"gradient_support": _OW, "mineral_access": _OW, "feed_support": _OW,
                "ablation_phase": _OW, "events": "tree"}

    def perform_update(self, state) -> bool:
        t = state.get("global_time")
        if t == self._last_time:
            return False
        self._last_time = t
        return True

    def floors(self) -> dict:
        return {"gradient": float(self.config["gradient_floor"]), "mineral": float(self.config["mineral_floor"]),
                "feed": float(self.config["feed_floor"])}

    def support(self, t: float) -> dict:
        floors = self.floors()
        if str(self.config["environment"]) == "generic":
            return dict(floors), 2
        start, dur = float(self.config["start"]), max(float(self.config["duration"]), 1e-9)
        if t < start:
            return {k: 1.0 for k in floors}, 0
        x = min((t - start) / dur, 1.0)
        return {k: 1.0 - (1.0 - f) * x for k, f in floors.items()}, (2 if x >= 1.0 else 1)

    def _event(self, t, kind, detail):
        self._n_events += 1
        return {f"e{self._n_events:04d}": {"t": float(t), "kind": kind, "detail": detail, "source": "ablation"}}

    def update(self, state):
        t = float(state.get("global_time", 0.0))
        sup, phase = self.support(t)
        events = {}
        if self._phase < 0:
            events.update(self._event(t, "world_assembled",
                                      f"environment={self.config['environment']} floors={self.floors()}"))
        if phase != self._phase:
            if phase == 1:
                events.update(self._event(t, "ablation_started", "gradient, mineral access and feed withdrawing"))
            elif phase == 2 and self._phase >= 0:
                events.update(self._event(t, "ablation_complete", f"drivers at their floors {self.floors()}"))
            self._phase = phase
        out = {"gradient_support": sup["gradient"], "mineral_access": sup["mineral"], "feed_support": sup["feed"],
               "ablation_phase": float(phase)}
        if events:
            out["events"] = events
        return out


# --------------------------------------------------------------------------- #
# Geological drivers — the posterior endmembers scaled by the support fractions
# --------------------------------------------------------------------------- #
class GeologicalDriverStep(Step):
    """Turn the support fractions into the physical drivers the phases read.

    The vent endmembers are one Phase-1 posterior draw (dissolved H2, ΔpH, T);
    the ocean endmembers are the Hadean-ocean floors. Publishes the external
    pmf (``electric_potential``), the vent-side pH the interface sees, the
    FeS catalyst activity, the dissolved H2 at the interface and the LIVE pore
    feed (universe species → molar): H2 and the inorganic N / P scaled by the
    feed fraction, CO2 from the ocean (never withdrawn), and the organic feed
    scaled by the feed fraction AND by the interface's net carbon flux relative
    to its in-vent steady state (the running maximum during the hold) — so the
    feed collapses when any driver the fixation chemistry needs is withdrawn.
    """

    contract = {
        "summary": "Posterior vent endmembers x support fractions -> pmf, interface pH, catalyst activity, interface H2 and the live pore feed (organics scaled by the fixation class's relative carbon flux).",
        "description": (
            "electric_potential = pmf(dpH, T) gradient_support; pH_vent = pH_ocean + dpH gradient_support; "
            "catalyst_activity = max(mineral_access, 1e-6); H2_interface = H2_ocean + (H2_vent - H2_ocean) feed_support; "
            "pore feed: H2 as at the interface, CO2 = DIC, pyruvate = feed_pyruvate feed_support (J_C / J_C,ref), "
            "ammonium / phosphate scaled by feed_support."
        ),
        "inputs": {"gradient_support": "0-1", "mineral_access": "0-1", "feed_support": "0-1",
                   "net_carbon_flux": "the interface's net carbon flux (mole/second)", "global_time": "clock"},
        "outputs": {"electric_potential": "volt", "pH_vent": "pH", "catalyst_activity": "0-1", "H2": "molar",
                    "feed": "pore feed (universe species -> molar)", "fixation_relative": "J_C / J_C,ref (0-1)"},
    }

    config_schema = {
        "h2_vent": _p(1.08e-2, "molar", "calibrated"),
        "h2_ocean": _p(0.0, "molar"),
        "delta_ph": _p(3.5, "dimensionless", "calibrated"),
        "ph_ocean": _p(6.0, "dimensionless", "extrapolated"),
        "temperature": _p(322.15, "kelvin", "calibrated"),
        "dic": _p(2.0e-3, "molar", "extrapolated"),
        "feed_pyruvate": _p(1.0e-4, "molar", "inferred"),
        "feed_formate": _p(0.0, "molar"),
        "feed_ammonium": _p(5.0e-5, "molar", "extrapolated"),
        "feed_phosphate": _p(1.0e-5, "molar", "extrapolated"),
        "feed_floor": _p(1.0e-2),
        "ablation_start": _p(3600.0, "second"),
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._last_time = None
        self._ref_flux = 0.0

    def inputs(self):
        return {"gradient_support": _DIMLESS, "mineral_access": _DIMLESS, "feed_support": _DIMLESS,
                "net_carbon_flux": _MOLS, "global_time": "float"}

    def outputs(self):
        return {"electric_potential": _OW_V, "pH_vent": _OW, "catalyst_activity": _OW, "H2": _OW_MOLAR,
                "feed": "tree", "fixation_relative": _OW}

    def perform_update(self, state) -> bool:
        t = state.get("global_time")
        if t == self._last_time:
            return False
        self._last_time = t
        return True

    def update(self, state):
        c = self.config
        t = float(state.get("global_time", 0.0))
        g = min(max(float(state.get("gradient_support", 1.0)), 0.0), 1.0)
        m = min(max(float(state.get("mineral_access", 1.0)), 0.0), 1.0)
        f = min(max(float(state.get("feed_support", 1.0)), 0.0), 1.0)
        flux = max(float(state.get("net_carbon_flux", 0.0)), 0.0)
        if t <= float(c["ablation_start"]):
            self._ref_flux = max(self._ref_flux, flux)
        rel = min(flux / self._ref_flux, 1.0) if self._ref_flux > 0.0 else 0.0
        h2 = float(c["h2_ocean"]) + (float(c["h2_vent"]) - float(c["h2_ocean"])) * f
        # the organic feed: the interface's products at the delivered fraction, never
        # below the ocean background (the same floor fraction as the feed itself)
        org = max(f * rel, float(c["feed_floor"]))
        # every key every tick (the feed store is a deep-merged tree: a withdrawn
        # species must read 0, not its last value)
        feed = {CANONICAL_TO_UNIVERSE["H2"]: h2, CANONICAL_TO_UNIVERSE["CO2"]: float(c["dic"]),
                CANONICAL_TO_UNIVERSE["pyruvate"]: float(c["feed_pyruvate"]) * org,
                CANONICAL_TO_UNIVERSE["formate"]: float(c["feed_formate"]) * org,
                "ammonium": float(c["feed_ammonium"]) * f, "phosphate": float(c["feed_phosphate"]) * f}
        return {"electric_potential": pmf_from_delta_ph(float(c["delta_ph"]), float(c["temperature"])) * g,
                "pH_vent": float(c["ph_ocean"]) + float(c["delta_ph"]) * g,
                "catalyst_activity": max(m, 1.0e-6), "H2": h2, "feed": feed, "fixation_relative": rel}


# --------------------------------------------------------------------------- #
# The transport law -> the per-species enrichment the coupling step reads
# --------------------------------------------------------------------------- #
class EnrichmentAdapterStep(Step):
    """Adapt a single-tracer ``localization`` class (og-03's column and its
    reduced surrogate publish ONE ``enrichment_factor``) onto the per-species
    ``enrichment`` tree the Phase-8 coupling step reads: every feed species
    gets the same factor — the species-agnostic transport law the multisolute
    classes refine species by species."""

    config_schema = {"species": {"_type": "string", "_default": "H2,CO2,pyruvate,formate,acetate,ammonium,phosphate",
                                 "_provenance": "inferred"}}

    def inputs(self):
        return {"enrichment_factor": _DIMLESS}

    def outputs(self):
        return {"enrichment": "tree"}

    def update(self, state):
        f = max(float(state.get("enrichment_factor", 1.0)), 1e-30)
        return {"enrichment": {s.strip(): f for s in str(self.config["species"]).split(",") if s.strip()}}


# --------------------------------------------------------------------------- #
# Lineage state — machinery, catalysis, drive availability
# --------------------------------------------------------------------------- #
class LineageStateProcess(Process):
    """Read the lineage's heredity class and the cell's live pools into the
    quantities the innovations run on.

    * ``machinery`` = the heredity class's ``mean_function`` over its
      ``function_reference`` (the function level at which the lineage holds
      its full machinery; hypothetical), clipped to 1 — the catalytic capacity
      behind the pump and the importer. With heredity forced off the class
      still runs (daughters re-form their heritable state de novo), so the
      knockout's machinery is whatever the de novo state holds.
    * ``catalysis_total`` = 1 - (1 - mineral_access)(1 - machinery): the
      mineral surface while on it, the lineage's own machinery once off it
      (drives the agent's mineral-catalysed rules).
    * ``drive_availability`` = max(H2_in / (H2_in + K_H2), org_in / (org_in +
      K_org)) x machinery: the fraction of the drive turnover the cell's own
      substrate pool sustains, coupled by its machinery — the pump's live input.
    * ``autonomy_information`` = machinery (1 - mineral_access) / catalysis_total:
      the share of the lineage's catalysis its heredity supplies.
    """

    config_schema = {
        "function_reference": _p(0.25),
        "k_h2": _p(1.0e-5, "molar"),
        "k_org": _p(1.0e-5, "molar"),
        "heredity": {"_type": "string", "_default": "on", "_provenance": "inferred"},
    }

    def inputs(self):
        return {"mean_function": _DIMLESS, "mineral_access": _DIMLESS, "internal": "map[vg_concentration]"}

    def outputs(self):
        return {"machinery": _OW, "catalysis_total": _OW, "catalysis_internal": _OW, "drive_availability": _OW,
                "substrate_availability": _OW, "autonomy_information": _OW}

    def initial_state(self):
        return {"mean_function": 0.0, "mineral_access": 1.0, "internal": {}}

    def update(self, state, interval):
        c = self.config
        fn = max(float(state.get("mean_function", 0.0)), 0.0)
        machinery = min(fn / max(float(c["function_reference"]), 1e-12), 1.0)
        mineral = min(max(float(state.get("mineral_access", 1.0)), 0.0), 1.0)
        total = 1.0 - (1.0 - mineral) * (1.0 - machinery)
        pool = state.get("internal", {}) or {}
        h2 = max(float(pool.get(CANONICAL_TO_UNIVERSE["H2"], 0.0)), 0.0)
        org = sum(max(float(pool.get(CANONICAL_TO_UNIVERSE[k], 0.0)), 0.0) for k in ("pyruvate", "formate", "acetate"))
        a_h2 = h2 / (h2 + float(c["k_h2"]))
        a_org = org / (org + float(c["k_org"]))
        substrate = max(a_h2, a_org)
        info = (machinery * (1.0 - mineral) / total) if total > 0.0 else 0.0
        return {"machinery": machinery, "catalysis_total": total, "catalysis_internal": machinery,
                "drive_availability": substrate * machinery, "substrate_availability": substrate,
                "autonomy_information": info}


# --------------------------------------------------------------------------- #
# The importer — the active-uptake rule fired on the agents map
# --------------------------------------------------------------------------- #
class ActiveImportProcess(Process):
    """Fire the :class:`~viva_genesis.ecology.reactive_system.ActiveUptakeRule`
    for every agent: a saturable transporter (``v_max`` per substrate at full
    machinery, scaled by the lineage's machinery) moving the configured
    substrates from the agent's field cell into the agent against their
    gradient, regulated like a transporter: it runs only while the inside is
    below its set-point (``targets``, a fraction of the in-vent level) and
    spends at most ``budget_fraction`` of the lineage's work supply per tick.
    Conserving (the same moles leave the cell and enter the agent); counted;
    its thermodynamic cost (RT ln(c_in / c_out) per mole uphill, over the
    transporter efficiency) is published as ``import_power`` for the work
    budget. ``importer = "off"`` is the knockout (no rule fires). A Process (not
    a Step): it exchanges with the same agents and field the coupling step
    does, and steps must form a DAG — the rule fires once per world tick."""

    contract = {
        "summary": "The importer innovation as a counted, conserving exchange rule: saturable active uptake against the gradient, costing RT ln(c_in/c_out) per mole from the work budget.",
        "description": (
            "Builds the reactive-system context from the agents map and the field, gives every agent an importer "
            "capacity v_max x machinery per substrate, fires ActiveUptakeRule and writes the deltas back; publishes "
            "the moles imported per species this tick, the organic carbon imported per second, the import power "
            "and the cumulative firings."
        ),
        "inputs": {"agents": "agents map", "lineages": "per-agent position", "field": "pore cells",
                   "machinery": "lineage machinery (0-1)", "global_time": "clock"},
        "outputs": {"agents": "uptake deltas", "field": "uptake deltas", "active_uptake": "moles per species this tick",
                    "active_uptake_carbon": "organic carbon imported (mole/second)", "import_power": "watt",
                    "import_firings": "cumulative firings"},
        "assumptions": ["Michaelis-Menten transporter regulated to an inside / outside ratio cap; thermodynamic minimum cost of concentration over a fixed coupling efficiency."],
        "references": ["sojo2014bioenergetic", "lane2012origin"],
    }

    config_schema = {
        "importer": {"_type": "string", "_default": "on", "_provenance": "inferred"},
        "v_max": _p(1.0e-19, "mole/second"),
        "k_m": _p(1.0e-6, "molar"),
        "max_ratio": _p(100.0),
        "targets": {"_type": "tree", "_default": {}, "_provenance": "hypothetical"},
        "budget_fraction": _p(0.3),
        "efficiency": _p(0.5),
        "temperature": _p(322.15, "kelvin", "calibrated"),
        "substrates": {"_type": "string", "_default": "pyruvate,formate,acetate,H2", "_provenance": "hypothetical"},
        "n_cells": _p(1, typ="integer", prov="inferred"),
        "cell_volume": _p(1.0e-17, "liter"),
        "coupling": {"_type": "string", "_default": "shared", "_provenance": "inferred"},
        "max_carbons": _p(4, typ="integer", prov="hypothetical"),
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        from ..ecology.reactive_system import ActiveUptakeRule, BigraphicalReactiveSystem
        rt = R_J * float(self.config["temperature"])
        self.system = BigraphicalReactiveSystem(rules=[ActiveUptakeRule(k_m=float(self.config["k_m"]),
                                                                        efficiency=float(self.config["efficiency"]),
                                                                        rt_j=rt, max_ratio=float(self.config["max_ratio"]),
                                                                        targets=dict(self.config.get("targets") or {}))])
        self._elements = species_elements(int(self.config["max_carbons"]))
        self._species = [CANONICAL_TO_UNIVERSE.get(s.strip(), s.strip())
                         for s in str(self.config["substrates"]).split(",") if s.strip()]

    def inputs(self):
        return {"agents": "map[vg_individual]", "lineages": "map[vg_lineage]",
                "field": "map[map[vg_concentration]]", "machinery": _DIMLESS, "work_supply": _W}

    def outputs(self):
        return {"agents": "map[vg_individual]", "field": "map[map[vg_concentration]]", "active_uptake": "tree",
                "active_uptake_carbon": _OW_MOLS, "import_power": _OW_W, "import_firings": _OW,
                "import_moles": _OW_MOL}

    def initial_state(self):
        return {"machinery": 0.0, "work_supply": 0.0}

    def update(self, state, interval):
        from ..ecology.proto_ecology import _cell_of
        from ..ecology.reactive_system import RuleContext
        dt = float(interval)
        zero_uptake = {s: 0.0 for s in self._species}
        off = str(self.config["importer"]).lower() != "on"
        machinery = min(max(float(state.get("machinery", 0.0)), 0.0), 1.0)
        vmax = 0.0 if off else float(self.config["v_max"]) * machinery
        n_cells = int(self.config["n_cells"])
        agents_in = state.get("agents", {}) or {}
        lineages = state.get("lineages", {}) or {}
        field_in = state.get("field", {}) or {}
        cells = {f"c{i}": dict(field_in.get(f"c{i}", {}) or {}) for i in range(n_cells)}
        agents = {}
        for aid, a in agents_in.items():
            lin = lineages.get(aid, {}) or {}
            agents[aid] = {"volume": float(a.get("volume", 1.0e-18)),
                           "cell": f"c{_cell_of(lin.get('position', (0.0, 0.0)), n_cells)}",
                           "internal": dict((a.get("internal") or {}).get("dissolved") or {}), "k": {},
                           "lineage": str(lin.get("lineage_id", "?")), "importer": {s: vmax for s in self._species}}
        if vmax <= 0.0 or not agents:
            return {"active_uptake": zero_uptake, "active_uptake_carbon": 0.0, "import_power": 0.0,
                    "import_firings": float(sum(self.system.counts.values())),
                    "import_moles": float(sum(self.system.moles.values()))}
        before = {aid: dict(a["internal"]) for aid, a in agents.items()}
        cells_before = {ck: dict(c) for ck, c in cells.items()}
        ctx = RuleContext(agents=agents, cells=cells, cell_volume=float(self.config["cell_volume"]),
                          background={ck: dict(c) for ck, c in cells.items()}, elements=self._elements, dt=dt,
                          private=(str(self.config["coupling"]) == "private"))
        # the transporter may spend at most budget_fraction of the lineage's work this tick
        ctx.import_budget = float(self.config["budget_fraction"]) * max(float(state.get("work_supply", 0.0)), 0.0) * dt
        self.system.fire(ctx)
        energy = float(getattr(ctx, "import_energy", 0.0))
        uptake = dict(zero_uptake)
        carbon = 0.0
        for f in ctx.firings:
            uptake[f.species] = uptake.get(f.species, 0.0) + f.moles
            carbon += f.moles * float((self._elements.get(f.species) or {}).get("C", 0))
        agent_deltas = {aid: {"internal": {"dissolved": {s: a["internal"][s] - before[aid].get(s, 0.0)
                                                          for s in a["internal"] if a["internal"][s] != before[aid].get(s, 0.0)}}}
                        for aid, a in agents.items()}
        field_deltas = {ck: {s: c[s] - cells_before[ck].get(s, 0.0) for s in c if c[s] != cells_before[ck].get(s, 0.0)}
                        for ck, c in cells.items()}
        return {"agents": agent_deltas, "field": field_deltas, "active_uptake": uptake,
                "active_uptake_carbon": carbon / dt, "import_power": energy / dt,
                "import_firings": float(sum(self.system.counts.values())),
                "import_moles": float(sum(self.system.moles.values()))}


# --------------------------------------------------------------------------- #
# Maintenance functions
# --------------------------------------------------------------------------- #
class MaintenanceDemandProcess(Process):
    """Price the lineage's upkeep under one of three maintenance laws (W per
    individual), calibrated to coincide at the reference point (full machinery,
    fatty-acid leakiness, pump on) and to differ in what they scale with:

    * ``constant`` — ``m_base + m_active a_eff`` (the Phase-6 law: upkeep
      follows the machinery actively coupled, ``a_eff = coupling x machinery``);
    * ``leak_repair`` — ``m_base + m_active a_eff x relative_leak`` (Sojo 2014:
      a leakier membrane costs proportionally more to keep energised);
    * ``turnover`` — ``m_base + m_active x machinery`` (Lane & Martin 2012:
      re-synthesis of the machinery held, whether or not it is used).
    """

    contract = {
        "summary": "Maintenance power under one of three laws: constant (Phase 6), leak_repair (scales with membrane leakiness), turnover (scales with machinery held).",
        "description": "m = m_base + m_active a_eff | m_base + m_active a_eff rel_leak | m_base + m_active machinery.",
        "inputs": {"machinery": "0-1", "relative_leak": ">= 1", "pump_on": "0/1"},
        "outputs": {"maintenance_power": "watt"},
        "references": ["sojo2014bioenergetic", "lane2012origin"],
    }

    config_schema = {
        "law": {"_type": "string", "_default": "constant", "_provenance": "hypothetical"},
        "m_base": _p(1.0e-19, "watt"),
        "m_active": _p(5.0e-18, "watt"),
        "pump": {"_type": "string", "_default": "on", "_provenance": "inferred"},
    }

    def inputs(self):
        return {"machinery": _DIMLESS, "relative_leak": _DIMLESS}

    def outputs(self):
        return {"maintenance_power": _OW_W}

    def initial_state(self):
        return {"machinery": 0.0, "relative_leak": 1.0}

    def update(self, state, interval):
        law = str(self.config["law"])
        if law not in MAINTENANCE_LAWS:
            raise ValueError(f"maintenance law must be one of {MAINTENANCE_LAWS}, got {law!r}")
        m = min(max(float(state.get("machinery", 0.0)), 0.0), 1.0)
        rel = max(float(state.get("relative_leak", 1.0)), 1.0)
        a_eff = m if str(self.config["pump"]).lower() == "on" else 0.0
        base, active = float(self.config["m_base"]), float(self.config["m_active"])
        if law == "constant":
            demand = base + active * a_eff
        elif law == "leak_repair":
            demand = base + active * a_eff * rel
        else:
            demand = base + active * m
        return {"maintenance_power": demand}


# --------------------------------------------------------------------------- #
# The lineage's supply to its heredity class: precursors from its own carbon,
# energy as a declared share of its work
# --------------------------------------------------------------------------- #
class LineageSupplyProcess(Process):
    """Feed the heredity class's shared pools and energy store from the
    integrated world instead of a chemostat: each precursor pool relaxes
    toward ``precursor_yield x total_organic_carbon`` (the fraction of the
    cell's own organic carbon that is activated precursor; hypothetical) and
    the store receives ``allocation x work x n_individuals`` per tick, capped —
    published as ``work_flux`` so the information ledger stays exact."""

    contract = {
        "summary": "Precursor pools from the cell's own organic carbon and an energy allocation from its work — the heredity budgets of the integrated world.",
        "description": "pool += feed_rate (yield TOC - pool); stored_work += min(allocation work N dt, room); work_flux = that inflow.",
        "inputs": {"work": "per-individual work (watt)", "total_organic_carbon": "the cell's organic carbon (molar C)",
                   "stored_work": "the heredity energy store (joule)"},
        "outputs": {"work_flux": "energy added this tick (joule)"},
    }

    config_schema = {
        "allocation": _p(0.3),
        "n_individuals": _p(32, typ="integer", prov="inferred"),
        "max_stored_work": _p(8.0e-16, "joule"),
        "precursor_yield": _p(0.1),
        "feed_rate": _p(0.5),
    }

    POOLS = ("nucleotide_precursor", "amino_precursor", "amphiphile", "mineral_precursor")

    def inputs(self):
        return {"work": _W, "total_organic_carbon": _MOLAR, "stored_work": {"_type": "float", "_units": "joule"},
                **{p: _MOLAR for p in self.POOLS}}

    def outputs(self):
        return {**{p: _MOLAR for p in self.POOLS}, "stored_work": {"_type": "float", "_units": "joule"},
                "work_flux": {"_type": "overwrite[float]", "_units": "joule"}}

    def initial_state(self):
        return {"work": 0.0, "total_organic_carbon": 0.0, "stored_work": 0.0, **{p: 0.0 for p in self.POOLS}}

    def update(self, state, interval):
        c = self.config
        target = float(c["precursor_yield"]) * max(float(state.get("total_organic_carbon", 0.0)), 0.0)
        r = float(c["feed_rate"])
        out = {p: r * (target - float(state.get(p, 0.0))) for p in self.POOLS}
        work = max(float(state.get("work", 0.0)), 0.0)
        room = max(float(c["max_stored_work"]) - float(state.get("stored_work", 0.0)), 0.0)
        flux = min(float(c["allocation"]) * work * int(c["n_individuals"]) * float(interval), room)
        out["stored_work"] = flux
        out["work_flux"] = flux
        return out


# --------------------------------------------------------------------------- #
# The co-limited budget and the autonomy decomposition
# --------------------------------------------------------------------------- #
class AutonomyBudgetStep(Step):
    """Read what the phases deliver and publish the co-limited budget and the
    continuous autonomy value, decomposed by function.

    Work (W per individual): supply = external tap + internal store work
    (the energy_coupling class); demand = maintenance (the maintenance law) +
    import power (the active-uptake rule) + the heredity allocation. Material
    (mol C/s): supply = passive organic uptake (the exchange rules, net of
    secretion, clipped at 0) + active organic import + the cell's own CO2
    fixation; demand = the carbon its network degrades to tar. Autonomy:
    work = internal / (internal + external); material = (active + own fixation)
    / supply; total = work-weighted over both with carbon at its free-energy
    equivalent. ``lineage_fitness`` = min(net work / P_scale, net material /
    M_scale) (dimensionless, og-08's readout name).
    """

    contract = {
        "summary": "The integrated co-limited budget (work AND material) and the continuous autonomy value decomposed by function (work / material / information).",
        "description": (
            "net_power = external + internal - maintenance - import - allocation x (external + internal); "
            "material_net = uptake_C + active_C + fixation_C - degraded_C; autonomy_work = internal / (internal + external); "
            "autonomy_material = (active_C + fixation_C) / supply_C; autonomy = (internal + (active_C + fixation_C) dG_C) / "
            "(internal + external + supply_C dG_C)."
        ),
        "inputs": {"external_power": "watt", "internal_power": "watt", "maintenance_power": "watt", "import_power": "watt",
                   "exchange": "per-agent uptake / secretion this tick (moles)", "active_uptake_carbon": "mole/second",
                   "rates": "per-agent network sensors", "autonomy_information": "0-1", "global_time": "clock"},
        "outputs": {"net_power": "watt", "material_net": "mole/second", "autonomy": "0-1", "lineage_fitness": "dimensionless"},
        "assumptions": ["Carbon is priced at a fixed free-energy equivalent when work and material are combined."],
        "references": ["sojo2014bioenergetic", "lane2012origin", "martin2007origin"],
    }

    config_schema = {
        "allocation": _p(0.3),
        "carbon_energy_equivalent": _p(4.0e4, "joule/mole"),
        "dt": _p(10.0, "second", "inferred"),
        "power_scale": _p(1.0e-17, "watt", "inferred"),
        "material_scale": _p(1.0e-23, "mole/second", "inferred"),
        "max_carbons": _p(4, typ="integer", prov="hypothetical"),
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._elements = species_elements(int(self.config["max_carbons"]))
        self._last_time = None
        self._deg_prev = None

    def inputs(self):
        return {"external_power": _W, "internal_power": _W, "maintenance_power": _W, "import_power": _W,
                "exchange": "tree", "active_uptake_carbon": _MOLS, "rates": "map[map[float]]",
                "autonomy_information": _DIMLESS, "global_time": "float"}

    def outputs(self):
        return {"work_supply": _OW_W, "work_demand": _OW_W, "heredity_power": _OW_W, "net_power": _OW_W,
                "passive_carbon": _OW_MOLS, "secreted_carbon": _OW_MOLS, "active_carbon": _OW_MOLS, "fixation_carbon": _OW_MOLS,
                "degradation_carbon": _OW_MOLS, "material_supply": _OW_MOLS, "material_net": _OW_MOLS,
                "autonomy_work": _OW, "autonomy_material": _OW, "autonomy_information": _OW, "autonomy": _OW,
                "lineage_fitness": _OW, "energy_ok": _OW, "material_ok": _OW}

    def perform_update(self, state) -> bool:
        t = state.get("global_time")
        if t == self._last_time:
            return False
        self._last_time = t
        return True

    def update(self, state):
        c = self.config
        dt = float(c["dt"])
        ext = max(float(state.get("external_power", 0.0)), 0.0)
        inte = max(float(state.get("internal_power", 0.0)), 0.0)
        maint = max(float(state.get("maintenance_power", 0.0)), 0.0)
        imp = max(float(state.get("import_power", 0.0)), 0.0)
        supply = ext + inte
        heredity = float(c["allocation"]) * supply
        demand = maint + imp + heredity
        net = supply - demand
        # organic carbon through the exchange rules: uptake is supply, secretion the
        # cell's steady-state export (reported, not subtracted)
        passive = secreted = 0.0
        for aid, ex in (state.get("exchange", {}) or {}).items():
            for s, v in ((ex or {}).get("uptake") or {}).items():
                if s != U.CO2:
                    passive += float(v) * float((self._elements.get(s) or {}).get("C", 0))
            for s, v in ((ex or {}).get("secretion") or {}).items():
                if s != U.CO2:
                    secreted += float(v) * float((self._elements.get(s) or {}).get("C", 0))
        passive /= dt
        secreted /= dt
        active = max(float(state.get("active_uptake_carbon", 0.0)), 0.0)
        rates = state.get("rates", {}) or {}
        fixation = sum(max(float((r or {}).get("co2_fixation", 0.0)), 0.0) for r in rates.values())
        deg_cum = sum(float((r or {}).get("carbon_degraded", 0.0)) for r in rates.values())
        if self._deg_prev is None:
            self._deg_prev = deg_cum
        degradation = max(deg_cum - self._deg_prev, 0.0) / dt
        self._deg_prev = deg_cum
        material_supply = passive + active + fixation
        material_net = material_supply - degradation
        a_work = inte / supply if supply > 0.0 else 0.0
        own = active + fixation
        a_mat = own / material_supply if material_supply > 0.0 else 0.0
        g_c = float(c["carbon_energy_equivalent"])
        tot = supply + material_supply * g_c
        a_tot = (inte + own * g_c) / tot if tot > 0.0 else 0.0
        fitness = min(net / float(c["power_scale"]), material_net / float(c["material_scale"]))
        return {"work_supply": supply, "work_demand": demand, "heredity_power": heredity, "net_power": net,
                "passive_carbon": passive, "secreted_carbon": secreted, "active_carbon": active, "fixation_carbon": fixation,
                "degradation_carbon": degradation, "material_supply": material_supply, "material_net": material_net,
                "autonomy_work": a_work, "autonomy_material": a_mat,
                "autonomy_information": min(max(float(state.get("autonomy_information", 0.0)), 0.0), 1.0),
                "autonomy": a_tot, "lineage_fitness": fitness,
                "energy_ok": 1.0 if net >= 0.0 else 0.0, "material_ok": 1.0 if material_net >= 0.0 else 0.0}


# --------------------------------------------------------------------------- #
# The population — individuals fed by the budget, divided / removed by rewrites
# --------------------------------------------------------------------------- #
class PopulationBudgetProcess(Process):
    """Carry the lineage's net budget into a population of real individuals.

    Each tick the lineage's co-limited gain — ``min(material_net, net_power /
    carbon_energy_equivalent)`` mol C (og-08's Liebig minimum: the scarcer of
    carbon and the work to fix it; a deficit on either side is a loss) —
    enters the ``localized`` biomass reservoir (a gain) or is drawn from the
    individuals (a deficit);
    the amount is published as ``external_flux`` so the rewrite ledger closes
    exactly. Individuals then take matter from the reservoir (up to
    ``uptake_cap`` each, while the population is below ``max_population``) and
    their ``division_state`` tracks matter / ``division_mass``: the Phase-5
    ``DivisionStep`` divides them at 1 (``_divide``, matter halved) and the
    individuals starved below ``min_matter`` are removed here by the Phase-5
    ``_remove`` rewrite (their matter reported as ``removed_matter`` for the
    rewrite ledger). ``survivors`` = alive / initial (capped at 1), og-08's
    readout from a count.
    """

    contract = {
        "summary": "The lineage budget as a population of individuals: biomass reservoir in / out (declared external_flux), growth to division, starvation to extinction.",
        "description": "gain = min(material_net, net_power / dG_C) dt; >= 0 -> reservoir, < 0 -> drawn from individuals; individuals fill from the reservoir and divide at matter = division_mass.",
        "inputs": {"population": "map of individuals", "localized": "biomass reservoir (mole)", "net_power": "watt",
                   "material_net": "mole/second"},
        "outputs": {"external_flux": "moles entering (> 0) / leaving (< 0) the audited system this tick",
                    "survivors": "alive / initial", "n_alive": "count"},
    }

    config_schema = {
        "carbon_energy_equivalent": _p(4.0e4, "joule/mole"),
        "division_mass": _p(1.0e-21, "mole"),
        "uptake_cap": _p(2.0e-22, "mole"),
        "max_population": _p(64, typ="integer"),
        "n_initial": _p(8, typ="integer"),
        "min_matter": _p(1.0e-22, "mole"),
    }

    def inputs(self):
        return {"population": "map[vg_individual]", "localized": "map[vg_amount]", "net_power": _W,
                "material_net": _MOLS}

    def outputs(self):
        return {"population": "map[vg_individual]", "localized": "map[vg_amount]", "external_flux": "overwrite[float]",
                "survivors": _OW, "n_alive": _OW, "reservoir": _OW_MOL, "extinct": "overwrite[float]",
                "removed_matter": "overwrite[float]"}

    def initial_state(self):
        return {"net_power": 0.0, "material_net": 0.0}

    def update(self, state, interval):
        c = self.config
        dt = float(interval)
        pop = {k: v for k, v in (state.get("population", {}) or {}).items() if isinstance(v, dict) and "internal_amounts" in v}
        reservoir = float((state.get("localized", {}) or {}).get("carbon", 0.0))
        net_p = float(state.get("net_power", 0.0))
        mat = float(state.get("material_net", 0.0))
        gain = min(mat, net_p / float(c["carbon_energy_equivalent"])) * dt
        n = len(pop)
        have = {k: float((ind.get("internal_amounts") or {}).get("carbon", 0.0)) for k, ind in pop.items()}
        loss = {k: 0.0 for k in pop}      # starvation: matter leaving the system (external, < 0)
        share = {k: 0.0 for k in pop}     # growth: matter moved reservoir -> individual (internal)
        res_delta = 0.0
        if gain >= 0.0:
            res_delta += gain
        elif n > 0:
            each = -gain / n
            for k in pop:
                loss[k] = min(each, have[k])
        avail = reservoir + res_delta
        if n > 0 and n < int(c["max_population"]) and avail > 0.0:
            s_each = min(avail / n, float(c["uptake_cap"]))
            for k in pop:
                share[k] = s_each
        dm = max(float(c["division_mass"]), 1e-300)
        floor = float(c["min_matter"])
        gone, removed, deltas = [], 0.0, {}
        for k, ind in pop.items():
            d = share[k] - loss[k]
            if have[k] + d < floor:
                # starved below the viable floor: the _remove rewrite takes the individual
                # with the matter it holds NOW; its loss and share this tick do not happen
                gone.append(k)
                removed += have[k]
                loss[k] = 0.0
                share[k] = 0.0
                continue
            target = (have[k] + d) / dm
            cur = float(ind.get("division_state", 0.0))
            if d != 0.0 or target != cur:
                deltas[k] = {"internal_amounts": {"carbon": d}, "division_state": target - cur}
        res_delta -= sum(share.values())
        external = (gain if gain >= 0.0 else 0.0) - sum(loss.values())
        alive = n - len(gone)
        out = {"external_flux": external, "survivors": min(alive / max(int(c["n_initial"]), 1), 1.0),
               "n_alive": float(alive), "reservoir": max(reservoir + res_delta, 0.0),
               "extinct": float(len(gone)), "removed_matter": removed}
        if deltas or gone:
            out["population"] = dict(deltas)
            if gone:
                out["population"]["_remove"] = gone
        if res_delta != 0.0:
            out["localized"] = {"carbon": res_delta}
        return out


# --------------------------------------------------------------------------- #
# The structural-event log
# --------------------------------------------------------------------------- #
class StructuralEventLogStep(Step):
    """Record every structural transition of the integrated world as an event:
    heredity attachment / detachment, the store charging past half / collapsing,
    the work and material budgets changing sign, divisions, extinctions, the
    loss of machinery and the lineage's extinction. The ablation step logs its
    own phases into the same tree."""

    config_schema = {"store_threshold": _p(0.5), "machinery_floor": _p(0.05)}

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._last_time = None
        self._n = 0
        self._prev = None

    def inputs(self):
        return {"global_time": "float", "attached": _DIMLESS, "energy_charge_fraction": _DIMLESS, "energy_ok": _DIMLESS,
                "material_ok": _DIMLESS, "division_count": "float", "extinct": "float", "n_alive": _DIMLESS,
                "machinery": _DIMLESS}

    def outputs(self):
        return {"events": "tree", "event_count": _OW}

    def perform_update(self, state) -> bool:
        t = state.get("global_time")
        if t == self._last_time:
            return False
        self._last_time = t
        return True

    def _ev(self, t, kind, detail=""):
        self._n += 1
        return (f"s{self._n:04d}", {"t": float(t), "kind": kind, "detail": detail, "source": "world"})

    def update(self, state):
        t = float(state.get("global_time", 0.0))
        cur = {"attached": float(state.get("attached", 0.0)) >= 0.5,
               "charged": float(state.get("energy_charge_fraction", 0.0)) >= float(self.config["store_threshold"]),
               "energy_ok": float(state.get("energy_ok", 1.0)) >= 0.5,
               "material_ok": float(state.get("material_ok", 1.0)) >= 0.5,
               "alive": float(state.get("n_alive", 0.0)) > 0.0,
               "machinery": float(state.get("machinery", 0.0)) >= float(self.config["machinery_floor"])}
        events = {}
        if self._prev is not None:
            p = self._prev
            flips = [("attached", "heredity_attached", "heredity_detached"), ("charged", "store_charged", "store_collapsed"),
                     ("energy_ok", "energy_surplus_restored", "energy_deficit_begins"),
                     ("material_ok", "material_surplus_restored", "material_deficit_begins"),
                     ("machinery", "machinery_held", "machinery_lost"), ("alive", "lineage_revived", "lineage_extinct")]
            for key, up, down in flips:
                if cur[key] != p[key]:
                    k, v = self._ev(t, up if cur[key] else down)
                    events[k] = v
        div = float(state.get("division_count", 0.0))
        ext = float(state.get("extinct", 0.0))
        if div > 0:
            k, v = self._ev(t, "division", f"{int(div)} individual(s) divided (_divide)")
            events[k] = v
        if ext > 0:
            k, v = self._ev(t, "extinction", f"{int(ext)} individual(s) removed (_remove)")
            events[k] = v
        self._prev = cur
        out = {"event_count": float(self._n)}
        if events:
            out["events"] = events
        return out


__all__ = ["AblationStep", "GeologicalDriverStep", "EnrichmentAdapterStep", "LineageStateProcess", "ActiveImportProcess",
           "MaintenanceDemandProcess", "LineageSupplyProcess", "AutonomyBudgetStep", "PopulationBudgetProcess",
           "StructuralEventLogStep", "INNOVATIONS", "MAINTENANCE_LAWS", "DRIVERS",
           "pmf_from_delta_ph"]
