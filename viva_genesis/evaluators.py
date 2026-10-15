"""Workspace evaluator hook — machine-gradeable readouts for og-00 behavior tests.

``viva_superpowers.study_evaluator`` calls ``register_derived_scalars(reg)`` on
this module (it is imported as ``<package_path>.evaluators``). Each registered
computer ``fn(reader, test, ws_root) -> float`` turns a persisted run store into
a single scalar the evaluator then grades with the study's ``pass_if`` op — so a
``behavior_test`` whose ``measure.path`` names one of these keys auto-grades
PASS/FAIL from real run data, no agent in the loop.

These read the Campaign-0 vent-reactor observables (temperature, pH, H2_flux,
charge_imbalance, flux_divergence_residual) that the ``serpentinizing_vent_reactor``
composite persists via its ParquetEmitter. "Settled" readouts use the last
quartile of the trajectory (the reactor's steady state, not the start-up
transient); "sustained" readouts reduce over the back half.
"""
from __future__ import annotations

from typing import Any


def _values(reader, observable: str) -> list[float]:
    """Return the run's series for *observable* as a clean float list.

    Raises if the observable isn't in the store, so the evaluator falls to the
    agent bucket honestly rather than fabricating a verdict.
    """
    df = reader.series(observable)  # viva_emitters RunReader -> polars DataFrame
    import math
    out: list[float] = []
    for v in df["value"].to_list():
        if v is None:
            continue
        fv = float(v)
        if math.isnan(fv):
            continue
        out.append(fv)
    if not out:
        raise ValueError(f"observable {observable!r} has no finite values")
    return out


def _tail(vals: list[float], frac: float) -> list[float]:
    """The last ``frac`` of the series (at least one point) — the settled window."""
    n = max(1, int(round(len(vals) * frac)))
    return vals[-n:]


def _settled_mean(reader, observable: str, frac: float = 0.25) -> float:
    tail = _tail(_values(reader, observable), frac)
    return sum(tail) / len(tail)


# --- registered computers --------------------------------------------------

def _settled_temperature_c(reader, test: dict, ws_root: Any) -> float:
    """Steady-state outlet temperature in deg C (store holds kelvin)."""
    return _settled_mean(reader, "temperature") - 273.15


def _settled_ph(reader, test: dict, ws_root: Any) -> float:
    """Steady-state outlet pH."""
    return _settled_mean(reader, "pH")


def _min_sustained_h2_flux(reader, test: dict, ws_root: Any) -> float:
    """Minimum H2 source flux over the back half of the run — a sustained,
    non-collapsing reducing supply has min flux > 0."""
    vals = _values(reader, "H2_flux")
    return min(_tail(vals, 0.5))


def _max_abs_charge_imbalance(reader, test: dict, ws_root: Any) -> float:
    """Worst-case |charge imbalance| (eq/kgw) over the run — PHREEQC balances
    charge by construction, so this stays ~0 (charge_neutrality invariant)."""
    return max(abs(v) for v in _values(reader, "charge_imbalance"))


def _max_flux_divergence_residual(reader, test: dict, ws_root: Any) -> float:
    """Worst-case finite-volume flux-divergence residual over the run — FiPy's
    conservative FVM keeps this ~0 (spatial_flux_conservation invariant)."""
    return max(abs(v) for v in _values(reader, "flux_divergence_residual"))


# --- og-01 (geology -> reduced carbon) readouts --------------------------

def _settled_formate_mM(reader, test: dict, ws_root: Any) -> float:
    """Batch formate yield in mM (store holds molar)."""
    return _settled_mean(reader, "formate", frac=0.1) * 1000.0


def _settled_acetate_uM(reader, test: dict, ws_root: Any) -> float:
    return _settled_mean(reader, "acetate", frac=0.1) * 1.0e6


def _settled_pyruvate_uM(reader, test: dict, ws_root: Any) -> float:
    return _settled_mean(reader, "pyruvate", frac=0.1) * 1.0e6


def _peak_net_carbon_flux(reader, test: dict, ws_root: Any) -> float:
    """Peak organic-carbon fixation rate (mol/s) over the run — the sustained-
    flux-region witness (>0 means a viable fixation region exists)."""
    return max(_values(reader, "net_carbon_flux"))


def _free_energy_logged_fraction(reader, test: dict, ws_root: Any) -> float:
    """Fraction of steps with a finite logged ΔG' (eQuilibrator) — the
    energy_directionality invariant witness; 1.0 when logged every step."""
    vals = _values(reader, "dg_formate")  # raises if none -> honest agent bucket
    return 1.0 if vals else 0.0


def _max_abs_electro_flux_residual(reader, test: dict, ws_root: Any) -> float:
    """Worst-case |FVM flux-divergence residual| from the Nernst-Planck solve."""
    return max(abs(v) for v in _values(reader, "flux_divergence_residual"))


def _pmf_backpressure_sag_frac(reader, test: dict, ws_root: Any) -> float:
    """Peak drawdown of the proton reservoir under fixation load — the chemiosmotic
    back-pressure depth (loaded pmf = open-circuit pmf × charge_state, so this is
    also the fractional pmf sag). >0 proves carbon fixation SPENDS the gradient (the
    stoichiometric proton budget draws it down); ~0 would mean the gradient merely
    correlates with fixation rather than powering it. Measured from charge_state
    (initialized to 1.0), so it is immune to the first-tick pmf-init transient."""
    charge = _values(reader, "charge_state")
    return max(0.0, 1.0 - min(charge)) if charge else 0.0


# --- og-02 (reduced carbon -> protometabolism) readouts ------------------

def _settled_net_carbon_flux(reader, test: dict, ws_root: Any) -> float:
    """Steady net carbon throughput (mol/s) under feed+washout."""
    return _settled_mean(reader, "net_carbon_flux", frac=0.2)


def _peak_autocatalytic_gain(reader, test: dict, ws_root: Any) -> float:
    """Peak OAA self-amplification ratio — >=1 means a reinforcing motif exists."""
    return max(_values(reader, "autocatalytic_gain"))


def _network_connected_final(reader, test: dict, ws_root: Any) -> float:
    """1.0 if the species-reaction graph is a single connected network."""
    return _values(reader, "network_connected")[-1]


# --- og-03 (dilution -> localized individuals) readouts ------------------

def _settled_accumulation_peclet(reader, test: dict, ws_root: Any) -> float:
    """Settled thermal-trap accumulation Péclet (= ln(enrichment)). >= ln(1e8) ≈
    18.4 reproduces Baaske's extreme nucleotide accumulation in favorable pores."""
    return _settled_mean(reader, "accumulation_peclet", frac=0.2)


def _log10_enrichment(reader, test: dict, ws_root: Any) -> float:
    """Settled trap enrichment as log10(fold) — ~7.9 for Baaske's >10^8, ~0 in a
    washout control (open pore / no convection)."""
    import math
    e = _settled_mean(reader, "enrichment_factor", frac=0.2)
    return math.log10(max(e, 1.0))


def _max_abs_trap_flux_residual(reader, test: dict, ws_root: Any) -> float:
    """Worst-case |FVM flux-divergence residual| from the thermal-trap column
    solve — the spatial_flux_conservation witness."""
    return max(abs(v) for v in _values(reader, "flux_divergence_residual"))


# --- og-04 (mineral compartments -> protocells) readouts -----------------

def _settled_viable_compartments(reader, test: dict, ws_root: Any) -> float:
    """Viable vesicle count in the favorable arm — >0 means vesicles form in the
    mixed-amphiphile stability window (Jordan 2019)."""
    return _settled_mean(reader, "viable_compartments", frac=0.2)


def _settled_individuality_access(reader, test: dict, ws_root: Any) -> float:
    """Retention × access — individuality WITHOUT isolation. >0 means the membrane
    holds internal chemistry AND stays permeable to the external gradient."""
    return _settled_mean(reader, "individuality_access", frac=0.2)


# --- og-05 (environmental -> internal bioenergetics) readouts ------------

def _final_internalization(reader, test: dict, ws_root: Any) -> float:
    """Active-pump fraction of the surviving population at the end of the run, as
    the external gradient collapses — >0.5 means selection internalized gradient
    generation (the bioenergetic transition)."""
    return _values(reader, "internalization")[-1]


def _final_survivors(reader, test: dict, ws_root: Any) -> float:
    """Surviving strategy mass at the end of the run — a lineage that internalized
    persists (~1); one that could not (weak pump) collapses (~0) as the external
    gradient drops (the Sojo constraint)."""
    return _values(reader, "survivors")[-1]


# --- og-06 (chemistry -> heredity) readouts ------------------------------

def _final_lineage_fitness(reader, test: dict, ws_root: Any) -> float:
    """Heredity-module lineage fitness at the end of the run = benefit*(retention*C)
    - cost*krep. >0 means inheritance pays within the replication budget; the best
    module wins the head-to-head."""
    return _values(reader, "lineage_fitness")[-1]


def _final_information_retention(reader, test: dict, ws_root: Any) -> float:
    """Functional-information retention C/(C+E) at the end — high above the Eigen
    error threshold, ~0 in the error catastrophe."""
    return _values(reader, "information_retention")[-1]


# --- og-08 (escape from the vent) readouts ------------------------------

def _offgradient_survival(reader, test: dict, ws_root: Any) -> float:
    """Surviving population fraction at the end of the run, as geological support is
    withdrawn (the external gradient, mineral access and feed all relaxed toward zero).
    ~1 means the full innovation set persists OFF the gradient (autonomy); ~0 means the
    lineage collapses with the vent (a knockout that cannot hold the minimum set)."""
    return _values(reader, "survivors")[-1]


# --- og-07 (ecology before LUCA) readouts -------------------------------

def _connected_metacommunity_robustness(reader, test: dict, ws_root: Any) -> float:
    """Settled functional redundancy (robustness) of the connected metacommunity —
    the fraction of protometabolic capabilities covered by >= R compartments (so each
    survives a single-compartment loss). Above the isolated counterfactual because
    cross-feeding + horizontal transfer spread capabilities into redundant coverage."""
    return _settled_mean(reader, "metacommunity_robustness", frac=0.2)


def _luca_capability_overlap(reader, test: dict, ws_root: Any) -> float:
    """Settled overlap of the metacommunity's collective capability repertoire with
    the anaerobic H2/CO2/FeS LUCA reconstruction (Weiss 2016) — reported as a far-end
    BOUNDARY the emergent set approaches, NOT a fitting target."""
    return _settled_mean(reader, "luca_capability_overlap", frac=0.2)


# --- og-res (nitrogen as a limiting resource) readouts ------------------

def _settled_nh4_uM(reader, test: dict, ws_root: Any) -> float:
    """Settled ammonium pool in µM (store holds molar) — the standing reduced-N the
    FeS-mediated reduction accumulates under feed + washout. ~0 in the no-FeS / no-H2
    controls, a sustained pool in the favourable arm."""
    return _settled_mean(reader, "NH4", frac=0.2) * 1.0e6


def _settled_reduced_n_uM(reader, test: dict, ws_root: Any) -> float:
    """Settled useful reduced N (NH4+ + amino-acid precursor) in µM."""
    return _settled_mean(reader, "reduced_n", frac=0.2) * 1.0e6


def _settled_cn_supply_ratio(reader, test: dict, ws_root: Any) -> float:
    """Settled C:N supply ratio = carbon demand / reduced-N production. Within a viable
    band (~Redfield) reduced N keeps pace with carbon; large means nitrogen is limiting."""
    vals = [min(v, 1.0e6) for v in _values(reader, "cn_supply_ratio")]
    return sum(_tail(vals, 0.2)) / len(_tail(vals, 0.2))


def _peak_nh4_production_rate(reader, test: dict, ws_root: Any) -> float:
    """Peak reduced-nitrogen (ammonium) production rate (mol/s) over the run — the
    witness that a viable reduced-N source exists (>0 in the favourable arm, ~0 in
    the no-FeS / no-H2 controls)."""
    return max(_values(reader, "nh4_production_rate"))


def _max_abs_n_mass_residual(reader, test: dict, ws_root: Any) -> float:
    """Worst-case |per-step nitrogen-mass accounting error| (M) — every internal
    reaction conserves N atoms, so Delta(total N) must equal feed - washout exactly;
    this stays ~0 to machine precision (the matter-accounting invariant witness)."""
    return max(abs(v) for v in _values(reader, "n_mass_residual"))


# --- og-res-phosphorus-availability (the phosphorus bottleneck) readouts ----

def _phosphate_reactive_p_settled(reader, test: dict, ws_root: Any) -> float:
    """Settled standing reactive-P pool in µM (store holds molar) — the available
    reactive phosphorus in the favorable (enriched) pore. >0 and above threshold
    means reactive P accumulates rather than precipitating."""
    return _settled_mean(reader, "reactive_P", frac=0.2) * 1.0e6


def _phosphorus_net_reactive_availability(reader, test: dict, ws_root: Any) -> float:
    """Settled net reactive-P availability (mol/s) = reactive-P production flux −
    precipitation/adsorption loss flux. >0 means reactive P is produced FASTER than
    phosphate precipitates — a local window where P is usable before it is lost."""
    return _settled_mean(reader, "net_reactive_P", frac=0.2)


def _phosphate_precipitated_fraction_final(reader, test: dict, ws_root: Any) -> float:
    """Final mineral-bound (precipitated/adsorbed) fraction of total P — ~0 in the
    favorable pore (reactive route wins), ~1 in the open-pore control (the sink wins)."""
    return _values(reader, "precipitated_fraction")[-1]


def _phosphorus_p_mass_residual(reader, test: dict, ws_root: Any) -> float:
    """Worst-case |total P − supplied| / supplied over the run — the P-mass
    conservation witness; ~0 because the speciation network is P-atom-conserving."""
    return max(abs(v) for v in _values(reader, "p_mass_residual"))


# --- og-proto-energetics (an energy currency before modern pumping) readouts ---

def _energy_final_charge_fraction(reader, test: dict, ws_root: Any) -> float:
    """Charged fraction of the carrier pool at the end of the run, under continuous
    endergonic load — >0 (above threshold) means the transferable currency is
    MAINTAINED, not merely charged transiently. ~0 in the no-coupling / no-drive
    ablations (the store never builds)."""
    return _values(reader, "energy_charge_fraction")[-1]


def _energy_stored_work_fraction(reader, test: dict, ws_root: Any) -> float:
    """Fraction of the input geochemical free energy captured as transferable usable
    work ((delivered work + currently stored)/input) at the end of the run — the
    stored-work fraction; the remainder is dissipated (uncoupled drive, discharge
    inefficiency, hydrolysis)."""
    return _values(reader, "energy_stored_work_fraction")[-1]


def _energy_ledger_residual(reader, test: dict, ws_root: Any) -> float:
    """Worst-case |free-energy ledger residual| = |input-(work+stored+dissipated)|
    over the run — the free-energy-accounting conservation witness; stays at machine
    precision (~0) by construction."""
    return max(abs(v) for v in _values(reader, "energy_ledger_residual"))


# --- og-growth-division (metabolism -> osmotic growth & division) readouts --

def _growth_division_count(reader, test: dict, ws_root: Any) -> float:
    """Final cumulative division count — >0 means the compartment's chemistry drove
    repeated osmotic growth to the division threshold (net growth leading to
    DIVISION), the physical-selection milestone of this stage."""
    return _values(reader, "division_count")[-1]


def _growth_net_growth(reader, test: dict, ws_root: Any) -> float:
    """Final net volume growth factor V/V0 — the compartment expanded under the
    osmotic load its metabolism generated (>1 = growth)."""
    return _values(reader, "net_growth")[-1]


def _osmotic_peak_pressure(reader, test: dict, ws_root: Any) -> float:
    """Peak internal osmotic pressure (Pa) over the run — the van 't Hoff pressure
    the product accumulation generated; bounded below the burst tension in the viable
    (dividing) regime, spiking past it in the lysis regime."""
    return max(_values(reader, "osmotic_pressure"))


def _osmotic_balance_residual_max(reader, test: dict, ws_root: Any) -> float:
    """Worst-case |osmolyte mass-balance residual| (mol) over the run — the growth /
    division mass-conservation witness ``(N0 + produced) - (N + leaked + daughter_mass)``;
    stays ~0 (machine precision) because division halves V and N exactly and the leak
    is capped at the amount present."""
    return max(abs(v) for v in _values(reader, "osmolyte_balance_residual"))


# --- geochemical_world / Phase-1 ledger (og-cal-vent-environment) ------------

def _ledger_ok_final(reader, test: dict, ws_root: Any) -> float:
    """Final ConservationLedgerProcess verdict (1 = every residual within tolerance)."""
    return _values(reader, "ledger_ok")[-1]


def _max_ledger_mass_residual(reader, test: dict, ws_root: Any) -> float:
    """Worst-case |pool - integrated source| / integral over H2 and alkalinity."""
    h2 = _values(reader, "H2_residual")
    alk = _values(reader, "alkalinity_residual")
    return max(max(abs(v) for v in h2), max(abs(v) for v in alk))


def _max_ledger_energy_residual(reader, test: dict, ws_root: Any) -> float:
    """Worst-case |heat pool - integrated heat source| / integral."""
    return max(abs(v) for v in _values(reader, "energy_residual"))


def _energy_directionality_final(reader, test: dict, ws_root: Any) -> float:
    """1 if the serpentinization heat source never went negative (released, not absorbed)."""
    return _values(reader, "energy_directionality")[-1]


def _settled_dissolved_h2_mM(reader, test: dict, ws_root: Any) -> float:
    """Reacted-fluid dissolved H2 (mmol/kg) backed out of the settled H2 flux.

    ``H2_flux = H2_conc * flow * area`` (PhreeqcSerpentinizationProcess), so with the
    run's ``flow_velocity`` and the process ``flux_area`` (test.params or 1e-3 / 60)."""
    params = test.get("params") or {}
    flow = float(params.get("flow_velocity", 1.0e-3))
    area = float(params.get("flux_area", 60.0))
    return 1.0e3 * _settled_mean(reader, "H2_flux") / (flow * area)


def _artifact_json(test: dict, ws_root: Any, default: str) -> dict:
    """Load the persisted ensemble/report artifact a cross-run gate reads
    (``test.artifact`` path relative to the workspace root; the ensemble is
    minutes of real PHREEQC + FiPy compute, so gates read the committed JSON)."""
    import json
    from pathlib import Path
    rel = str(test.get("artifact") or default)
    path = Path(ws_root) / rel if ws_root else Path(rel)
    if not path.exists():
        raise FileNotFoundError(f"ensemble artifact not found: {path}")
    return json.loads(path.read_text())


_OGCAL_REPORT = "workspace/studies/og-cal-vent-environment/artifacts/vent_environment_report.json"


def _posterior_viable_fraction(reader, test: dict, ws_root: Any) -> float:
    """Fraction of vent states consistent with observation that also satisfy the
    downstream chemical requirements (headline class) — the Phase-1 Robustness."""
    return float(_artifact_json(test, ws_root, _OGCAL_REPORT)["report"]["robustness"]["fraction"])


def _posterior_consistent_fraction(reader, test: dict, ws_root: Any) -> float:
    """Fraction of prior draws consistent with every observation window (headline class)."""
    rep = _artifact_json(test, ws_root, _OGCAL_REPORT)
    head = rep["report"]["meta"]["headline_class"]
    return float(rep["conditioning"]["per_class"][head]["p_consistent"])


def _structure_agreement_viable(reader, test: dict, ws_root: Any) -> float:
    """Fraction of prior draws on which every model class agrees about viability."""
    return float(_artifact_json(test, ws_root, _OGCAL_REPORT)["conditioning"]["cross_class"]["viable"]["agreement"])


def register_derived_scalars(registry: dict) -> None:
    """Hook called by study_evaluator.load_workspace_derived_scalars."""
    # og-00
    registry["settled_temperature_c"] = _settled_temperature_c
    registry["settled_pH"] = _settled_ph
    registry["min_sustained_H2_flux"] = _min_sustained_h2_flux
    registry["max_abs_charge_imbalance"] = _max_abs_charge_imbalance
    registry["max_flux_divergence_residual"] = _max_flux_divergence_residual
    # og-01
    registry["settled_formate_mM"] = _settled_formate_mM
    registry["settled_acetate_uM"] = _settled_acetate_uM
    registry["settled_pyruvate_uM"] = _settled_pyruvate_uM
    registry["peak_net_carbon_flux"] = _peak_net_carbon_flux
    registry["free_energy_logged_fraction"] = _free_energy_logged_fraction
    registry["max_abs_electro_flux_residual"] = _max_abs_electro_flux_residual
    registry["pmf_backpressure_sag_frac"] = _pmf_backpressure_sag_frac
    # og-02
    registry["settled_net_carbon_flux"] = _settled_net_carbon_flux
    registry["peak_autocatalytic_gain"] = _peak_autocatalytic_gain
    registry["network_connected_final"] = _network_connected_final
    # og-03
    registry["settled_accumulation_peclet"] = _settled_accumulation_peclet
    registry["log10_enrichment"] = _log10_enrichment
    registry["max_abs_trap_flux_residual"] = _max_abs_trap_flux_residual
    # og-04
    registry["settled_viable_compartments"] = _settled_viable_compartments
    registry["settled_individuality_access"] = _settled_individuality_access
    # og-05
    registry["final_internalization"] = _final_internalization
    registry["final_survivors"] = _final_survivors
    # og-06
    registry["final_lineage_fitness"] = _final_lineage_fitness
    registry["final_information_retention"] = _final_information_retention
    # og-08
    registry["offgradient_survival"] = _offgradient_survival
    # og-07
    registry["metacommunity_robustness"] = _connected_metacommunity_robustness
    registry["luca_capability_overlap"] = _luca_capability_overlap
    # og-res (nitrogen as a limiting resource)
    registry["settled_nh4_uM"] = _settled_nh4_uM
    registry["settled_reduced_n_uM"] = _settled_reduced_n_uM
    registry["cn_supply_ratio_settled"] = _settled_cn_supply_ratio
    registry["peak_nh4_production_rate"] = _peak_nh4_production_rate
    registry["max_abs_n_mass_residual"] = _max_abs_n_mass_residual
    # og-res-phosphorus-availability
    registry["phosphate_reactive_p_settled"] = _phosphate_reactive_p_settled
    registry["phosphorus_net_reactive_availability"] = _phosphorus_net_reactive_availability
    registry["phosphate_precipitated_fraction_final"] = _phosphate_precipitated_fraction_final
    registry["phosphorus_p_mass_residual"] = _phosphorus_p_mass_residual
    # og-proto-energetics
    registry["energy_final_charge_fraction"] = _energy_final_charge_fraction
    registry["energy_stored_work_fraction"] = _energy_stored_work_fraction
    registry["energy_ledger_residual"] = _energy_ledger_residual
    # og-growth-division
    registry["growth_division_count"] = _growth_division_count
    registry["growth_net_growth"] = _growth_net_growth
    registry["osmotic_peak_pressure"] = _osmotic_peak_pressure
    registry["osmotic_balance_residual_max"] = _osmotic_balance_residual_max
    # geochemical_world / Phase-1 environmental calibration (og-cal-vent-environment)
    registry["ledger_ok_final"] = _ledger_ok_final
    registry["max_ledger_mass_residual"] = _max_ledger_mass_residual
    registry["max_ledger_energy_residual"] = _max_ledger_energy_residual
    registry["energy_directionality_final"] = _energy_directionality_final
    registry["settled_dissolved_h2_mM"] = _settled_dissolved_h2_mM
    registry["posterior_viable_fraction"] = _posterior_viable_fraction
    registry["posterior_consistent_fraction"] = _posterior_consistent_fraction
    registry["structure_agreement_viable"] = _structure_agreement_viable
