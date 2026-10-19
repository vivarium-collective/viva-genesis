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


# --- electrochemical interface / Phase-2 (og-01-cal-electrochemistry) --------

_OGCAL_ELECTRO_REPORT = "workspace/studies/og-01-cal-electrochemistry/artifacts/electrochemistry_report.json"


def _charge_ledger_residual_max(reader, test: dict, ws_root: Any) -> float:
    """Worst-case Kirchhoff residual |anode - (carbon + her)| / anode over the run
    (ChargeLedgerProcess) — the charge + electron-count ledger witness."""
    return max(abs(v) for v in _values(reader, "charge_residual_max"))


def _faradaic_efficiency_max(reader, test: dict, ws_root: Any) -> float:
    """Worst-case faradaic efficiency (electrons to carbon / electrons supplied)
    over the run — must never exceed 1."""
    return max(_values(reader, "faradaic_efficiency_max"))


def _iv_residual_max(reader, test: dict, ws_root: Any) -> float:
    """Worst-case current-voltage (circuit-equation) residual of the galvanic-cell solve."""
    return max(abs(v) for v in _values(reader, "iv_residual_max"))


def _charge_ledger_ok_final(reader, test: dict, ws_root: Any) -> float:
    """Final ChargeLedgerProcess verdict (1 = every residual within tolerance, FE <= 1)."""
    return _values(reader, "charge_ledger_ok")[-1]


def _settled_current_density(reader, test: dict, ws_root: Any) -> float:
    """Settled cell current density (A/m^2) — compared with the Altair-2025 window."""
    return _settled_mean(reader, "current_density", frac=0.1)


def _settled_faradaic_efficiency(reader, test: dict, ws_root: Any) -> float:
    """Settled fraction of the electrons reaching the cathode that reduce CO2."""
    return _settled_mean(reader, "faradaic_efficiency", frac=0.1)


def _failure_mode_label_coverage(reader, test: dict, ws_root: Any) -> float:
    """Fraction of mechanism-map points that carry a limitation label, worst class
    (every point must be attributed: thermodynamic / electrical / catalytic / transport)."""
    att = _artifact_json(test, ws_root, _OGCAL_ELECTRO_REPORT)["attribution"]
    return min(float(pc["label_coverage"]) for pc in att["per_class"].values())


def _failure_mode_agreement_favorable(reader, test: dict, ws_root: Any) -> float:
    """Fraction of the region BOTH runnable classes call favorable on which they agree
    about the limitation label — the failure-mode-attributed gate metric."""
    v = _artifact_json(test, ws_root, _OGCAL_ELECTRO_REPORT)["attribution"]["cross_class"]["label_agreement_favorable"]
    if v is None:
        raise ValueError("no point is favorable under every class; agreement undefined")
    return float(v)


def _failure_mode_agreement_all(reader, test: dict, ws_root: Any) -> float:
    """Label agreement over every point both classes ran."""
    return float(_artifact_json(test, ws_root, _OGCAL_ELECTRO_REPORT)["attribution"]["cross_class"]["label_agreement_all"])


def _mechanism_map_ledger_all_ok(reader, test: dict, ws_root: Any) -> float:
    """1.0 when the charge ledger closed on every mechanism-map point of every class."""
    att = _artifact_json(test, ws_root, _OGCAL_ELECTRO_REPORT)["attribution"]
    return 1.0 if all(pc["ledger"]["all_ok"] for pc in att["per_class"].values()) else 0.0
# --- open_chemical_network / Phase-3 reaction universe (og-02-alt-reaction-universe) ----

_OG02ALT_ENRICHMENT = "workspace/studies/og-02-alt-reaction-universe/artifacts/motif_enrichment.json"
_OG02ALT_VERIFICATION = "workspace/studies/og-02-alt-reaction-universe/artifacts/reaction_universe_verification.json"


def _network_ledger_ok_final(reader, test: dict, ws_root: Any) -> float:
    """Final NetworkLedgerProcess verdict (element, carbon and free-energy witnesses within tolerance)."""
    return _values(reader, "ledger_ok")[-1]


def _max_element_residual(reader, test: dict, ws_root: Any) -> float:
    """Worst-case stoichiometric element residual max|E S| (exact; 0 for a generated universe)."""
    return _values(reader, "element_residual_max")[-1]


def _max_carbon_residual(reader, test: dict, ws_root: Any) -> float:
    """Worst-case integrated carbon-balance residual (integrator tolerance)."""
    return _values(reader, "carbon_residual_max")[-1]


def _free_energy_directionality_final(reader, test: dict, ws_root: Any) -> float:
    """1 if the dissipation -sum v dG never went below -tolerance (second law)."""
    return _values(reader, "free_energy_directionality")[-1]


def _final_n_persistent_species(reader, test: dict, ws_root: Any) -> float:
    return _values(reader, "n_persistent_species")[-1]


def _final_n_autocatalytic_motifs(reader, test: dict, ws_root: Any) -> float:
    return _values(reader, "n_autocatalytic_motifs")[-1]


def _settled_malate_M(reader, test: dict, ws_root: Any) -> float:
    """Settled malate pool (M): the rTCA reductive branch emerging from the rules."""
    return _settled_mean(reader, "malate")


def _motif_enrichment_p(reader, test: dict, ws_root: Any) -> float:
    """Empirical one-sided p of the universe's persistent-motif count against the
    matched nulls, in the arm named by ``test.params.arm`` (default formose_feed)."""
    arm = str((test.get("params") or {}).get("arm", "formose_feed"))
    rep = _artifact_json(test, ws_root, _OG02ALT_ENRICHMENT)
    return float(rep["arms"][arm]["enrichment"]["n_motifs"]["p_empirical"])


def _universe_motif_count(reader, test: dict, ws_root: Any) -> float:
    """Persistent autocatalytic motifs detected post hoc in the universe (arm from test.params.arm)."""
    arm = str((test.get("params") or {}).get("arm", "formose_feed"))
    rep = _artifact_json(test, ws_root, _OG02ALT_ENRICHMENT)
    return float(rep["arms"][arm]["universe"]["n_motifs"])


def _null_max_motif_count(reader, test: dict, ws_root: Any) -> float:
    arm = str((test.get("params") or {}).get("arm", "formose_feed"))
    rep = _artifact_json(test, ws_root, _OG02ALT_ENRICHMENT)
    return float(rep["arms"][arm]["enrichment"]["n_motifs"]["null_max"])


def _curated_element_residual(reader, test: dict, ws_root: Any) -> float:
    """max|E S| of og-02's curated rTCA SBML, computed post hoc from its stoichiometry."""
    rep = _artifact_json(test, ws_root, _OG02ALT_ENRICHMENT)
    return float(rep["arms"]["phase1_feed"]["curated_rtca"]["element_residual"])


def _fcc_summation_residual_max(reader, test: dict, ws_root: Any) -> float:
    """Worst |sum_j C^J_ij - 1| over the DOMINANT fluxes (>= 1% of the largest) of the
    settled universe (MCA summation theorem; exact only at steady state)."""
    rep = _artifact_json(test, ws_root, _OG02ALT_VERIFICATION)
    fc = rep["reaction_universe"]["flux_control"]
    if not fc.get("ok"):
        raise ValueError(f"flux-control analysis failed: {fc.get('error')}")
    return float(fc["dominant_summation_residual"])


def _tolerance_sensitivity_max(reader, test: dict, ws_root: Any) -> float:
    """Worst relative species deviation when CVODE tolerances are loosened/tightened around the defaults."""
    rep = _artifact_json(test, ws_root, _OG02ALT_VERIFICATION)
    devs = rep["reaction_universe"]["stiffness"]["deviations"]
    return max(float(v["max_rel_dev"]) for v in devs.values())


# Phase 5 (og-04-alt endogenous boundary / og-growth-alt physical reproduction)
# These gates read the committed JSON run artifact (headline block) rather than
# the gitignored run.db, so every number verifies from the tree — and the
# headline scalars are the PEAK / all-steps reductions ("reaches generation N",
# "conserves at every rewrite"), not the series mean the raw-observable resolver
# would apply. The derived-scalar names deliberately do NOT collide with any
# emitted observable, so _resolve_series raises and these computers run.
_PHASE5_BOUNDARY_REPORT = (
    "workspace/studies/og-self-compartmentation/artifacts/og-04-alt-endogenous-boundary/"
    "endogenous_boundary_report.json")
_PHASE5_GROWTH_REPORT = (
    "workspace/studies/og-growth-alt-physical-reproduction/artifacts/"
    "physical_reproduction_report.json")


def _boundary_forms_from_chemistry(reader, test, ws_root):
    """1.0 iff the favorable arm forms individuals and the synthesis-ablated
    control forms none — boundary formation is caused by the endogenous chemistry."""
    h = _artifact_json(test, ws_root, _PHASE5_BOUNDARY_REPORT)["headline"]
    return 1.0 if (h["n_agents_favorable"] >= 1 and h["n_agents_ablated"] == 0) else 0.0


def _endogenous_rewrite_conservation_ok(reader, test, ws_root):
    """1.0 iff every _add boundary-formation rewrite conserved matter (min over steps)."""
    return float(_artifact_json(test, ws_root, _PHASE5_BOUNDARY_REPORT)
                 ["headline"]["rewrite_conservation_ok"])


def _peak_generation(reader, test, ws_root):
    """Deepest generation the lineage reaches (PEAK over the run), not the time-mean."""
    return float(_artifact_json(test, ws_root, _PHASE5_GROWTH_REPORT)
                 ["headline"]["peak_generation"])


def _partition_residual_peak(reader, test, ws_root):
    """Worst (max) partition residual over every _divide — 0 means every split conserved."""
    return float(_artifact_json(test, ws_root, _PHASE5_GROWTH_REPORT)
                 ["headline"]["partition_residual_peak"])


# --- protocell_energetics / Phase-6 energy coupling (og-energy-alt-internalization-threshold) ----

_OGENERGYALT_REPORT = "workspace/studies/og-energy-alt-internalization-threshold/artifacts/internalization_threshold_report.json"


def _free_energy_ledger_ok_final(reader, test: dict, ws_root: Any) -> float:
    """Final FreeEnergyLedgerProcess verdict (residual, second-law margin, dissipation >= 0, efficiency <= 1)."""
    return _values(reader, "free_energy_ledger_ok")[-1]


def _free_energy_residual_max(reader, test: dict, ws_root: Any) -> float:
    """Worst-case |in_cum + E0 - work_cum - diss_cum - E(t)| / in_cum over the run (rounding by construction)."""
    return _values(reader, "free_energy_residual_max")[-1]


def _second_law_margin_min(reader, test: dict, ws_root: Any) -> float:
    """Minimum of in_cum + E0 - work_cum - diss_cum (J) over the run — free_energy_in >= work + dissipated."""
    return _values(reader, "second_law_margin_min")[-1]


def _final_autonomy(reader, test: dict, ws_root: Any) -> float:
    """Per-individual autonomy internal / (internal + external) power at the end of the run."""
    return _values(reader, "autonomy")[-1]


def _settled_net_power(reader, test: dict, ws_root: Any) -> float:
    """Settled net power (W) = work - maintenance of the individual (last quintile)."""
    return _settled_mean(reader, "net_power", frac=0.2)


def _settled_internal_power(reader, test: dict, ws_root: Any) -> float:
    return _settled_mean(reader, "internal_power", frac=0.2)


def _threshold_class(test: dict) -> str:
    return str((test.get("params") or {}).get("class", "thioester_acyl_phosphate"))


def _internalization_threshold_activity(reader, test: dict, ws_root: Any) -> float:
    """Threshold coupling activity a* at the nominal membrane + gradient for ``test.params.class``
    (raises when the class never pays on the grid, so the gate falls to the honest bucket)."""
    att = _artifact_json(test, ws_root, _OGENERGYALT_REPORT)["attribution"]
    v = att["per_class"][_threshold_class(test)]["nominal"]["threshold_activity"]
    if v is None:
        raise ValueError(f"{_threshold_class(test)} never pays at the nominal membrane; no threshold")
    return float(v)


def _autonomy_at_threshold(reader, test: dict, ws_root: Any) -> float:
    att = _artifact_json(test, ws_root, _OGENERGYALT_REPORT)["attribution"]
    v = att["per_class"][_threshold_class(test)]["nominal"]["autonomy_at_threshold"]
    if v is None:
        raise ValueError(f"{_threshold_class(test)} never pays at the nominal membrane; no autonomy at threshold")
    return float(v)


def _internalization_pays_fraction(reader, test: dict, ws_root: Any) -> float:
    """Fraction of the swept (activity x permeability x pmf) grid where ``test.params.class`` beats the passive baseline."""
    att = _artifact_json(test, ws_root, _OGENERGYALT_REPORT)["attribution"]
    return float(att["per_class"][_threshold_class(test)]["pays_fraction"])


def _n_classes_paying_at_nominal(reader, test: dict, ws_root: Any) -> float:
    """How many active classes have a finite threshold at the nominal membrane + gradient."""
    return float(_artifact_json(test, ws_root, _OGENERGYALT_REPORT)["attribution"]["cross_class"]["n_classes_paying_at_nominal"])


def _internalization_structure_agreement(reader, test: dict, ws_root: Any) -> float:
    """Fraction of the grid on which every active class gives the same pays / does-not-pay answer."""
    sa = _artifact_json(test, ws_root, _OGENERGYALT_REPORT)["attribution"]["cross_class"]["structure_agreement_pays"]
    return float(sa["agreement"])


def _threshold_map_ledger_all_ok(reader, test: dict, ws_root: Any) -> float:
    """1.0 when the free-energy ledger closed on every threshold-map point of every class."""
    att = _artifact_json(test, ws_root, _OGENERGYALT_REPORT)["attribution"]
    return 1.0 if all(pc["ledger"]["all_ok"] for pc in att["per_class"].values()) else 0.0
# --- competing_heredity / Phase-7 (og-06-alt-information-per-cost) --------------

_OG06ALT_FRONTIER = "workspace/studies/og-06-alt-information-per-cost/artifacts/information_frontier.json"


def _heritable_bits_final(reader, test: dict, ws_root: Any) -> float:
    """Realised heritable bits on the final tick: parent-offspring MI net of its permutation null."""
    return _values(reader, "information_content")[-1]


def _mi_converged_final(reader, test: dict, ws_root: Any) -> float:
    """1 when the MI estimator's prefix ladder + bootstrap SE converged on the final tick."""
    return _values(reader, "mi_converged")[-1]


def _information_ledger_ok_final(reader, test: dict, ws_root: Any) -> float:
    """Final InformationLedgerProcess verdict (energy store audited + MI converged)."""
    return _values(reader, "information_ledger_ok")[-1]


def _energy_store_residual_max(reader, test: dict, ws_root: Any) -> float:
    """Worst-case |stored_work - (W0 + in - used)| / in over the run."""
    return max(abs(v) for v in _values(reader, "energy_residual"))


def _bits_per_joule_final(reader, test: dict, ws_root: Any) -> float:
    return _values(reader, "bits_per_joule")[-1]


def _heredity_settled_function(reader, test: dict, ws_root: Any) -> float:
    """Settled population mean function (last quartile) of the lineage."""
    return _settled_mean(reader, "mean_function")


def _heredity_attached_final(reader, test: dict, ws_root: Any) -> float:
    return _values(reader, "attached")[-1]


def _n_classes_ancestry_predicts(reader, test: dict, ws_root: Any) -> float:
    """Number of heredity classes whose converged heritable bits pass the pre-registered
    per-class rule (>= 0.1 bit and >= 0.05 bit above the class's own unattached control)."""
    return float(_artifact_json(test, ws_root, _OG06ALT_FRONTIER)["gates"]["n_classes_ancestry_predicts"])


def _frontier_pareto_size(reader, test: dict, ws_root: Any) -> float:
    """Number of classes on the (bits up, energy down) Pareto front of converged classes."""
    return float(_artifact_json(test, ws_root, _OG06ALT_FRONTIER)["gates"]["frontier_pareto_size"])


def _frontier_span_decades(reader, test: dict, ws_root: Any) -> float:
    """log10 range of bits-per-joule across classes."""
    v = _artifact_json(test, ws_root, _OG06ALT_FRONTIER)["gates"]["frontier_span_decades"]
    if v is None:
        raise ValueError("bits-per-joule span undefined (fewer than two finite classes)")
    return float(v)


def _nonrna_bits_fraction(reader, test: dict, ws_root: Any) -> float:
    """Best non-RNA class's heritable bits / the rna_like class's (class substitution)."""
    v = _artifact_json(test, ws_root, _OG06ALT_FRONTIER)["gates"]["nonrna_bits_fraction"]
    if v is None:
        raise ValueError("no converged non-RNA class, or rna_like transmits 0 bits")
    return float(v)


def _nonrna_bits_per_joule_fraction(reader, test: dict, ws_root: Any) -> float:
    """Best non-RNA class's bits per joule / the rna_like class's (certified classes only)."""
    v = _artifact_json(test, ws_root, _OG06ALT_FRONTIER)["gates"]["nonrna_bits_per_joule_fraction"]
    if v is None:
        raise ValueError("no certified non-RNA class, or rna_like uncertified / 0 bits per joule")
    return float(v)


def _attachment_budget_span(reader, test: dict, ws_root: Any) -> float:
    """Mean (attached fraction at the highest budget - at the lowest) over classes the Eigen floor admits."""
    return float(_artifact_json(test, ws_root, _OG06ALT_FRONTIER)["gates"]["attachment_budget_span"])


def _class_heritable_bits(reader, test: dict, ws_root: Any) -> float:
    """Converged heritable bits of one class (test.params.heredity_class), attached arm."""
    cls = str((test.get("params") or {}).get("heredity_class", "rna_like"))
    return float(_artifact_json(test, ws_root, _OG06ALT_FRONTIER)["classes"][cls]["attached"]["heritable_bits"])


def _frontier_ledger_residual_max(reader, test: dict, ws_root: Any) -> float:
    return float(_artifact_json(test, ws_root, _OG06ALT_FRONTIER)["ledger"]["energy_residual_max"])


def _templated_takeover_fidelity(reader, test: dict, ws_root: Any) -> float:
    """Lowest per-site fidelity at which rna_like attaches AND out-transmits the organic
    non-templated classes (compositional / network) — the transition to templated heredity."""
    v = _artifact_json(test, ws_root, _OG06ALT_FRONTIER)["gates"]["templated_takeover_fidelity"]
    if v is None:
        raise ValueError("rna_like never overtakes the organic non-templated classes in the swept fidelity range")
    return float(v)


def _frontier_energy_within_tolerance(reader, test: dict, ws_root: Any) -> float:
    """1.0 when the energy-store residual stayed within tolerance on every frontier / map run."""
    return 1.0 if _artifact_json(test, ws_root, _OG06ALT_FRONTIER)["ledger"]["all_energy_within_tolerance"] else 0.0


# --- Phase 8 (og-07-alt-real-metabolite-exchange): run-level + artifact gates ----------------
_OG07ALT_MAP = "workspace/studies/og-07-alt-real-metabolite-exchange/artifacts/community_function_map.json"


def _element_ledger_ok_final(reader, test: dict, ws_root: Any) -> float:
    """Final EcologyElementLedgerProcess verdict (C / N / P residuals over agents + field within tolerance)."""
    return _values(reader, "element_ledger_ok")[-1]


def _element_residual_max_all(reader, test: dict, ws_root: Any) -> float:
    """Worst-case C / N / P residual of the cross-system element ledger on the run."""
    return max(_values(reader, "C_residual_max")[-1], _values(reader, "N_residual_max")[-1],
               _values(reader, "P_residual_max")[-1])


def _carbon_residual_max_final(reader, test: dict, ws_root: Any) -> float:
    return _values(reader, "C_residual_max")[-1]


def _exchange_firings_final(reader, test: dict, ws_root: Any) -> float:
    """Cumulative exchange-rule firings (uptake + secretion + diffusion + pore exchange) on the run."""
    return _values(reader, "exchange_firings_total")[-1]


def _cross_lineage_flux_total_final(reader, test: dict, ws_root: Any) -> float:
    """Cumulative moles secreted by one lineage and taken up by another (the real-flux witness)."""
    return _values(reader, "cross_lineage_flux_total")[-1]


def _max_cell_completeness_final(reader, test: dict, ws_root: Any) -> float:
    """Max over agents of |functions held| / |community union| on the final tick (< 1: no cell is complete)."""
    return _values(reader, "max_cell_completeness")[-1]


def _n_functions_union_final(reader, test: dict, ws_root: Any) -> float:
    return _values(reader, "n_functions_union")[-1]


def _settled_robustness_gain(reader, test: dict, ws_root: Any) -> float:
    """Settled held-minus-produced robustness: what real metabolite flux delivered."""
    return _settled_mean(reader, "robustness_gain", frac=0.2)


def _n_community_only_functions(reader, test: dict, ws_root: Any) -> float:
    """Product classes held in the community but held / produced by no lineage in monoculture (nominal point)."""
    return float(_artifact_json(test, ws_root, _OG07ALT_MAP)["gates"]["n_community_only_functions"])


def _n_vanish_without_exchange(reader, test: dict, ws_root: Any) -> float:
    return float(_artifact_json(test, ws_root, _OG07ALT_MAP)["gates"]["n_vanish_without_exchange"])


def _community_flux_sustained(reader, test: dict, ws_root: Any) -> float:
    """1 when every community-only function vanishes in the private arm and a cross-lineage flux of its precursor exists."""
    return float(_artifact_json(test, ws_root, _OG07ALT_MAP)["gates"]["flux_sustained"])


def _community_cross_lineage_flux(reader, test: dict, ws_root: Any) -> float:
    return float(_artifact_json(test, ws_root, _OG07ALT_MAP)["gates"]["community_cross_lineage_flux_total"])


def _community_max_cell_completeness(reader, test: dict, ws_root: Any) -> float:
    return float(_artifact_json(test, ws_root, _OG07ALT_MAP)["gates"]["community_max_cell_completeness"])


def _community_over_generalist(reader, test: dict, ws_root: Any) -> float:
    v = _artifact_json(test, ws_root, _OG07ALT_MAP)["gates"]["community_over_generalist"]
    if v is None:
        raise ValueError("no community-only function to compare with the generalist")
    return float(v)


def _null_community_only_max(reader, test: dict, ws_root: Any) -> float:
    return float(_artifact_json(test, ws_root, _OG07ALT_MAP)["gates"]["null_community_only_max"])


def _segregated_n_community_only(reader, test: dict, ws_root: Any) -> float:
    return float(_artifact_json(test, ws_root, _OG07ALT_MAP)["gates"]["segregated_n_community_only"])


def _emergence_p_diacid_nominal(reader, test: dict, ws_root: Any) -> float:
    """Lowest diacid permeability (m/s) at the nominal residence at which the community-only function emerges."""
    v = _artifact_json(test, ws_root, _OG07ALT_MAP)["gates"]["emergence_p_diacid_at_nominal_residence"]
    if v is None:
        raise ValueError("no emergence inside the swept permeability range")
    return float(v)


def _map_ledgers_all_ok(reader, test: dict, ws_root: Any) -> float:
    return 1.0 if _artifact_json(test, ws_root, _OG07ALT_MAP)["gates"]["all_ledgers_ok"] else 0.0


def _map_carbon_residual_max(reader, test: dict, ws_root: Any) -> float:
    return float(_artifact_json(test, ws_root, _OG07ALT_MAP)["ledger"]["C_residual_max"])


def _connected_minus_isolated_robustness(reader, test: dict, ws_root: Any) -> float:
    """og-07's connected-beats-isolated, on the real community: robustness(shared) - robustness(private)."""
    return float(_artifact_json(test, ws_root, _OG07ALT_MAP)["gates"]["connected_minus_isolated_robustness"])


# --- Phase 9 (og-08-alt-robust-innovation-set): run-level + artifact gates ------------------
_OG08ALT_SET = "workspace/studies/og-independence/artifacts/og-08-alt-robust-innovation-set/robust_innovation_set.json"
_PHASE9_LEDGER_FLAGS = ("geology_ledger_ok", "charge_ledger_ok", "network_ledger_ok", "element_ledger_ok",
                        "free_energy_ledger_ok", "rewrite_ok")


def _every_ledger_ok_final(reader, test: dict, ws_root: Any) -> float:
    """1 when every ledger of the integrated world reports ok on the final tick (the information
    ledger by its exact energy-store residual, since its ok flag also needs MI convergence)."""
    flags = [_values(reader, k)[-1] >= 0.5 for k in _PHASE9_LEDGER_FLAGS]
    info = _values(reader, "energy_residual")[-1] <= 1.0e-9
    return 1.0 if all(flags) and info else 0.0


def _ablation_complete_final(reader, test: dict, ws_root: Any) -> float:
    return 1.0 if _values(reader, "ablation_phase")[-1] >= 2.0 else 0.0


def _structural_events_logged(reader, test: dict, ws_root: Any) -> float:
    return _values(reader, "event_count")[-1]


def _settled_autonomy(reader, test: dict, ws_root: Any) -> float:
    """The work-weighted autonomy over the final 15 % of the run (every driver at its floor)."""
    return _settled_mean(reader, "autonomy", frac=0.15)


def _settled_autonomy_work(reader, test: dict, ws_root: Any) -> float:
    return _settled_mean(reader, "autonomy_work", frac=0.15)


def _settled_autonomy_material(reader, test: dict, ws_root: Any) -> float:
    return _settled_mean(reader, "autonomy_material", frac=0.15)


def _settled_net_power_offgradient(reader, test: dict, ws_root: Any) -> float:
    return _settled_mean(reader, "net_power", frac=0.15)


def _settled_machinery_offgradient(reader, test: dict, ws_root: Any) -> float:
    return _settled_mean(reader, "machinery", frac=0.15)


def _final_survivors_integrated(reader, test: dict, ws_root: Any) -> float:
    return _values(reader, "survivors")[-1]


def _set_gate(key: str):
    def fn(reader, test: dict, ws_root: Any) -> float:
        v = _artifact_json(test, ws_root, _OG08ALT_SET)["gates"][key]
        if v is None:
            raise ValueError(f"{key}: no value in the artifact (undefined for this ensemble)")
        return float(v)
    fn.__doc__ = f"artifact gate {key} of robust_innovation_set.json"
    return fn


def register_derived_scalars(registry: dict) -> None:
    """Hook called by study_evaluator.load_workspace_derived_scalars."""
    # Phase 9 (og-08-alt-robust-innovation-set): the seven ledgers over the integrated world,
    # the ablation, the structural-event log, the autonomy decomposition and the lattice gates
    registry["every_ledger_ok_final"] = _every_ledger_ok_final
    registry["ablation_complete_final"] = _ablation_complete_final
    registry["structural_events_logged"] = _structural_events_logged
    registry["settled_autonomy"] = _settled_autonomy
    registry["settled_autonomy_work"] = _settled_autonomy_work
    registry["settled_autonomy_material"] = _settled_autonomy_material
    registry["settled_net_power_offgradient"] = _settled_net_power_offgradient
    registry["settled_machinery_offgradient"] = _settled_machinery_offgradient
    registry["final_survivors_integrated"] = _final_survivors_integrated
    for key in ("full_set_persistence_fraction", "full_set_persistence_fraction_rich", "viable_fraction", "viable_fraction_rich",
                "robust_required_count", "robust_required_count_rich", "required_union_count", "required_union_count_rich",
                "required_set_agreement", "required_set_agreement_rich", "og08_intersection_matches",
                "og08_intersection_matches_rich", "minimum_sufficient_set_resolved", "minimum_sufficient_set_resolved_rich",
                "generic_persistence_fraction", "generic_rejected", "all_ledgers_ok", "ledger_ok_runs", "events_total",
                "autonomy_persisting_full_set", "autonomy_work_persisting_full_set", "autonomy_material_persisting_full_set",
                "autonomy_information_persisting_full_set", "autonomy_persisting_full_set_rich",
                "autonomy_persisting_any", "autonomy_persisting_any_rich", "autonomy_work_persisting_any_rich",
                "autonomy_material_persisting_any_rich", "autonomy_information_persisting_any_rich",
                "n_persisting_any_rich", "n_persisting_any", "autonomy_all_full_set_rich",
                "lowest_floor_majority_persists", "lowest_floor_any_persists"):
        registry[f"lattice_{key}"] = _set_gate(key)
    # protocell_energetics / Phase-6 energy coupling (og-energy-alt-internalization-threshold)
    registry["free_energy_ledger_ok_final"] = _free_energy_ledger_ok_final
    registry["free_energy_residual_max"] = _free_energy_residual_max
    registry["second_law_margin_min"] = _second_law_margin_min
    registry["final_autonomy"] = _final_autonomy
    registry["settled_net_power"] = _settled_net_power
    registry["settled_internal_power"] = _settled_internal_power
    registry["internalization_threshold_activity"] = _internalization_threshold_activity
    registry["autonomy_at_threshold"] = _autonomy_at_threshold
    registry["internalization_pays_fraction"] = _internalization_pays_fraction
    registry["n_classes_paying_at_nominal"] = _n_classes_paying_at_nominal
    registry["internalization_structure_agreement"] = _internalization_structure_agreement
    registry["threshold_map_ledger_all_ok"] = _threshold_map_ledger_all_ok
    # competing heredity / Phase-7 (og-06-alt-information-per-cost)
    registry["heritable_bits_final"] = _heritable_bits_final
    registry["mi_converged_final"] = _mi_converged_final
    registry["information_ledger_ok_final"] = _information_ledger_ok_final
    registry["energy_store_residual_max"] = _energy_store_residual_max
    registry["bits_per_joule_final"] = _bits_per_joule_final
    registry["heredity_settled_function"] = _heredity_settled_function
    registry["heredity_attached_final"] = _heredity_attached_final
    registry["n_classes_ancestry_predicts"] = _n_classes_ancestry_predicts
    registry["frontier_pareto_size"] = _frontier_pareto_size
    registry["frontier_span_decades"] = _frontier_span_decades
    registry["nonrna_bits_fraction"] = _nonrna_bits_fraction
    registry["nonrna_bits_per_joule_fraction"] = _nonrna_bits_per_joule_fraction
    registry["attachment_budget_span"] = _attachment_budget_span
    registry["class_heritable_bits"] = _class_heritable_bits
    registry["frontier_ledger_residual_max"] = _frontier_ledger_residual_max
    registry["templated_takeover_fidelity"] = _templated_takeover_fidelity
    registry["frontier_energy_within_tolerance"] = _frontier_energy_within_tolerance
    # electrochemical interface / Phase-2 (og-01-cal-electrochemistry)
    registry["charge_ledger_residual_max"] = _charge_ledger_residual_max
    registry["faradaic_efficiency_max"] = _faradaic_efficiency_max
    registry["iv_residual_max"] = _iv_residual_max
    registry["charge_ledger_ok_final"] = _charge_ledger_ok_final
    registry["settled_current_density"] = _settled_current_density
    registry["settled_faradaic_efficiency"] = _settled_faradaic_efficiency
    registry["failure_mode_label_coverage"] = _failure_mode_label_coverage
    registry["failure_mode_agreement_favorable"] = _failure_mode_agreement_favorable
    registry["failure_mode_agreement_all"] = _failure_mode_agreement_all
    registry["mechanism_map_ledger_all_ok"] = _mechanism_map_ledger_all_ok
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
    # open_chemical_network / Phase-3 reaction universe (og-02-alt-reaction-universe)
    registry["network_ledger_ok_final"] = _network_ledger_ok_final
    registry["max_element_residual"] = _max_element_residual
    registry["max_carbon_residual"] = _max_carbon_residual
    registry["free_energy_directionality_final"] = _free_energy_directionality_final
    registry["final_n_persistent_species"] = _final_n_persistent_species
    registry["final_n_autocatalytic_motifs"] = _final_n_autocatalytic_motifs
    registry["settled_malate_M"] = _settled_malate_M
    registry["motif_enrichment_p"] = _motif_enrichment_p
    registry["universe_motif_count"] = _universe_motif_count
    registry["null_max_motif_count"] = _null_max_motif_count
    registry["curated_element_residual"] = _curated_element_residual
    registry["fcc_summation_residual_max"] = _fcc_summation_residual_max
    registry["tolerance_sensitivity_max"] = _tolerance_sensitivity_max
    # Phase 5 (og-04-alt endogenous boundary / og-growth-alt physical reproduction)
    # Artifact-backed (read the committed JSON report); names avoid emitted-observable
    # shadowing so these computers actually run (peak/min reductions, not series mean).
    registry["boundary_forms_from_chemistry"] = _boundary_forms_from_chemistry
    registry["endogenous_rewrite_conservation_ok"] = _endogenous_rewrite_conservation_ok
    registry["peak_generation"] = _peak_generation
    registry["partition_residual_peak"] = _partition_residual_peak
    # Phase 8 (og-07-alt-real-metabolite-exchange): the cross-system element ledger,
    # the exchange-rule firings / cross-lineage flux, cell completeness and the
    # community-function artifact gates
    registry["element_ledger_ok_final"] = _element_ledger_ok_final
    registry["element_residual_max_all"] = _element_residual_max_all
    registry["carbon_residual_max_final"] = _carbon_residual_max_final
    registry["exchange_firings_final"] = _exchange_firings_final
    registry["cross_lineage_flux_total_final"] = _cross_lineage_flux_total_final
    registry["max_cell_completeness_final"] = _max_cell_completeness_final
    registry["n_functions_union_final"] = _n_functions_union_final
    registry["settled_robustness_gain"] = _settled_robustness_gain
    registry["n_community_only_functions"] = _n_community_only_functions
    registry["n_vanish_without_exchange"] = _n_vanish_without_exchange
    registry["community_flux_sustained"] = _community_flux_sustained
    registry["community_cross_lineage_flux"] = _community_cross_lineage_flux
    registry["community_max_cell_completeness"] = _community_max_cell_completeness
    registry["community_over_generalist"] = _community_over_generalist
    registry["null_community_only_max"] = _null_community_only_max
    registry["segregated_n_community_only"] = _segregated_n_community_only
    registry["emergence_p_diacid_nominal"] = _emergence_p_diacid_nominal
    registry["map_ledgers_all_ok"] = _map_ledgers_all_ok
    registry["map_carbon_residual_max"] = _map_carbon_residual_max
    registry["connected_minus_isolated_robustness"] = _connected_minus_isolated_robustness
