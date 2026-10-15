"""The integrated autonomy world — og-08 re-run inside ONE persistent world (Phase 9).

One layer generator assembling the merged phases around a single lineage
(``viva_genesis.autonomy.integrated`` for the Phase-9 steps):

* **geology** — the reduced ``serpentinization`` class at the Phase-1 posterior
  draw's (T, flow, olivine extent) under the Phase-1 ``ConservationLedgerProcess``;
* **interface** — the Butler–Volmer ``carbon_fixation`` class (Phase 2) under
  the ``ChargeLedgerProcess``, making the organic feed from the draw's H2 and
  pH contrast on the mineral catalyst;
* **pore** — a ``localization`` class (``model_localization``: the *transport
  law*) shaping the feed; the Phase-8 ``SpatialCouplingStep`` firing the
  exchange rules under the ``EcologyElementLedgerProcess`` and the Phase-3
  ``NetworkLedgerProcess`` over the cell;
* **cell** — one protocell running the Phase-3 universe (``proto_ecology``
  face); an ``energy_coupling`` class (``model_energy_coupling``: the *storage
  model*) as its power budget under the ``FreeEnergyLedgerProcess``; a
  ``boundary`` class (``model_boundary``: the *permeability assumption*) whose
  leakiness relative to the fatty-acid vesicle scales the H+ leak and the
  exchange permeabilities; a ``heredity`` class (``model_heredity``: the
  *inheritance class*) as the lineage's machinery under the
  ``InformationLedgerProcess``; ``maintenance_law`` (the *maintenance function*);
* **population** — individuals fed by the lineage budget, dividing and going
  extinct by the Phase-5 ``_divide`` / ``_remove`` rewrites under the
  ``RewriteLedgerProcess``;
* ``AblationStep`` withdrawing the gradient, the mineral access and the feed
  toward their ocean floors at ``ablation_start`` over ``ablation_duration``,
  ``StructuralEventLogStep`` recording every structural event, and
  ``AutonomyBudgetStep`` publishing the co-limited budget and the autonomy
  decomposition.

The three og-08 innovations are ``pump`` (``coupling_activity`` 1 | 0 on the
storage class), ``importer`` (the ``ActiveUptakeRule`` fired | not) and
``heredity`` (attachment decided by the ``HeredityAttachmentStep`` | forced
off — og-06's non-heritable control). ``environment = "generic"`` is the og-adv
reject control (every driver at its floor from t = 0, no pore concentration).
Seven ledgers run beside the world: conservation (geology), charge (interface),
network and ecology (the cell and its pore), free-energy (the storage class),
information (the inheritance class) and rewrite (the population).
"""

from __future__ import annotations

import math

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from .. import models
from ..autonomy.integrated import INNOVATIONS, MAINTENANCE_LAWS, pmf_from_delta_ph
from ..ecology.proto_ecology import DEFAULT_PERMEABILITY, PERMEABILITY_CLASSES, field_species, function_names
from ..heredity.competing import DEFAULTS as HEREDITY_DEFAULTS, POOLS
from ..ledger import (CHARGE_LEDGER_KEYS, ECOLOGY_LEDGER_KEYS, FREE_ENERGY_LEDGER_KEYS, INFORMATION_LEDGER_KEYS,
                      LEDGER_KEYS, NETWORK_LEDGER_KEYS, REWRITE_LEDGER_KEYS)
from ..multisolute_localization import _default_species_params
from ..protometabolism import universe as U

_BUDGET_PORTS = ("free_energy_in", "external_power", "internal_power", "maintenance_power", "work", "dissipated",
                 "leak_power", "net_power", "energy_stored", "autonomy", "energy_charge_fraction", "store_potential")
_AGENT_SCALARS = ("net_carbon_flux", "h2_consumption", "co2_fixation", "dissipation", "element_residual",
                  "carbon_degraded", "total_organic_carbon", "n_persistent_species", "catalyst_saturation")
_SENSORS = ("mean_function", "functional_fraction", "population", "lineage_depth", "heritability", "fidelity",
            "mutation_rate", "mean_molecules", "n_attached")
_INFO = ("information_content", "information_capacity", "mi_converged", "mi_standard_error")
_COSTS = ("replication_energy", "quanta_used", "precursors_consumed", "precursor_energy", "copies", "births")
_ATTACH = ("attached", "attachment_margin", "fidelity_floor")
_LINEAGE = ("machinery", "catalysis_total", "catalysis_internal", "drive_availability", "substrate_availability",
            "autonomy_information")
_AUTONOMY = ("work_supply", "work_demand", "heredity_power", "net_power", "passive_carbon", "active_carbon",
             "fixation_carbon", "degradation_carbon", "material_supply", "material_net", "autonomy_work",
             "autonomy_material", "autonomy_information", "autonomy", "lineage_fitness", "energy_ok", "material_ok")
_HEREDITY_RATES = ("base_growth_rate", "k_replicate", "k_degrade", "k_denovo", "k_incorporate", "k_release",
                   "k_autocatalysis", "k_spontaneous", "k_layer", "k_dissolve")
_STORAGE_CLASSES = ("h_na_gradient_leaky_membrane", "thioester_acyl_phosphate", "polyphosphate", "fe_redox")
# The permeability assumption's second factor: the Phase-8 charged-solute classes
# (extrapolated, 1e-7 / 1e-8 / 1e-10 m/s) or the measured passage of charged
# solutes through fatty-acid vesicles, ~3 decades tighter (the og-07-alt decision).
PERMEABILITY_ANCHORS = {"extrapolated": {}, "measured": {"p_monoacid": 1.0e-3, "p_diacid": 1.0e-3, "p_ion": 1.0e-3}}
_TRANSPORT_CLASSES = ("multisolute_surrogate", "surrogate", "fipy")

_EMIT = {
    # the drivers
    "gradient_support": ["env", "gradient_support"], "mineral_access": ["env", "mineral_access"],
    "feed_support": ["env", "feed_support"], "ablation_phase": ["env", "ablation_phase"],
    "electric_potential": ["env", "electric_potential"], "fixation_relative": ["env", "fixation_relative"],
    "net_carbon_flux": ["interface", "flux", "net_carbon_flux"],
    # the storage class's budget + the lineage state + the autonomy decomposition
    **{k: ["budget", k] for k in _BUDGET_PORTS if k != "maintenance_power"},
    "class_maintenance_power": ["budget", "maintenance_power"],
    "maintenance_power": ["maintenance", "maintenance_power"],
    **{k: ["lineage", k] for k in _LINEAGE},
    **{k: ["autonomy", k] for k in _AUTONOMY},
    "import_power": ["import", "import_power"], "active_uptake_carbon": ["import", "active_uptake_carbon"],
    "import_firings": ["import", "import_firings"],
    # the cell
    **{k: ["rates", "cell-0", k] for k in ("co2_fixation", "h2_consumption", "total_organic_carbon", "dissipation",
                                            "carbon_degraded", "n_persistent_species")},
    "exchange_firings_total": ["ledger_eco", "exchange_firings_total"],
    # heredity
    "attached": ["heredity", "attached"], "attachment_margin": ["heredity", "attachment_margin"],
    "mean_function": ["lineage_sensors", "mean_function"], "heredity_population": ["lineage_sensors", "population"],
    "information_content": ["info", "information_content"], "mi_converged": ["info", "mi_converged"],
    "stored_work": ["henergy", "stored_work"],
    # the population
    "survivors": ["stats", "survivors"], "n_alive": ["stats", "n_alive"], "max_generation": ["stats", "max_generation"],
    "reservoir": ["stats", "reservoir"], "event_count": ["stats", "event_count"],
    "division_count": ["diag", "division_count"], "extinct": ["diag", "extinct"],
    # the seven ledgers
    "geology_ledger_ok": ["ledger_geo", "ledger_ok"], "geology_mass_residual": ["ledger_geo", "H2_residual"],
    "charge_ledger_ok": ["ledger_charge", "charge_ledger_ok"], "charge_residual_max": ["ledger_charge", "charge_residual_max"],
    "network_ledger_ok": ["ledger_net", "ledger_ok"], "element_residual_max": ["ledger_net", "element_residual_max"],
    "free_energy_directionality": ["ledger_net", "free_energy_directionality"],
    "element_ledger_ok": ["ledger_eco", "element_ledger_ok"], "C_residual_max": ["ledger_eco", "C_residual_max"],
    "N_residual_max": ["ledger_eco", "N_residual_max"], "P_residual_max": ["ledger_eco", "P_residual_max"],
    "free_energy_ledger_ok": ["ledger_fe", "free_energy_ledger_ok"],
    "free_energy_residual_max": ["ledger_fe", "free_energy_residual_max"],
    "second_law_margin_min": ["ledger_fe", "second_law_margin_min"],
    "information_ledger_ok": ["ledger_info", "information_ledger_ok"], "energy_residual": ["ledger_info", "energy_residual"],
    "rewrite_ok": ["ledger_rw", "rewrite_ok"], "rewrite_residual_max": ["ledger_rw", "rewrite_residual_max"],
    "partition_residual_max": ["ledger_rw", "partition_residual_max"],
    "global_time": ["global_time"],
}
_EMIT_TREES = {"events": ["events"]}
_EMIT_PATHS = ["/".join(v) for v in {**_EMIT, **_EMIT_TREES}.values()]


def relative_leak(core, model_boundary: str, *, temperature: float, ph: float = 8.3, ionic_strength: float = 0.1,
                  max_relative_leak: float = 100.0) -> dict:
    """The ``boundary`` class's permeability relative to the single-chain
    fatty-acid vesicle at the same conditions, clipped to ``[1, max]`` — the
    one factor by which the H+ leak and the exchange permeabilities scale
    under the permeability assumption — plus the class's viability witness."""
    def _run(name):
        addr = models.resolve_checked(core, "boundary", name)
        cls = core.link_registry[addr.split(":", 1)[1]]
        proc = cls(config={}, core=core)
        state = {"pH": ph, "ionic_strength": ionic_strength, "temperature": temperature,
                 "mix_fraction": 0.4 if name == "mixed" else 0.0, "amphiphile": 5.0e-3}
        return proc.update(state, 1.0)
    ref = _run("single_chain")
    out = _run(model_boundary)
    rel = float(out["permeability"]) / max(float(ref["permeability"]), 1e-30)
    return {"relative_leak": min(max(rel, 1.0), float(max_relative_leak)), "permeability": float(out["permeability"]),
            "viable_compartments": float(out["viable_compartments"]), "reference_permeability": float(ref["permeability"])}


@composite_generator(
    name="integrated_autonomy_world",
    methods=["reduced serpentinization + conservation ledger", "Butler-Volmer carbon fixation + charge ledger",
             "localization class (transport law)", "Phase-3 universe in the cell (libRoadRunner) + network / C-N-P ledgers",
             "energy_coupling class (storage model) + free-energy ledger", "boundary class (permeability assumption)",
             "heredity class (Gillespie, inheritance class) + information ledger", "maintenance law",
             "active-uptake exchange rule (importer)", "population rewrites (_divide / _remove) + rewrite ledger",
             "scheduled ablation + structural-event log"],
    fidelity="real",
    description=(
        "og-08's off-gradient test inside ONE persistent world assembled from the merged phases: the lineage lives "
        "on what real processes deliver — the external pmf tapped through its membrane leak and an internal store "
        "charged by the drive its live substrate pool sustains (an energy_coupling class, the STORAGE MODEL), organic "
        "carbon reaching it through a localization class (the TRANSPORT LAW) and the Phase-8 exchange rules at a "
        "boundary class's leakiness (the PERMEABILITY ASSUMPTION), the Phase-3 universe inside it catalysed by the "
        "mineral surface or by the machinery its heredity class holds (the INHERITANCE CLASS), upkeep priced by a "
        "MAINTENANCE LAW, and a population of individuals that divide and go extinct by structural rewrites. An "
        "AblationStep withdraws the gradient, the mineral access and the feed; pump (coupling_activity), importer "
        "(the ActiveUptakeRule) and heredity (attachment) are the three innovations; environment=generic is the "
        "og-adv reject control. Seven ledgers run beside the world and a structural-event log records every event. "
        "The vent endmembers are one Phase-1 posterior draw (vg-data integrated_autonomy)."
    ),
    parameters={
        **models.model_parameters("energy_coupling", "heredity", "boundary", "localization",
                                  defaults={"energy_coupling": "thioester_acyl_phosphate", "heredity": "rna_like",
                                            "boundary": "single_chain", "localization": "multisolute_surrogate"}),
        "maintenance_law": {"type": "string", "default": "constant",
                            "description": "Maintenance function: constant (Phase 6) | leak_repair (scales with leakiness) | turnover (scales with machinery held)"},
        "pump": {"type": "string", "default": "on", "description": "Internal energy conversion: on | off (coupling_activity 1 | 0 on the storage class)"},
        "importer": {"type": "string", "default": "on", "description": "Active resource import: on | off (the ActiveUptakeRule fires | not)"},
        "heredity": {"type": "string", "default": "on", "description": "Information maintenance: on (HeredityAttachmentStep decides) | off (non-heritable control)"},
        "environment": {"type": "string", "default": "vent", "description": "vent | generic (og-adv reject control: every driver at its floor from t = 0, no pore concentration)"},
        "h2_vent": {"type": "float", "default": 1.08e-2, "description": "Dissolved H2 of the vent fluid (M) [vg-data: calibrated, Phase-1 posterior draw]"},
        "delta_ph": {"type": "float", "default": 3.5, "description": "Vent - ocean pH contrast [vg-data: calibrated, Phase-1 posterior draw]"},
        "temperature": {"type": "float", "default": 322.15, "description": "Vent fluid temperature (K) [vg-data: calibrated, Phase-1 posterior draw]"},
        "dic": {"type": "float", "default": 2.0e-3, "description": "Ocean DIC / CO2 (M), never withdrawn [vg-data: extrapolated]"},
        "flow_velocity": {"type": "float", "default": 3.0e-3, "description": "Vent flow through the reaction zone (m/s) [vg-data: Phase-1 posterior draw]"},
        "olivine_rate": {"type": "float", "default": 0.2, "description": "Serpentinization extent of the geology layer [vg-data: Phase-1 posterior draw]"},
        "ph_ocean": {"type": "float", "default": 6.0, "description": "Ocean-side pH [vg-data: extrapolated]"},
        "ablation_start": {"type": "float", "default": 3600.0, "description": "World time at which withdrawal begins (s)"},
        "ablation_duration": {"type": "float", "default": 6000.0, "description": "Duration of the linear withdrawal (s)"},
        "feed_floor": {"type": "float", "default": 1.0e-2, "description": "Ocean floor of the feed fraction (H2, organics, N, P) [vg-data: hypothetical, swept]"},
        "gradient_floor": {"type": "float", "default": 0.0, "description": "Ocean floor of the gradient fraction"},
        "mineral_floor": {"type": "float", "default": 0.0, "description": "Ocean floor of the mineral access"},
        "tick_seconds": {"type": "float", "default": 60.0, "description": "World seconds per tick (every process runs at this interval)"},
        "heredity_clock_ratio": {"type": "float", "default": 1.0 / 60.0, "description": "Lineage-time units of the heredity class per world second (one per tick) [vg-data: hypothetical]"},
        "coupling_activity": {"type": "float", "default": 1.0, "description": "Storage-class coupling activity when the pump is on [vg-data: hypothetical]"},
        "permeability_reference": {"type": "float", "default": 1.0e-6, "description": "H+ permeability of the fatty-acid reference membrane (m/s) [vg-data: extrapolated]"},
        "max_relative_leak": {"type": "float", "default": 100.0, "description": "Cap on a boundary class's leakiness relative to the fatty-acid vesicle [vg-data: hypothetical]"},
        "v_max_import": {"type": "float", "default": 1.0e-19, "description": "Importer capacity per substrate at full machinery (mol/s; ~6e4 molecules/s) [vg-data: hypothetical]"},
        "k_m_import": {"type": "float", "default": 1.0e-6, "description": "Importer half-saturation (M) [vg-data: hypothetical]"},
        "import_ratio_cap": {"type": "float", "default": 100.0, "description": "Inside / outside ratio at which the importer stops [vg-data: hypothetical]"},
        "import_setpoint": {"type": "float", "default": 0.1, "description": "The importer holds each substrate at this fraction of its in-vent level [vg-data: hypothetical]"},
        "import_budget_fraction": {"type": "float", "default": 0.3, "description": "Share of the lineage's work the importer may spend per tick [vg-data: hypothetical]"},
        "permeability_anchor": {"type": "string", "default": "extrapolated", "description": "Charged-solute exchange permeabilities: extrapolated (Phase-8 classes) | measured (1000x tighter: the fatty-acid-vesicle charged-solute anchor, og-07-alt decision)"},
        "k_org": {"type": "float", "default": 1.0e-5, "description": "Drive half-saturation on the cell's organic substrate (M) [vg-data: hypothetical]"},
        "k_h2": {"type": "float", "default": 1.0e-5, "description": "Drive half-saturation on the cell's H2 (M; hydrogenase-like affinity) [vg-data: hypothetical]"},
        "function_reference": {"type": "float", "default": 0.25, "description": "Heredity-class mean function at which the lineage holds its full machinery [vg-data: hypothetical]"},
        "heredity_allocation": {"type": "float", "default": 0.05, "description": "Share of the lineage's work allocated to heredity [vg-data: hypothetical]"},
        "k_wash": {"type": "float", "default": 0.01, "description": "Pore feed / washout rate (1/s) [vg-data: inferred, Phase-8 canonical]"},
        "peclet": {"type": "float", "default": 8.0, "description": "Control Peclet of the multisolute transport class [Phase-8 operating point]"},
        "pore_flow_velocity": {"type": "float", "default": 1.0e-5, "description": "Flow of the single-tracer transport classes (m/s): accumulation Peclet ~1.8, inside og-03's resolvable range"},
        "feed_pyruvate": {"type": "float", "default": 1.0e-4, "description": "Organic feed the vent delivers at full support (M) [vg-data: inferred]"},
        "n_initial": {"type": "integer", "default": 8, "description": "Founding individuals of the population"},
        "protocell_radius": {"type": "float", "default": 5.0e-7, "description": "Protocell radius (m): the cell's volume, membrane area and A/V [vg-data: inferred, Phase 6]"},
        "seed": {"type": "integer", "default": 1, "description": "Heredity-class RNG seed"},
    },
    default_n_steps=14400,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def integrated_autonomy_world(core=None, *, model_energy_coupling="thioester_acyl_phosphate", model_heredity="rna_like",
                              model_boundary="single_chain", model_localization="multisolute_surrogate",
                              maintenance_law="constant", pump="on", importer="on", heredity="on", environment="vent",
                              h2_vent=1.08e-2, delta_ph=3.5, temperature=322.15, dic=2.0e-3, flow_velocity=3.0e-3,
                              olivine_rate=0.2, ph_ocean=6.0, ablation_start=3600.0, ablation_duration=6000.0,
                              feed_floor=1.0e-2, gradient_floor=0.0, mineral_floor=0.0, tick_seconds=60.0,
                              heredity_clock_ratio=1.0 / 60.0, coupling_activity=1.0, permeability_reference=1.0e-6,
                              max_relative_leak=100.0, v_max_import=1.0e-19, k_m_import=1.0e-6, import_ratio_cap=100.0,
                              import_setpoint=0.1, import_budget_fraction=0.3, permeability_anchor="extrapolated",
                              k_org=1.0e-5, k_h2=1.0e-5, function_reference=0.25, heredity_allocation=0.05, k_wash=0.01, peclet=8.0,
                              pore_flow_velocity=1.0e-5, feed_pyruvate=1.0e-4, n_initial=8, protocell_radius=5.0e-7,
                              seed=1):
    if core is None:
        core = build_core()
    if model_energy_coupling not in _STORAGE_CLASSES:
        raise ValueError(f"model_energy_coupling must be a storage class {_STORAGE_CLASSES} (passive_gradient is the "
                         f"pump knockout, pump='off'), got {model_energy_coupling!r}")
    if model_localization not in _TRANSPORT_CLASSES:
        raise ValueError(f"model_localization must be one of {_TRANSPORT_CLASSES}, got {model_localization!r}")
    if maintenance_law not in MAINTENANCE_LAWS:
        raise ValueError(f"maintenance_law must be one of {MAINTENANCE_LAWS}, got {maintenance_law!r}")
    for name, val in (("pump", pump), ("importer", importer), ("heredity", heredity)):
        if str(val).lower() not in ("on", "off"):
            raise ValueError(f"{name} must be 'on' | 'off', got {val!r}")
    if environment not in ("vent", "generic"):
        raise ValueError(f"environment must be vent | generic, got {environment!r}")
    if permeability_anchor not in PERMEABILITY_ANCHORS:
        raise ValueError(f"permeability_anchor must be one of {tuple(PERMEABILITY_ANCHORS)}, got {permeability_anchor!r}")
    energy_addr = models.resolve_checked(core, "energy_coupling", model_energy_coupling)
    heredity_addr = models.resolve_checked(core, "heredity", model_heredity)
    boundary_addr = models.resolve_checked(core, "boundary", model_boundary)
    loc_addr = models.resolve_checked(core, "localization", model_localization)
    net_addr = models.resolve_checked(core, "proto_ecology", "reaction_universe")
    serp_addr = models.resolve_checked(core, "serpentinization", "reduced")
    fix_addr = models.resolve_checked(core, "carbon_fixation", "butler_volmer")

    dt = float(tick_seconds)
    T = float(temperature)
    generic = environment == "generic"
    pump_on, importer_on, heredity_on = (str(v).lower() == "on" for v in (pump, importer, heredity))

    # the permeability assumption: the boundary class's leakiness relative to the fatty-acid vesicle
    leak = relative_leak(core, model_boundary, temperature=T, max_relative_leak=float(max_relative_leak))
    rel = leak["relative_leak"]
    anchor = PERMEABILITY_ANCHORS[permeability_anchor]
    perm = {p: DEFAULT_PERMEABILITY[p] * rel * anchor.get(p, 1.0) for p in PERMEABILITY_CLASSES}

    # the cell and its pore: the Phase-6 individual (radius protocell_radius) carries the
    # Phase-8 chemistry and exchange (k = P A / V with A / V = 3 / r)
    r_agent = float(protocell_radius)
    v_agent = (4.0 / 3.0) * math.pi * r_agent ** 3 * 1.0e3        # liter
    area = 4.0 * math.pi * r_agent ** 2                            # m^2
    area_per_volume = 3.0 / r_agent                                # 1/m
    cell_volume = 10.0 * v_agent
    species = field_species(4)
    zero = {s: 0.0 for s in species}
    h2_pore = float(h2_vent) * (float(feed_floor) if generic else 1.0)
    feed0 = {U.CO2: float(dic), U.H2: h2_pore, "X_AKM": float(feed_pyruvate) * (float(feed_floor) if generic else 1.0), "X_A": 0.0,
             "ammonium": 5.0e-5, "phosphate": 1.0e-5}
    sp = _default_species_params()
    pmf0 = pmf_from_delta_ph(float(delta_ph), T) * (float(gradient_floor) if generic else 1.0)

    # the heredity class's clock: lineage-time units per world second
    ratio = float(heredity_clock_ratio)
    class_cfg = {"seed": int(seed), "n_individuals": int(HEREDITY_DEFAULTS["n_individuals"]),
                 **{k: float(HEREDITY_DEFAULTS[k]) * ratio for k in _HEREDITY_RATES}}
    attach_cfg = {"heredity_class": model_heredity, "n_individuals": int(HEREDITY_DEFAULTS["n_individuals"]),
                  **{k: float(HEREDITY_DEFAULTS[k]) * ratio for k in _HEREDITY_RATES}}
    w0 = 8.0e-16

    # the population: founders at half the division mass (the cell's organic carbon at 1 mM C)
    division_mass = 1.0e-3 * v_agent
    population = {f"ind-{i}": {"id": f"ind-{i}", "volume": v_agent, "internal_amounts": {"carbon": 0.5 * division_mass},
                               "boundary": {"area": area, "integrity": 1.0}, "division_state": 0.5, "persistence": 0.0}
                  for i in range(int(n_initial))}

    energy_cfg = {"drive_turnover": 1.0e-21, "maintenance_active": 5.0e-18, "seconds_per_tick": 1.0}
    if pump_on:
        energy_cfg["coupling_activity"] = float(coupling_activity)   # 0.0 is the class default (the knockout)

    doc = {
        # ---- the ablation schedule and the drivers ---------------------------------------------
        "ablation": {
            "_type": "step", "address": "local:AblationStep",
            "config": {"start": float(ablation_start), "duration": float(ablation_duration),
                       "gradient_floor": float(gradient_floor), "mineral_floor": float(mineral_floor),
                       "feed_floor": float(feed_floor), "environment": environment},
            "inputs": {"global_time": ["global_time"]},
            "outputs": {"gradient_support": ["env", "gradient_support"], "mineral_access": ["env", "mineral_access"],
                        "feed_support": ["env", "feed_support"], "ablation_phase": ["env", "ablation_phase"],
                        "events": ["events"]},
        },
        "drivers": {
            "_type": "step", "address": "local:GeologicalDriverStep",
            "config": {"h2_vent": float(h2_vent), "h2_ocean": 0.0, "delta_ph": float(delta_ph), "ph_ocean": float(ph_ocean),
                       "temperature": T, "dic": float(dic), "feed_pyruvate": float(feed_pyruvate),
                       "feed_floor": float(feed_floor), "ablation_start": float(ablation_start)},
            "inputs": {"gradient_support": ["env", "gradient_support"], "mineral_access": ["env", "mineral_access"],
                       "feed_support": ["env", "feed_support"], "net_carbon_flux": ["interface", "flux", "net_carbon_flux"],
                       "global_time": ["global_time"]},
            "outputs": {"electric_potential": ["env", "electric_potential"], "pH_vent": ["env", "pH_vent"],
                        "catalyst_activity": ["catalyst", "active"], "H2": ["interface", "env", "H2"],
                        "feed": ["pore", "feed"], "fixation_relative": ["env", "fixation_relative"]},
        },
        # ---- geology: the vent under its conservation ledger -----------------------------------
        "serpentinization": {
            "_type": "process", "address": serp_addr, "interval": dt,
            "config": {"h2_rate_max": 1.0e-3 * float(olivine_rate) / 0.15},
            "inputs": {"temperature": ["geo", "temperature"], "flow_velocity": ["geo", "flow_velocity"]},
            "outputs": {"H2": ["geo", "H2"], "alkalinity": ["geo", "alkalinity"], "heat": ["geo", "heat"],
                        "H2_flux": ["geo", "rates", "H2_flux"], "alkalinity_flux": ["geo", "rates", "alkalinity_flux"],
                        "heat_flux": ["geo", "rates", "heat_flux"]},
        },
        "conservation_ledger": {
            "_type": "process", "address": "local:ConservationLedgerProcess", "config": {}, "interval": dt,
            "inputs": {"H2": ["geo", "H2"], "alkalinity": ["geo", "alkalinity"], "heat": ["geo", "heat"],
                       "H2_flux": ["geo", "rates", "H2_flux"], "alkalinity_flux": ["geo", "rates", "alkalinity_flux"],
                       "heat_flux": ["geo", "rates", "heat_flux"], "charge_imbalance": ["geo", "charge_imbalance"],
                       "flux_divergence_residual": ["geo", "flux_divergence_residual"]},
            "outputs": {k: ["ledger_geo", k] for k in LEDGER_KEYS},
        },
        # ---- interface: carbon fixation under the charge ledger ---------------------------------
        "fixation": {
            "_type": "process", "address": fix_addr, "interval": dt,
            "config": {"dilution_rate": 1.0e-3},
            "inputs": {"H2": ["interface", "env", "H2"], "CO2": ["interface", "env", "CO2"], "temperature": ["env", "temperature"],
                       "pH_vent": ["env", "pH_vent"], "pH_ocean": ["env", "pH_ocean"], "catalyst_activity": ["catalyst", "active"],
                       "ni_fraction": ["minerals", "ni_fraction"], "conductivity": ["minerals", "conductivity"],
                       "layer_thickness": ["minerals", "layer_thickness"], "porosity": ["minerals", "porosity"],
                       "ionic_strength": ["env", "ionic_strength"],
                       **{p: ["interface", "products", p] for p in ("formate", "acetate", "pyruvate")}},
            "outputs": {**{p: ["interface", "products", p] for p in ("formate", "acetate", "pyruvate")},
                        "net_carbon_flux": ["interface", "flux", "net_carbon_flux"],
                        **{k: ["interface", "electro", k] for k in ("current_density", "emf", "overpotential", "faradaic_efficiency",
                                                                    "electron_flux", "carbon_electron_flux", "her_electron_flux",
                                                                    "iv_residual")},
                        **{k: ["interface", "diagnostics", k] for k in ("loss_thermodynamic", "loss_electrical", "loss_catalytic",
                                                                        "loss_transport", "limitation_code")}},
        },
        "charge_ledger": {
            "_type": "process", "address": "local:ChargeLedgerProcess", "config": {}, "interval": dt,
            "inputs": {k: ["interface", "electro", k] for k in ("electron_flux", "carbon_electron_flux", "her_electron_flux", "iv_residual")},
            "outputs": {k: ["ledger_charge", k] for k in CHARGE_LEDGER_KEYS},
        },
        # ---- the pore: the transport law ---------------------------------------------------------
        "localization": {
            "_type": "process", "address": loc_addr, "interval": dt,
            "config": ({"peclet": (1.0e3 if generic else float(peclet)), "species_params": sp}
                       if model_localization == "multisolute_surrogate" else ({"nz": 40} if model_localization == "fipy" else {})),
            "inputs": {"temperature": ["pore", "temperature"], "porosity": ["pore", "porosity"],
                       "flow_velocity": ["pore", "flow_velocity"],
                       **({"species_params": ["pore", "species_params"]} if model_localization == "multisolute_surrogate" else {})},
            "outputs": ({"enrichment": ["pore", "enrichment"], "flux_divergence_residual": ["pore", "flux_residual"]}
                        if model_localization == "multisolute_surrogate" else
                        {"enrichment_factor": ["pore", "enrichment_factor"], "flux_divergence_residual": ["pore", "flux_residual"]}),
        },
        # ---- the cell: the Phase-3 universe inside the protocell ----------------------------------
        "network_cell-0": {
            "_type": "process", "address": net_addr, "interval": dt,
            "config": {"lineage": "generalist", "volume": v_agent},
            "inputs": {"internal": ["agents", "cell-0", "internal", "dissolved"], "catalyst_activity": ["lineage", "catalysis_total"]},
            "outputs": {"internal": ["agents", "cell-0", "internal", "dissolved"],
                        "functions_produced": ["metabolism", "cell-0", "functions_produced"],
                        "rule_flux": ["metabolism", "cell-0", "rule_flux"],
                        **{k: ["rates", "cell-0", k] for k in _AGENT_SCALARS}},
        },
        "coupling": {
            "_type": "step", "address": "local:SpatialCouplingStep",
            "config": {"n_cells": 1, "cell_volume": cell_volume, "dt": dt, "k_wash": float(k_wash), "k_diffusion": 0.0,
                       "coupling": "shared", "feed": feed0, "area_per_volume": area_per_volume, **perm},
            "inputs": {"agents": ["agents"], "lineages": ["lineages"], "field": ["field", "cells"],
                       "enrichment": ["pore", "enrichment"], "global_time": ["global_time"], "feed": ["pore", "feed"]},
            "outputs": {"agents": ["agents"], "field": ["field", "cells"], "firings": ["exchange", "firings"],
                        "firing_moles": ["exchange", "firing_moles"], "cross_lineage_flux": ["exchange", "cross_lineage_flux"],
                        "cross_lineage_flux_total": ["exchange", "cross_lineage_flux_total"],
                        "inflow": ["exchange", "inflow"], "outflow": ["exchange", "outflow"], "exchange": ["exchange", "exchange"]},
        },
        "active_import": {
            "_type": "process", "address": "local:ActiveImportProcess", "interval": dt,
            "config": {"importer": "on" if importer_on else "off", "v_max": float(v_max_import), "k_m": float(k_m_import),
                       "max_ratio": float(import_ratio_cap), "budget_fraction": float(import_budget_fraction),
                       "targets": {U.H2: float(import_setpoint) * float(h2_vent), "X_AKM": float(import_setpoint) * float(feed_pyruvate),
                                   "X_A": float(import_setpoint) * float(feed_pyruvate), "X_AM": float(import_setpoint) * float(feed_pyruvate)},
                       "temperature": T, "n_cells": 1, "cell_volume": cell_volume},
            "inputs": {"agents": ["agents"], "lineages": ["lineages"], "field": ["field", "cells"],
                       "machinery": ["lineage", "machinery"], "work_supply": ["autonomy", "work_supply"]},
            "outputs": {"agents": ["agents"], "field": ["field", "cells"], "active_uptake": ["import", "active_uptake"],
                        "active_uptake_carbon": ["import", "active_uptake_carbon"], "import_power": ["import", "import_power"],
                        "import_firings": ["import", "import_firings"], "import_moles": ["import", "import_moles"]},
        },
        "element_ledger": {
            "_type": "process", "address": "local:EcologyElementLedgerProcess", "interval": dt,
            "config": {"cell_volume": cell_volume},
            "inputs": {"agents": ["agents"], "field": ["field", "cells"], "inflow": ["exchange", "inflow"],
                       "outflow": ["exchange", "outflow"], "rates": ["rates"], "firings": ["exchange", "firings"]},
            "outputs": {k: ["ledger_eco", k] for k in ECOLOGY_LEDGER_KEYS},
        },
        "network_ledger": {
            "_type": "process", "address": "local:NetworkLedgerProcess", "config": {}, "interval": dt,
            "inputs": {"element_residual": ["rates", "cell-0", "element_residual"], "carbon_residual": ["ledger_eco", "C_residual"],
                       "dissipation": ["rates", "cell-0", "dissipation"], "total_organic_carbon": ["rates", "cell-0", "total_organic_carbon"]},
            "outputs": {k: ["ledger_net", k] for k in NETWORK_LEDGER_KEYS},
        },
        # ---- the boundary class (witness) ----------------------------------------------------------
        "boundary_class": {
            "_type": "process", "address": boundary_addr, "config": {}, "interval": dt,
            "inputs": {"pH": ["boundary", "pH"], "ionic_strength": ["boundary", "ionic_strength"], "temperature": ["env", "temperature"],
                       **({"amphiphile": ["boundary", "amphiphile"]} if model_boundary == "thioester_aminothiol"
                          else {"mix_fraction": ["boundary", "mix_fraction"]})},
            "outputs": {"membrane_area": ["boundary", "class_membrane_area"], "permeability": ["boundary", "class_permeability"],
                        "compartment_volume": ["boundary", "class_compartment_volume"],
                        "viable_compartments": ["boundary", "viable_compartments"], "retention": ["boundary", "retention"],
                        "access": ["boundary", "access"], "individuality_access": ["boundary", "individuality_access"]},
        },
        # ---- the storage model: the cell's power budget under the free-energy ledger ---------------
        "energy": {
            "_type": "process", "address": energy_addr, "config": energy_cfg, "interval": dt,
            "inputs": {"electric_potential": ["env", "electric_potential"],
                       "drive_free_energy": ["env", "drive_fe_redox" if model_energy_coupling == "fe_redox" else "drive_chemical"],
                       "permeability": ["boundary", "leak_permeability"], "membrane_area": ["individual", "membrane_area"],
                       "compartment_volume": ["individual", "compartment_volume"], "temperature": ["env", "temperature"],
                       "catalyst_activity": ["env", "unity"], "drive_availability": ["lineage", "drive_availability"]},
            "outputs": {**{p: ["budget", p] for p in _BUDGET_PORTS},
                        **({"pmf": ["budget", "pmf"]} if model_energy_coupling == "h_na_gradient_leaky_membrane" else {})},
        },
        "free_energy_ledger": {
            "_type": "process", "address": "local:FreeEnergyLedgerProcess", "config": {"seconds_per_tick": 1.0}, "interval": dt,
            "inputs": {"free_energy_in": ["budget", "free_energy_in"], "work": ["budget", "work"],
                       "dissipated": ["budget", "dissipated"], "energy_stored": ["budget", "energy_stored"]},
            "outputs": {k: ["ledger_fe", k] for k in FREE_ENERGY_LEDGER_KEYS},
        },
        "maintenance_demand": {
            "_type": "process", "address": "local:MaintenanceDemandProcess", "interval": dt,
            "config": {"law": maintenance_law, "pump": "on" if pump_on else "off"},
            "inputs": {"machinery": ["lineage", "machinery"], "relative_leak": ["boundary", "relative_leak"]},
            "outputs": {"maintenance_power": ["maintenance", "maintenance_power"]},
        },
        # ---- the inheritance class: the lineage's machinery under the information ledger -----------
        "heredity_class": {
            "_type": "process", "address": heredity_addr, "config": class_cfg, "interval": dt,
            "inputs": {"temperature": ["env", "temperature"], "attached": ["heredity", "attached"],
                       "stored_work": ["henergy", "stored_work"], **{p: ["pool", p] for p in POOLS}},
            "outputs": {**{p: ["pool", p] for p in POOLS}, "stored_work": ["henergy", "stored_work"],
                        **{k: ["lineage_sensors", k] for k in _SENSORS}, **{k: ["info", k] for k in _INFO},
                        **{k: ["cost", k] for k in _COSTS}},
        },
        "lineage_supply": {
            "_type": "process", "address": "local:LineageSupplyProcess", "interval": dt,
            "config": {"allocation": float(heredity_allocation), "n_individuals": int(HEREDITY_DEFAULTS["n_individuals"]),
                       "max_stored_work": w0},
            "inputs": {"work": ["budget", "work"], "total_organic_carbon": ["rates", "cell-0", "total_organic_carbon"],
                       "stored_work": ["henergy", "stored_work"], **{p: ["pool", p] for p in POOLS}},
            "outputs": {**{p: ["pool", p] for p in POOLS}, "stored_work": ["henergy", "stored_work"],
                        "work_flux": ["henergy", "work_flux"]},
        },
        "information_ledger": {
            "_type": "process", "address": "local:InformationLedgerProcess", "config": {}, "interval": dt,
            "inputs": {"information_content": ["info", "information_content"], "mi_converged": ["info", "mi_converged"],
                       "replication_energy": ["cost", "replication_energy"], "precursor_energy": ["cost", "precursor_energy"],
                       "precursors_consumed": ["cost", "precursors_consumed"], "births": ["cost", "births"],
                       "stored_work": ["henergy", "stored_work"], "work_flux": ["henergy", "work_flux"]},
            "outputs": {k: ["ledger_info", k] for k in INFORMATION_LEDGER_KEYS},
        },
        "lineage_state": {
            "_type": "process", "address": "local:LineageStateProcess", "interval": dt,
            "config": {"function_reference": float(function_reference), "k_h2": float(k_h2), "k_org": float(k_org),
                       "heredity": "on" if heredity_on else "off"},
            "inputs": {"mean_function": ["lineage_sensors", "mean_function"], "mineral_access": ["env", "mineral_access"],
                       "internal": ["agents", "cell-0", "internal", "dissolved"]},
            "outputs": {k: ["lineage", k] for k in _LINEAGE},
        },
        # ---- the integrated budget and the autonomy decomposition ----------------------------------
        "autonomy_budget": {
            "_type": "step", "address": "local:AutonomyBudgetStep",
            "config": {"allocation": float(heredity_allocation), "dt": dt},
            "inputs": {"external_power": ["budget", "external_power"], "internal_power": ["budget", "internal_power"],
                       "maintenance_power": ["maintenance", "maintenance_power"], "import_power": ["import", "import_power"],
                       "exchange": ["exchange", "exchange"], "active_uptake_carbon": ["import", "active_uptake_carbon"],
                       "rates": ["rates"], "autonomy_information": ["lineage", "autonomy_information"],
                       "global_time": ["global_time"]},
            "outputs": {k: ["autonomy", k] for k in _AUTONOMY},
        },
        # ---- the population: real individuals under the rewrite ledger -----------------------------
        "population_budget": {
            "_type": "process", "address": "local:PopulationBudgetProcess", "interval": dt,
            "config": {"division_mass": division_mass, "uptake_cap": 0.2 * division_mass, "n_initial": int(n_initial),
                       "min_matter": 0.1 * division_mass},
            "inputs": {"population": ["population"], "localized": ["localized"], "net_power": ["autonomy", "net_power"],
                       "material_net": ["autonomy", "material_net"]},
            "outputs": {"population": ["population"], "localized": ["localized"], "external_flux": ["diag", "external_flux"],
                        "survivors": ["stats", "survivors"], "n_alive": ["stats", "n_alive"], "reservoir": ["stats", "reservoir"],
                        "extinct": ["diag", "extinct"], "removed_matter": ["diag", "rm"]},
        },
        "division": {
            "_type": "step", "address": "local:DivisionStep", "config": {},
            "inputs": {"agents": ["population"]},
            "outputs": {"agents": ["population"], "division_count": ["diag", "division_count"], "partition_residual": ["diag", "pr"]},
        },
        "rewrite_ledger": {
            "_type": "process", "address": "local:RewriteLedgerProcess", "config": {"tol": 1.0e-30}, "interval": dt,
            "inputs": {"agents": ["population"], "localized": ["localized"], "partition_residual": ["diag", "pr"],
                       "removed_matter": ["diag", "rm"], "external_flux": ["diag", "external_flux"]},
            "outputs": {k: ["ledger_rw", k] for k in REWRITE_LEDGER_KEYS},
        },
        "lineage_stats": {
            "_type": "process", "address": "local:LineageStatsProcess", "config": {}, "interval": dt,
            "inputs": {"agents": ["population"]},
            "outputs": {"n_agents": ["stats", "n_agents"], "max_generation": ["stats", "max_generation"],
                        "total_volume": ["stats", "total_volume"]},
        },
        "event_log": {
            "_type": "step", "address": "local:StructuralEventLogStep", "config": {},
            "inputs": {"global_time": ["global_time"], "attached": ["heredity", "attached"],
                       "energy_charge_fraction": ["budget", "energy_charge_fraction"], "energy_ok": ["autonomy", "energy_ok"],
                       "material_ok": ["autonomy", "material_ok"], "division_count": ["diag", "division_count"],
                       "extinct": ["diag", "extinct"], "n_alive": ["stats", "n_alive"], "machinery": ["lineage", "machinery"]},
            "outputs": {"events": ["events"], "event_count": ["stats", "event_count"]},
        },
        # ---- stores -----------------------------------------------------------------------------------
        "env": {"temperature": T, "pH_ocean": float(ph_ocean), "pH_vent": float(ph_ocean) + float(delta_ph) * (0.0 if generic else 1.0),
                "ionic_strength": 0.25, "electric_potential": pmf0, "drive_chemical": 50.0, "drive_fe_redox": 40.0, "unity": 1.0,
                "gradient_support": 0.0 if generic else 1.0, "mineral_access": 0.0 if generic else 1.0,
                "feed_support": float(feed_floor) if generic else 1.0, "ablation_phase": 0.0, "fixation_relative": 0.0},
        "geo": {"temperature": T, "flow_velocity": float(flow_velocity), "H2": 0.0, "alkalinity": 0.0, "heat": 0.0,
                "rates": {"H2_flux": 0.0, "alkalinity_flux": 0.0, "heat_flux": 0.0}, "charge_imbalance": 0.0,
                "flux_divergence_residual": 0.0},
        "catalyst": {"active": 1.0e-6 if generic else 1.0},
        "minerals": {"conductivity": 1.0e-3, "layer_thickness": 1.0e-3, "ni_fraction": 0.75, "porosity": 0.35},
        "interface": {"env": {"H2": h2_pore, "CO2": float(dic)}, "products": {"formate": 0.0, "acetate": 0.0, "pyruvate": 0.0},
                      "flux": {"net_carbon_flux": 0.0},
                      "electro": {k: 0.0 for k in ("current_density", "emf", "overpotential", "faradaic_efficiency", "electron_flux",
                                                   "carbon_electron_flux", "her_electron_flux", "iv_residual")},
                      "diagnostics": {k: 0.0 for k in ("loss_thermodynamic", "loss_electrical", "loss_catalytic", "loss_transport",
                                                       "limitation_code")}},
        "pore": {"temperature": 333.15, "porosity": (0.99 if generic else 0.3), "flow_velocity": float(pore_flow_velocity),
                 "species_params": sp, "enrichment": {}, "enrichment_factor": 1.0, "flux_residual": 0.0, "feed": dict(feed0)},
        "agents": {"cell-0": {"id": "cell-0", "volume": v_agent, "internal": {"dissolved": dict(zero)}}},
        "lineages": {"cell-0": {"lineage_id": "generalist", "parent_id": "", "generation": 0, "position": (0.5, 0.0), "population": 1}},
        "metabolism": {"cell-0": {"functions_produced": {f: 0.0 for f in function_names(4)}, "rule_flux": {r: 0.0 for r in U.RULES}}},
        "rates": {"cell-0": {k: 0.0 for k in _AGENT_SCALARS}},
        "field": {"cells": {"c0": dict(zero)}},
        "exchange": {"firings": {}, "firing_moles": {}, "cross_lineage_flux": {}, "cross_lineage_flux_total": 0.0,
                     "inflow": {}, "outflow": {}, "exchange": {}},
        "import": {"active_uptake": {}, "active_uptake_carbon": 0.0, "import_power": 0.0, "import_firings": 0.0, "import_moles": 0.0},
        "boundary": {"pH": 8.3, "ionic_strength": 0.1, "mix_fraction": 0.4 if model_boundary == "mixed" else 1.0e-9,
                     "amphiphile": 5.0e-3, "relative_leak": rel, "leak_permeability": float(permeability_reference) * rel,
                     "class_membrane_area": 0.0, "class_permeability": leak["permeability"], "class_compartment_volume": 0.0,
                     "viable_compartments": leak["viable_compartments"], "retention": 0.0, "access": 0.0, "individuality_access": 0.0},
        "individual": {"membrane_area": area, "compartment_volume": v_agent},
        "budget": {**{p: 0.0 for p in _BUDGET_PORTS}, "pmf": 0.0},
        "maintenance": {"maintenance_power": 0.0},
        "lineage": {k: 0.0 for k in _LINEAGE},
        "pool": {p: 0.1 * 1.0e-3 for p in POOLS},
        "henergy": {"stored_work": w0, "work_flux": 0.0},
        "heredity": {"attached": 0.0, "attachment_margin": 0.0, "fidelity_floor": 0.0},
        "lineage_sensors": {k: 0.0 for k in _SENSORS}, "info": {k: 0.0 for k in _INFO}, "cost": {k: 0.0 for k in _COSTS},
        "autonomy": {k: 0.0 for k in _AUTONOMY},
        "population": population, "localized": {"carbon": 0.0},
        "diag": {"external_flux": 0.0, "division_count": 0.0, "pr": 0.0, "extinct": 0.0, "rm": 0.0},
        "stats": {"survivors": 1.0, "n_alive": float(n_initial), "n_agents": float(n_initial), "max_generation": 0.0,
                  "total_volume": v_agent * int(n_initial), "reservoir": 0.0, "event_count": 0.0},
        "events": {},
        "ledger_geo": {**{k: 0.0 for k in LEDGER_KEYS}, "energy_directionality": 1.0, "ledger_ok": 1.0},
        "ledger_charge": {k: (1.0 if k == "charge_ledger_ok" else 0.0) for k in CHARGE_LEDGER_KEYS},
        "ledger_net": {**{k: 0.0 for k in NETWORK_LEDGER_KEYS}, "free_energy_directionality": 1.0, "ledger_ok": 1.0},
        "ledger_eco": {**{k: 0.0 for k in ECOLOGY_LEDGER_KEYS}, "element_ledger_ok": 1.0},
        "ledger_fe": {**{k: 0.0 for k in FREE_ENERGY_LEDGER_KEYS}, "free_energy_ledger_ok": 1.0},
        "ledger_info": {k: 0.0 for k in INFORMATION_LEDGER_KEYS},
        "ledger_rw": {**{k: 0.0 for k in REWRITE_LEDGER_KEYS}, "rewrite_ok": 1.0, "n_agents": float(n_initial)},
        "emitter": {
            "_type": "step", "address": "local:RAMEmitter",
            "config": {"emit": {**{k: "float" for k in _EMIT}, **{k: "tree" for k in _EMIT_TREES}}},
            "inputs": {k: list(v) for k, v in {**_EMIT, **_EMIT_TREES}.items()},
        },
    }
    if model_localization != "multisolute_surrogate":
        doc["enrichment_adapter"] = {
            "_type": "step", "address": "local:EnrichmentAdapterStep", "config": {},
            "inputs": {"enrichment_factor": ["pore", "enrichment_factor"]},
            "outputs": {"enrichment": ["pore", "enrichment"]},
        }
    if heredity_on:
        doc["heredity_attachment"] = {
            "_type": "step", "address": "local:HeredityAttachmentStep", "config": attach_cfg,
            "inputs": {**{p: ["pool", p] for p in POOLS}, "stored_work": ["henergy", "stored_work"]},
            "outputs": {k: ["heredity", k] for k in _ATTACH},
        }
    return doc


# --------------------------------------------------------------------------- #
# Reducers (module-level, picklable)
# --------------------------------------------------------------------------- #
LEDGER_FLAGS = ("geology_ledger_ok", "charge_ledger_ok", "network_ledger_ok", "element_ledger_ok",
                "free_energy_ledger_ok", "information_ledger_ok", "rewrite_ok")


def _last(rows, key):
    return float(rows[-1].get(key, float("nan"))) if rows else float("nan")


def _settled(rows, key, frac=0.15):
    n = max(1, int(round(len(rows) * frac)))
    t = [float(r.get(key, float("nan"))) for r in rows[-n:]]
    return sum(t) / len(t) if t else float("nan")


def settled_rows(rows, frac=0.15):
    n = max(1, int(round(len(rows) * frac)))
    return rows[-n:]


def final_survivors(rows) -> float:
    return _last(rows, "survivors")


def settled_autonomy(rows) -> float:
    return _settled(rows, "autonomy")


def settled_autonomy_work(rows) -> float:
    return _settled(rows, "autonomy_work")


def settled_autonomy_material(rows) -> float:
    return _settled(rows, "autonomy_material")


def settled_autonomy_information(rows) -> float:
    return _settled(rows, "autonomy_information")


def settled_net_power(rows) -> float:
    return _settled(rows, "net_power")


def settled_material_net(rows) -> float:
    return _settled(rows, "material_net")


def settled_machinery(rows) -> float:
    return _settled(rows, "machinery")


def ablation_complete(rows) -> float:
    return 1.0 if _last(rows, "ablation_phase") >= 2.0 else 0.0


def every_ledger_ok(rows) -> float:
    """1 when every one of the seven ledgers reports ok on the final tick (the
    information ledger counts only while heredity is attached — its ok flag is
    0 by definition until the MI estimator has converged)."""
    if not rows:
        return float("nan")
    last = rows[-1]
    flags = [float(last.get(k, 0.0)) >= 0.5 for k in LEDGER_FLAGS if k != "information_ledger_ok"]
    info_ok = float(last.get("energy_residual", 1.0)) <= 1.0e-9
    return 1.0 if all(flags) and info_ok else 0.0


def worst_residuals(rows) -> dict:
    if not rows:
        return {}
    last = rows[-1]
    return {"geology_mass": float(last.get("geology_mass_residual", float("nan"))),
            "charge": float(last.get("charge_residual_max", float("nan"))),
            "element": float(last.get("element_residual_max", float("nan"))),
            "C": float(last.get("C_residual_max", float("nan"))), "N": float(last.get("N_residual_max", float("nan"))),
            "P": float(last.get("P_residual_max", float("nan"))),
            "free_energy": float(last.get("free_energy_residual_max", float("nan"))),
            "information_energy": float(last.get("energy_residual", float("nan"))),
            "rewrite": float(last.get("rewrite_residual_max", float("nan"))),
            "partition": float(last.get("partition_residual_max", float("nan")))}


def event_count(rows) -> float:
    return _last(rows, "event_count")


PHASE9_REDUCERS = {
    "survivors": final_survivors, "autonomy": settled_autonomy, "autonomy_work": settled_autonomy_work,
    "autonomy_material": settled_autonomy_material, "autonomy_information": settled_autonomy_information,
    "net_power": settled_net_power, "material_net": settled_material_net, "machinery": settled_machinery,
    "ablation_complete": ablation_complete, "every_ledger_ok": every_ledger_ok, "event_count": event_count,
}

__all__ = ["integrated_autonomy_world", "relative_leak", "PHASE9_REDUCERS", "LEDGER_FLAGS", "worst_residuals",
           "settled_rows", "INNOVATIONS"]
