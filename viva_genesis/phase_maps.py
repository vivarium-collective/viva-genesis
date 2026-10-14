"""Decision surfaces (phase maps) for the pre-genetic campaign stages.

Each builder sweeps a real composite over a physically meaningful 2-D slice of its
parameter space and reduces every run to a decision scalar, so the Workbench can
render the viz plan's **Decision view** — the bounded region where the transition
occurs and the neighbouring regions where it fails. Reducers are module-level so
:func:`viva_genesis.sweep.sweep_grid` can fan the grid out over a process pool / Ray.
"""
from __future__ import annotations

import numpy as np

from .sweep import SweepResult, sweep_grid

# ----------------------------------------------------------------------------
# og-01 — geology → reduced carbon : the carbon-fixation landscape
# ----------------------------------------------------------------------------
# Decision metric. net_carbon_flux is an instantaneous RATE that collapses to ~0 as
# the (semi-batch) product pools saturate — so a settled-flux reading would read
# "dead" everywhere. The honest decision metric is the TOTAL reduced carbon fixed
# (the accumulated C1+C2+C3 pool, in mol-C): C1 formate + 2·C2 acetate + 3·C3
# pyruvate. Peak flux + whether the flux sustained separate "transient" from
# "sustained" within the producing region.
_C_PER = {"formate": 1.0, "acetate": 2.0, "pyruvate": 3.0}


def carbon_total(rows) -> float:
    """Final total reduced carbon fixed (mol-C) = Σ cᵢ·[productᵢ]."""
    if not rows:
        return float("nan")
    r = rows[-1]
    return sum(n * r.get(sp, 0.0) for sp, n in _C_PER.items())


def carbon_sustained_throughput(rows) -> float:
    """Settled sustained carbon-fixation throughput (mol-C/s) in the open-flow reactor.

    In the batch this collapses to ~0 at saturation; under washout it settles to a
    nonzero, condition-dependent steady rate — the real decision metric."""
    if not rows:
        return float("nan")
    tail = [r.get("net_carbon_flux", 0.0) for r in rows[-max(1, len(rows) // 10):]]
    return float(np.mean(tail))


def carbon_peak_flux(rows) -> float:
    """Peak net carbon-fixation rate over the run (mol-C per step)."""
    return max((r.get("net_carbon_flux", 0.0) for r in rows), default=0.0)


def carbon_sustained_frac(rows) -> float:
    """Fraction of peak flux still flowing at the end — 1 = sustained, ~0 = transient."""
    if not rows:
        return float("nan")
    fluxes = [r.get("net_carbon_flux", 0.0) for r in rows]
    pk = max(fluxes, default=0.0)
    if pk <= 0.0:
        return 0.0
    tail = np.mean(fluxes[-max(1, len(fluxes) // 10):])  # mean of final tenth
    return float(max(0.0, tail / pk))


def carbon_final_pmf(rows) -> float:
    """Loaded proton-motive force at the end (V) — the energy actually delivered."""
    if not rows:
        return float("nan")
    return float(rows[-1].get("pmf", 0.0))


def carbon_fixation_phase_map(
    *,
    ph_vent=(7.0, 11.0, 16),
    h2=(1.0e-4, 2.0e-2, 16),
    gradient_efficiency: float = 1.0,
    dilution_rate: float = 2.0,
    n_steps: int = 60,
    n_jobs: int = 1,
) -> SweepResult:
    """og-01 carbon-fixation landscape over (vent pH × dissolved H₂).

    Run in the OPEN-FLOW regime (``dilution_rate`` > 0) so the decision metric is
    sustained throughput, not a batch pool that saturates to the Preiner ceiling
    everywhere. ``ph_vent`` / ``h2`` are ``(lo, hi, n)``; H₂ is swept on a log grid
    (it spans decades). ``gradient_efficiency`` picks the arm: ``1.0`` favourable,
    ``~0.1`` the Tutolo-2026 in-situ collapse — plotting both on the same axes shows
    the favourable region shrinking.
    """
    from .composites.carbon_fixation import hydrothermal_carbon_fixation

    ph_lo, ph_hi, ph_n = ph_vent
    h2_lo, h2_hi, h2_n = h2
    axes = {
        "ph_vent": np.linspace(ph_lo, ph_hi, int(ph_n)),
        "h2": np.geomspace(h2_lo, h2_hi, int(h2_n)),
    }
    return sweep_grid(
        hydrothermal_carbon_fixation,
        axes,
        reduce={
            "sustained_throughput": carbon_sustained_throughput,  # primary decision surface
            "carbon_total": carbon_total,                         # steady reduced-carbon pool
            "sustained_frac": carbon_sustained_frac,
            "final_pmf": carbon_final_pmf,
        },
        fixed={"gradient_efficiency": float(gradient_efficiency),
               "dilution_rate": float(dilution_rate)},
        n_steps=n_steps,
        n_jobs=n_jobs,
    )


# ----------------------------------------------------------------------------
# og-02 — reduced carbon → protometabolism : the persistence / autocatalytic-gain map
# ----------------------------------------------------------------------------
# Decision: a protometabolic network is "alive" when it PERSISTS and SELF-AMPLIFIES
# against washout — the autocatalytic OAA hub stays populated and net carbon
# throughput is sustained. The controlling trade-off is feed vs dilution: enough
# geological carbon in, slow enough washout, and the rTCA loop ignites; starve the
# feed or flush too fast and it collapses. Swept over (feed CO₂ × washout rate).
def net_sustained_flux(rows) -> float:
    """Settled net carbon throughput (mol-C/s) — sustained if the network persists."""
    if not rows:
        return float("nan")
    tail = [r.get("net_carbon_flux", 0.0) for r in rows[-max(1, len(rows) // 10):]]
    return float(np.mean(tail))


def network_oaa_pool(rows) -> float:
    """Settled OAA hub concentration (M) — the autocatalytic loop's state; >0 and
    sustained means the self-amplifying cycle is populated, not washed out."""
    if not rows:
        return float("nan")
    return float(rows[-1].get("OAA", 0.0))


def network_gain(rows) -> float:
    """Settled autocatalytic gain (k_rtca·[CO2]/k_wash); >1 ⇒ self-amplifying."""
    if not rows:
        return float("nan")
    return float(rows[-1].get("autocatalytic_gain", 0.0))


def protometabolism_gain_phase_map(
    *,
    feed_CO2=(1.0e-4, 1.0e-2, 14),
    k_wash=(2.0e-3, 1.0, 14),
    k_rtca: float = 800.0,
    n_steps: int = 60,
    n_jobs: int = 1,
) -> SweepResult:
    """og-02 persistence / autocatalytic-gain landscape over (feed CO₂ × washout).

    Both axes are log (each spans decades). The primary surface is the settled OAA
    hub pool — the clearest witness of whether the autocatalytic cycle persists —
    with net throughput and the gain ratio alongside."""
    from .composites.protometabolism import protometabolic_network

    c_lo, c_hi, c_n = feed_CO2
    w_lo, w_hi, w_n = k_wash
    axes = {
        "feed_CO2": np.geomspace(c_lo, c_hi, int(c_n)),
        "k_wash": np.geomspace(w_lo, w_hi, int(w_n)),
    }
    return sweep_grid(
        protometabolic_network,
        axes,
        reduce={
            "oaa_pool": network_oaa_pool,            # primary: autocatalytic hub persistence
            "net_flux": net_sustained_flux,
            "gain": network_gain,
        },
        fixed={"k_rtca": float(k_rtca)},
        n_steps=n_steps,
        n_jobs=n_jobs,
    )


# ----------------------------------------------------------------------------
# og-04 — mineral compartments → protocells : the retention-access tradeoff
# ----------------------------------------------------------------------------
# Decision: a membrane is only useful if it RETAINS internal chemistry without
# SEVERING access to the external gradient. As permeability rises (driven by
# temperature / composition) the compartment sweeps from "too closed" (retains but
# starves) through a VIABLE window (individuality + access) to "too open" (leaks /
# washes out). Plotted as the retention-access plane; the Jordan mixed-amphiphile
# result (co-surfactant broadens the viable window) is the 2-D feasibility map.
def protocell_retention(rows) -> float:
    return float(rows[-1].get("retention", 0.0)) if rows else float("nan")


def protocell_access(rows) -> float:
    return float(rows[-1].get("access", 0.0)) if rows else float("nan")


def protocell_individuality(rows) -> float:
    """retention × access — individuality WITHOUT isolation (the viable product)."""
    return float(rows[-1].get("individuality_access", 0.0)) if rows else float("nan")


def protocell_retention_access_arc(
    *, temperature=(285.0, 360.0, 24), mix_fraction: float = 0.4, pH: float = 9.0,
    n_steps: int = 20, n_jobs: int = 1,
) -> SweepResult:
    """1-D sweep over temperature (the permeability driver) tracing the arc through
    (access, retention) space — too closed → viable → too open."""
    from .composites.mixed_amphiphile_protocell import mixed_amphiphile_protocell
    t_lo, t_hi, t_n = temperature
    axes = {"temperature": np.linspace(t_lo, t_hi, int(t_n))}
    return sweep_grid(
        mixed_amphiphile_protocell, axes,
        reduce={"retention": protocell_retention, "access": protocell_access,
                "individuality": protocell_individuality},
        fixed={"mix_fraction": float(mix_fraction), "pH": float(pH)},
        n_steps=n_steps, n_jobs=n_jobs,
    )


def protocell_feasibility_map(
    *, mix_fraction=(0.0, 0.6, 16), ionic_strength=(0.05, 1.2, 16),
    pH: float = 9.0, temperature: float = 318.15, n_steps: int = 20, n_jobs: int = 1,
) -> SweepResult:
    """2-D feasibility over (co-surfactant fraction × ionic strength): the viable salt
    ceiling RISES with mixed amphiphiles — vesicles survive at seawater salt and
    beyond only with enough co-surfactant (Jordan 2019). Primary surface =
    individuality (retention × access)."""
    from .composites.mixed_amphiphile_protocell import mixed_amphiphile_protocell
    m_lo, m_hi, m_n = mix_fraction
    i_lo, i_hi, i_n = ionic_strength
    axes = {"mix_fraction": np.linspace(m_lo, m_hi, int(m_n)),
            "ionic_strength": np.linspace(i_lo, i_hi, int(i_n))}
    return sweep_grid(
        mixed_amphiphile_protocell, axes,
        reduce={"individuality": protocell_individuality,
                "retention": protocell_retention, "access": protocell_access},
        fixed={"pH": float(pH), "temperature": float(temperature)},
        n_steps=n_steps, n_jobs=n_jobs,
    )


# ----------------------------------------------------------------------------
# og-06 — chemistry → heredity : the error-threshold phase map
# ----------------------------------------------------------------------------
# The agent-based lineage (viva_genesis.heredity.lineage) is NOT a composite, so
# this builder loops the real simulator directly and assembles a SweepResult by
# hand (same dataclass the Workbench renders). The decision metric is the lineage's
# FUNCTIONAL PERSISTENCE at the final generation = mean phenotype function × surviving-
# population fraction. Mean function alone is survivor-biased (a near-collapsed
# lineage's few lucky survivors can read high-φ), so it is weighted by how much of the
# carrying capacity the lineage still holds: above the Eigen error threshold a template
# lineage holds BOTH its function and its numbers; below it it ratchets down and crashes
# (the error catastrophe). The boundary Q = fidelity^length = const is a curve in
# (fidelity × length) space — and the non-template modules (compositional / hybrid) are
# sampled as reference lines, persisting where a long template cannot ("heredity need
# not presume a long, high-fidelity template").
_PERSIST_THRESHOLD = 0.35   # functional persistence above this = information retained


def _lineage_persistence(r: dict, capacity: int) -> float:
    """Functional persistence = mean function × surviving fraction of capacity."""
    frac = min(float(r.get("final_population", 0)) / max(capacity, 1), 1.0)
    return float(r.get("final_function", 0.0)) * frac


def heredity_error_threshold_map(
    *, per_site_fidelity=(0.90, 0.995, 14), length=(6, 44, 12),
    n_gen: int = 40, seed: int = 1, replicates: int = 1, capacity: int = 220,
) -> SweepResult:
    """2-D Decision view over (per-site fidelity × template length) for the TEMPLATE
    module: final-generation functional persistence (function × surviving fraction) and
    a persists mask trace the Eigen error threshold Q = fidelity^length.
    ``meta['reference_modules']`` records where the non-template modules land (length-
    independent compositional / hybrid, and the non-heritable control) so the figure can
    overlay them. Serial (the simulator is fast); a higher-res grid is a persisted
    artifact runner's job."""
    from .heredity.lineage import simulate_lineage

    f_lo, f_hi, f_n = per_site_fidelity
    l_lo, l_hi, l_n = length
    f_axis = np.linspace(f_lo, f_hi, int(f_n))
    l_axis = np.round(np.linspace(l_lo, l_hi, int(l_n))).astype(int)

    persistence = np.zeros((int(f_n), int(l_n)))
    final_fn = np.zeros((int(f_n), int(l_n)))
    q_whole = np.zeros((int(f_n), int(l_n)))
    for i, f in enumerate(f_axis):
        for j, L in enumerate(l_axis):
            runs = [simulate_lineage("template", per_site_fidelity=float(f), length=int(L),
                                     n_gen=n_gen, capacity=capacity, seed=seed + k)
                    for k in range(max(int(replicates), 1))]
            persistence[i, j] = float(np.mean([_lineage_persistence(r, capacity) for r in runs]))
            final_fn[i, j] = float(np.mean([r["final_function"] for r in runs]))
            q_whole[i, j] = float(f) ** int(L)
    persists = (persistence > _PERSIST_THRESHOLD).astype(float)

    # Reference modules: the non-template heredity mechanisms, as (persistence,
    # realized heritability) — length-independent, so they plot as horizontal bands.
    refs = {}
    for mod in ("compositional", "hybrid", "non-heritable"):
        r = simulate_lineage(mod, per_site_fidelity=0.98, length=30, n_gen=n_gen,
                             capacity=capacity, seed=seed)
        refs[mod] = {"persistence": round(_lineage_persistence(r, capacity), 4),
                     "final_function": round(r["final_function"], 4),
                     "heritability": round(float(r["heritability"]), 4)}

    return SweepResult(
        axis_order=["per_site_fidelity", "length"],
        axes={"per_site_fidelity": f_axis, "length": l_axis.astype(float)},
        surfaces={"persistence": persistence, "persists": persists,
                  "final_function": final_fn, "whole_fidelity": q_whole},
        meta={"model": "agent_based_lineage", "module": "template", "n_gen": n_gen,
              "persist_threshold": _PERSIST_THRESHOLD, "capacity": capacity,
              "reference_modules": refs},
    )


# ----------------------------------------------------------------------------
# og-08 — escape from the vent : the off-gradient survival frontier
# ----------------------------------------------------------------------------
# Decision: as the geological reactor's support is withdrawn (external gradient,
# mineral/FeS access, feed all relaxing toward zero), which minimum INNOVATION SET lets
# a lineage persist? The budget is co-limited (energy AND resources), so a lone
# innovation is a cost without a co-benefit — the set is irreducible. Swept over
# (environmental-support level × innovation-set); the pass region (persistence) reaches
# support→0 only for the FULL set, and each single knockout lifts the frontier. The
# off-gradient lineage model is deterministic (no RNG), so the surface is reproducible
# and built by hand (same SweepResult the Workbench renders).
_OFFGRID_PERSIST_THRESHOLD = 0.5   # surviving-fraction above this = the lineage persists

# The innovation-set axis (full set, each single knockout, and the bare control).
_INNOVATION_SETS = [
    ("full", {"has_pump": 1.0, "has_importer": 1.0, "has_heredity": 1.0}),
    ("-pump", {"has_pump": 0.0, "has_importer": 1.0, "has_heredity": 1.0}),
    ("-importer", {"has_pump": 1.0, "has_importer": 0.0, "has_heredity": 1.0}),
    ("-heredity", {"has_pump": 1.0, "has_importer": 1.0, "has_heredity": 0.0}),
    ("none", {"has_pump": 0.0, "has_importer": 0.0, "has_heredity": 0.0}),
]


def off_gradient_phase_map(
    *, support=(0.0, 1.0, 16), n_steps: int = 60, catalyst_efficiency: float = 1.0,
) -> SweepResult:
    """2-D Decision view over (environmental-support level × innovation-set) for the
    off-gradient lineage: final-run persistence (surviving fraction) and a persists mask
    trace the SURVIVAL FRONTIER. The frontier (minimum support at which each set
    persists) is recorded in ``meta['frontier']`` — the full set reaches support→0 while
    each single knockout is lifted off the gradient. Serial (the model is fast);
    a higher-res grid is the persisted-artifact runner's job."""
    from .autonomy.off_gradient import simulate_offgradient

    s_lo, s_hi, s_n = support
    s_axis = np.linspace(s_lo, s_hi, int(s_n))
    set_axis = np.arange(len(_INNOVATION_SETS), dtype=float)

    persistence = np.zeros((int(s_n), len(_INNOVATION_SETS)))
    for i, s in enumerate(s_axis):
        for j, (_, flags) in enumerate(_INNOVATION_SETS):
            persistence[i, j] = simulate_offgradient(
                float(s), n_steps=n_steps, catalyst_efficiency=catalyst_efficiency, **flags)["survivors"]
    persists = (persistence >= _OFFGRID_PERSIST_THRESHOLD).astype(float)

    # Survival frontier: the minimum support level at which each set persists.
    frontier = {}
    for j, (label, _) in enumerate(_INNOVATION_SETS):
        col = persists[:, j]
        frontier[label] = float(s_axis[int(np.argmax(col > 0))]) if col.any() else None

    return SweepResult(
        axis_order=["support", "innovation_set"],
        axes={"support": s_axis, "innovation_set": set_axis},
        surfaces={"persistence": persistence, "persists": persists},
        meta={"model": "off_gradient_autonomy", "n_steps": int(n_steps),
              "persist_threshold": _OFFGRID_PERSIST_THRESHOLD,
              "innovation_sets": [label for label, _ in _INNOVATION_SETS],
              "frontier": frontier},
    )


# ----------------------------------------------------------------------------
# og-07 — ecology before LUCA : where cross-feeding robustness EMERGES
# ----------------------------------------------------------------------------
# Decision: a metacommunity of connected pore compartments develops functional
# REDUNDANCY (robustness) that an isolated compartment cannot — but only in a bounded
# region of (exchange_rate × diversity). With too little diversity the compartments
# are near-identical, so cross-feeding/HGT have nothing to share and robustness stays
# at the sparse intrinsic floor; with too little exchange, a diverse-but-disconnected
# set holds a broad repertoire fragilely (each capability in one compartment). Only
# where BOTH are high do capabilities spread into redundant coverage. The LUCA overlap
# climbs alongside and is reported as a BOUNDARY the emergent repertoire approaches,
# never a fitting target. Reducers are module-level so sweep_grid can fan the grid
# out over a process pool / Ray.
_ROBUST_EMERGE_THRESHOLD = 0.5   # metacommunity robustness above this = redundancy emerged


def metacommunity_robustness_final(rows) -> float:
    """Settled metacommunity robustness (functional redundancy) at the final tick."""
    return float(rows[-1].get("metacommunity_robustness", 0.0)) if rows else float("nan")


def metacommunity_isolated_final(rows) -> float:
    """Settled isolated-counterfactual robustness (same seeded assignment, no exchange)."""
    return float(rows[-1].get("isolated_robustness", 0.0)) if rows else float("nan")


def metacommunity_diversity_final(rows) -> float:
    """Settled mean per-compartment functional breadth (collective diversity)."""
    return float(rows[-1].get("capability_diversity", 0.0)) if rows else float("nan")


def metacommunity_luca_final(rows) -> float:
    """Settled overlap of the collective repertoire with the anaerobic LUCA core
    (a reported boundary, not a target)."""
    return float(rows[-1].get("luca_capability_overlap", 0.0)) if rows else float("nan")


def metacommunity_robustness_phase_map(
    *, exchange_rate=(0.02, 0.8, 16), diversity=(0.05, 1.0, 16),
    parasite_load: float = 0.0, hgt_rate: float = 0.1, n_compartments: int = 8,
    seed: int = 1, n_steps: int = 40, n_jobs: int = 1,
) -> SweepResult:
    """og-07 Decision view over (cross-feeding exchange_rate × inter-compartment
    diversity): the metacommunity-robustness emergence boundary. Primary surface =
    ``robustness`` (functional redundancy), with the isolated counterfactual, the
    collective ``capability_diversity`` and the ``luca_overlap`` boundary alongside.

    Both axes start strictly above 0.0 on purpose — process-bigraph's config merge
    ignores a falsy 0.0 override, so the true isolated / homogeneous edges are read
    from the process's internal counterfactual, not from a 0.0 sweep point. The
    composite is pure-numpy and fast, so this sweeps the real generator with
    :func:`sweep_grid`; a higher-res grid is the artifact runner's job."""
    from .composites.cross_feeding_metacommunity import cross_feeding_metacommunity

    e_lo, e_hi, e_n = exchange_rate
    d_lo, d_hi, d_n = diversity
    axes = {
        "exchange_rate": np.linspace(e_lo, e_hi, int(e_n)),
        "diversity": np.linspace(d_lo, d_hi, int(d_n)),
    }
    return sweep_grid(
        cross_feeding_metacommunity,
        axes,
        reduce={
            "robustness": metacommunity_robustness_final,           # primary decision surface
            "capability_diversity": metacommunity_diversity_final,
            "luca_overlap": metacommunity_luca_final,
            "isolated_robustness": metacommunity_isolated_final,
        },
        fixed={"parasite_load": float(parasite_load), "hgt_rate": float(hgt_rate),
               "n_compartments": int(n_compartments), "seed": int(seed)},
        n_steps=n_steps,
        n_jobs=n_jobs,
    )


# og-07 Decision (ecology_): the robustness-vs-parasite phase map. Where
# metacommunity_robustness_phase_map sweeps (exchange × diversity) — the raw material
# and the spreading mechanism — this second slice holds diversity at the canonical
# operating point and sweeps (cross-feeding exchange_rate × parasite_load): robustness
# EMERGES above the floor once exchange crosses ~0.2, but a rising parasite load (drain
# on neighbours) pushes the community back below the emergence threshold. The PASS
# region (robustness ≥ threshold) is the cooperative, well-connected corner.
def ecology_robustness_parasite_map(
    *, exchange_rate=(0.02, 0.8, 16), parasite_load=(0.0, 0.9, 16),
    diversity: float = 0.75, hgt_rate: float = 0.1, n_compartments: int = 8,
    seed: int = 1, n_steps: int = 40, n_jobs: int = 1,
) -> SweepResult:
    """og-07 Decision view over (cross-feeding exchange_rate × parasite_load) at the
    canonical inter-compartment diversity. Primary surface = ``robustness`` (functional
    redundancy), with the LUCA-overlap boundary alongside. Cross-feeding robustness
    emerges in the well-connected, low-parasite corner and collapses as parasites drain
    their neighbours — a PASS/FAIL boundary at ``_ROBUST_EMERGE_THRESHOLD``."""
    from .composites.cross_feeding_metacommunity import cross_feeding_metacommunity

    e_lo, e_hi, e_n = exchange_rate
    p_lo, p_hi, p_n = parasite_load
    axes = {
        "exchange_rate": np.linspace(e_lo, e_hi, int(e_n)),
        "parasite_load": np.linspace(p_lo, p_hi, int(p_n)),
    }
    res = sweep_grid(
        cross_feeding_metacommunity,
        axes,
        reduce={
            "robustness": metacommunity_robustness_final,
            "luca_overlap": metacommunity_luca_final,
            "isolated_robustness": metacommunity_isolated_final,
        },
        fixed={"diversity": float(diversity), "hgt_rate": float(hgt_rate),
               "n_compartments": int(n_compartments), "seed": int(seed)},
        n_steps=n_steps,
        n_jobs=n_jobs,
    )
    res.meta.update({"stage": "og-07", "model": "cross_feeding_metacommunity_parasite",
                     "robust_emerge_threshold": _ROBUST_EMERGE_THRESHOLD,
                     "diversity": float(diversity)})
    return res


# ----------------------------------------------------------------------------
# og-adv — adversarial control : vent-specificity of the carbon-fixation gate
# ----------------------------------------------------------------------------
# The og-01 "net-carbon-flux-nonzero-region" gate passes only when BOTH the Fe/Ni/S
# catalytic interface is active AND dissolved H2 (the reductant) is present — i.e.
# in the vent corner. A generic non-vent mixture (no catalyst, no sustained H2) sits
# at the origin of this plane, far below the gate threshold. Swept over
# (dissolved H2 x catalyst activity); the gate's PASS region IS the vent corner, so
# the plane shows the gate REJECTING generic chemistry rather than measuring generic
# nonequilibrium chemistry.
def vent_specificity_map(
    *,
    h2=(1.0e-9, 2.0e-2, 16),
    catalyst_active=(0.0, 1.0, 16),
    gradient_efficiency: float = 1.0,
    dilution_rate: float = 2.0,
    n_steps: int = 60,
    n_jobs: int = 1,
) -> SweepResult:
    """og-adv vent-specificity plane over (dissolved H₂ × Fe/Ni/S catalyst activity).

    Reuses the real og-01 ``hydrothermal_carbon_fixation`` composite. ``h2`` is swept
    on a log grid (it spans decades, down to a generic ~0); ``catalyst_active`` linearly
    from 0 (no mineral interface) to 1 (full vent). The primary surface is the peak net
    carbon-fixation flux the og-01 gate reads; ``GATE_THRESHOLD`` marks the pass/fail
    boundary (> 1e-6). The generic-control corner (H₂≈0, catalyst=0) is deep in the
    fail region; only the vent corner passes.
    """
    from .composites.carbon_fixation import hydrothermal_carbon_fixation

    h2_lo, h2_hi, h2_n = h2
    cat_lo, cat_hi, cat_n = catalyst_active
    axes = {
        "h2": np.geomspace(h2_lo, h2_hi, int(h2_n)),
        "catalyst_active": np.linspace(cat_lo, cat_hi, int(cat_n)),
    }
    res = sweep_grid(
        hydrothermal_carbon_fixation,
        axes,
        reduce={
            "peak_flux": carbon_peak_flux,                       # the og-01 net-flux gate
            "sustained_throughput": carbon_sustained_throughput,
            "carbon_total": carbon_total,
        },
        fixed={"gradient_efficiency": float(gradient_efficiency),
               "dilution_rate": float(dilution_rate)},
        n_steps=n_steps,
        n_jobs=n_jobs,
    )
    res.meta.update({
        "stage": "og-adv", "model": "vent_specificity_control",
        "gate": "net-carbon-flux-nonzero-region", "gate_threshold": 1.0e-6,
        "vent_corner": {"h2": float(h2_hi), "catalyst_active": 1.0},
        "generic_corner": {"h2": float(h2_lo), "catalyst_active": 0.0},
    })
    return res


# ----------------------------------------------------------------------------
# og-res — nitrogen as a limiting resource : the C:N supply-ratio landscape
# ----------------------------------------------------------------------------
# Carbon fixation is not the only requirement — every amino acid and nucleobase needs
# REDUCED nitrogen (NH4+), and the early ocean's accessible N was oxidised (NO3-/NO2-)
# or inert (N2). Decision: does FeS-mediated reduced-N production keep pace with the
# carbon-fixation demand, or does nitrogen become limiting first? The controlling
# trade-off is the nitrate feed vs the FeS catalyst activity: feed enough NO3- over an
# active mineral and the C:N supply ratio (carbon demand / reduced-N production) sits at
# ~Redfield (N keeps pace); starve the feed or passivate the mineral and the ratio blows
# up (N limiting). Swept over (nitrate supply x FeS activity). Reducers are module-level
# so sweep_grid can fan the grid out over a process pool / Ray.
_CN_KEEPS_PACE_THRESHOLD = 8.0   # C:N supply ratio at/below which reduced N keeps pace


def nitrogen_cn_ratio_settled(rows) -> float:
    """Settled C:N supply ratio (carbon demand / reduced-N production). <= ~Redfield
    means reduced N keeps pace with carbon; large means nitrogen is limiting."""
    if not rows:
        return float("nan")
    tail = rows[-max(1, len(rows) // 5):]
    return float(np.mean([min(r.get("cn_supply_ratio", float("nan")), 1.0e6) for r in tail]))


def nitrogen_production_settled(rows) -> float:
    """Settled reduced-nitrogen (ammonium) production rate (mol/s)."""
    if not rows:
        return float("nan")
    tail = rows[-max(1, len(rows) // 5):]
    return float(np.mean([r.get("nh4_production_rate", 0.0) for r in tail]))


def nitrogen_nh4_settled(rows) -> float:
    """Settled ammonium pool (M) — the standing reduced-N the stage accumulates."""
    return float(rows[-1].get("NH4", 0.0)) if rows else float("nan")


def nitrogen_keeps_pace(rows) -> float:
    """1.0 where the settled C:N supply ratio is at/below the keeps-pace threshold."""
    cn = nitrogen_cn_ratio_settled(rows)
    if cn != cn:  # nan
        return 0.0
    return 1.0 if cn <= _CN_KEEPS_PACE_THRESHOLD else 0.0


def nitrogen_assimilation_phase_map(
    *,
    no3_supply=(2.0e-6, 1.0e-4, 16),
    fes_activity=(0.05, 1.0, 16),
    h2: float = 5.0e-3,
    temperature: float = 353.15,
    c_demand: float = 1.0e-4,
    loss_rate: float = 1.0e-2,
    no3_init: float = 1.0e-4,
    n_steps: int = 140,
    n_jobs: int = 1,
) -> SweepResult:
    """og-res reduced-nitrogen landscape over (nitrate supply x FeS activity).

    Run open-flow (``loss_rate`` > 0) so the decision metric is the sustained C:N
    supply ratio, not a batch pool. ``no3_supply`` is swept on a log grid (it spans
    decades); ``fes_activity`` linearly in (0, 1]. The primary surface is the C:N
    supply ratio — below ~Redfield (``_CN_KEEPS_PACE_THRESHOLD``) reduced N keeps pace
    with carbon; above it nitrogen is limiting. The ``keeps_pace`` mask traces the
    PASS boundary, with the ammonium-production rate and standing pool alongside."""
    from .composites.nitrogen_assimilation import reduced_nitrogen_reactor

    s_lo, s_hi, s_n = no3_supply
    f_lo, f_hi, f_n = fes_activity
    axes = {
        "no3_supply": np.geomspace(s_lo, s_hi, int(s_n)),
        "fes_activity": np.linspace(f_lo, f_hi, int(f_n)),
    }
    return sweep_grid(
        reduced_nitrogen_reactor,
        axes,
        reduce={
            "cn_ratio": nitrogen_cn_ratio_settled,       # primary decision surface
            "keeps_pace": nitrogen_keeps_pace,
            "nh4_production": nitrogen_production_settled,
            "nh4_pool": nitrogen_nh4_settled,
        },
        fixed={"h2": float(h2), "temperature": float(temperature),
               "c_demand": float(c_demand), "loss_rate": float(loss_rate),
               "no3_init": float(no3_init)},
        n_steps=n_steps,
        n_jobs=n_jobs,
    )


# ----------------------------------------------------------------------------
# og-res-phosphorus — the phosphorus bottleneck : the reactive-P availability map
# ----------------------------------------------------------------------------
# Decision: phosphorus may be a HARDER bottleneck than carbon — dissolved phosphate
# precipitates / adsorbs onto minerals before it is chemically useful. The question
# is whether the SAME thermal-gradient pore that concentrates carbon (og-03) can
# co-concentrate P enough that reactive-P formation outpaces the precipitation sink.
# Swept over (phosphate source × pore/thermal enrichment): the reactive route wins
# only where enrichment lifts the condensation/activation fluxes above the
# first-order precipitation loss. The PASS region is where reactive-P availability
# beats loss (net > 0) AND the enrichment co-concentrates carbon (enr >= the carbon
# co-concentration floor the same og-03 pore provides). Reducers are module-level so
# sweep_grid can fan the grid out over a process pool / Ray.
_CARBON_COCONC_FLOOR = 10.0   # pore enrichment at which the same trap also concentrates carbon usefully


def phosphorus_reactive_pool(rows) -> float:
    """Settled standing reactive-P pool (M) — the available reactive phosphorus."""
    if not rows:
        return float("nan")
    tail = [r.get("reactive_P", 0.0) for r in rows[-max(1, len(rows) // 5):]]
    return float(np.mean(tail))


def phosphorus_net_available(rows) -> float:
    """Settled net reactive-P availability (mol/s) = production − precipitation loss;
    > 0 ⇒ reactive P is produced faster than phosphate precipitates."""
    if not rows:
        return float("nan")
    tail = [r.get("net_reactive_P", 0.0) for r in rows[-max(1, len(rows) // 5):]]
    return float(np.mean(tail))


def phosphorus_precipitated_fraction(rows) -> float:
    """Final mineral-bound (precipitated/adsorbed) fraction of total P."""
    return float(rows[-1].get("precipitated_fraction", 0.0)) if rows else float("nan")


def phosphorus_availability_map(
    *,
    phosphate_supply=(1.0e-6, 1.0e-3, 14),
    pore_enrichment=(1.0, 60.0, 14),
    temperature: float = 333.15,
    loss_rate: float = 0.08,
    n_steps: int = 120,
    n_jobs: int = 1,
) -> SweepResult:
    """og-res-phosphorus Decision view over (phosphate source × pore/thermal
    enrichment): the reactive-P availability landscape. Primary surface = the
    settled reactive-P pool, with the net availability (production − loss) and the
    precipitated fraction alongside. ``meta['carbon_coconc_floor']`` records the
    enrichment at which the same og-03 pore also concentrates carbon, so the figure
    can mark the PASS region = net availability > 0 AND enrichment >= that floor
    (reactive P wins AND co-concentrates with carbon). The supply axis is log (it
    spans decades); the enrichment axis is linear. The composite is a fast
    libRoadRunner ODE, so this sweeps the real generator with :func:`sweep_grid`; a
    higher-res grid is the artifact runner's job."""
    from .composites.phosphorus_availability import phosphorus_availability

    s_lo, s_hi, s_n = phosphate_supply
    e_lo, e_hi, e_n = pore_enrichment
    axes = {
        "phosphate_supply": np.geomspace(s_lo, s_hi, int(s_n)),
        "pore_enrichment": np.linspace(e_lo, e_hi, int(e_n)),
    }
    res = sweep_grid(
        phosphorus_availability,
        axes,
        reduce={
            "reactive_pool": phosphorus_reactive_pool,          # primary decision surface
            "net_available": phosphorus_net_available,
            "precipitated_fraction": phosphorus_precipitated_fraction,
        },
        fixed={"temperature": float(temperature), "loss_rate": float(loss_rate)},
        n_steps=n_steps,
        n_jobs=n_jobs,
    )
    res.meta["carbon_coconc_floor"] = _CARBON_COCONC_FLOOR
    return res


# ----------------------------------------------------------------------------
# og-proto-energetics — an energy currency before modern pumping : the
# free-energy-capture phase map
# ----------------------------------------------------------------------------
# Decision: a pre-ATP energy currency is viable when it CAPTURES environmental free
# energy into a transferable store that STAYS CHARGED under endergonic load — not
# merely when a reaction runs downhill. The controlling trade-off is the geochemical
# drive vs the coupling chemistry: the drive ΔG must clear the carrier's high-energy
# bond (a thermodynamic gate), and the coupling must be efficient enough that the
# charging flux beats discharge + hydrolysis. Swept over (free-energy drive ×
# coupling efficiency); the PASS region is "net transferable currency maintained
# above threshold under load". Reducers are module-level so sweep_grid can fan the
# grid out over a process pool / Ray. All symbols energy_*-prefixed (shared file).
_ENERGY_CURRENCY_THRESHOLD = 0.25   # charged fraction above this (under load) = currency maintained


def energy_charge_fraction_final(rows) -> float:
    """Settled charged fraction of the carrier pool at the final tick — is the
    transferable currency MAINTAINED under load (not just transiently charged)?"""
    return float(rows[-1].get("energy_charge_fraction", 0.0)) if rows else float("nan")


def energy_stored_work_fraction_final(rows) -> float:
    """Final fraction of input geochemical free energy captured as transferable
    usable work ((work + stored)/input) — the rest is dissipated."""
    return float(rows[-1].get("energy_stored_work_fraction", 0.0)) if rows else float("nan")


def energy_work_final(rows) -> float:
    """Cumulative useful endergonic work delivered (kJ/liter) over the run."""
    return float(rows[-1].get("energy_work", 0.0)) if rows else float("nan")


def proto_energetics_map(
    *, drive_free_energy=(15.0, 70.0, 16), coupling_efficiency=(0.05, 1.0, 16),
    carrier_pool: float = 1.0e-3, loss_rate: float = 0.05, load: float = 0.20,
    carrier: str = "thioester", n_steps: int = 60, n_jobs: int = 1,
) -> SweepResult:
    """og-proto-energetics Decision view over (geochemical free-energy drive ×
    coupling efficiency): where a transferable energy currency is maintained above
    threshold under endergonic load. Primary surface = settled ``charge_fraction``
    (the currency maintained), with the captured stored-work fraction and the useful
    work delivered alongside. The drive axis spans below the thioester bond (~35
    kJ/mol, where the drive cannot charge the carrier) to well above it; the
    efficiency axis starts strictly above 0.0 (a literal 0.0 is the ablation, read
    from the composite's no-coupling control, not a sweep point). The composite is
    pure-numpy and fast, so this sweeps the real generator with :func:`sweep_grid`;
    a higher-res grid is the persisted-artifact runner's job."""
    from .composites.proto_energetics import proto_energetics

    d_lo, d_hi, d_n = drive_free_energy
    e_lo, e_hi, e_n = coupling_efficiency
    axes = {
        "drive_free_energy": np.linspace(d_lo, d_hi, int(d_n)),
        "coupling_efficiency": np.linspace(e_lo, e_hi, int(e_n)),
    }
    res = sweep_grid(
        proto_energetics,
        axes,
        reduce={
            "charge_fraction": energy_charge_fraction_final,           # primary decision surface
            "stored_work_fraction": energy_stored_work_fraction_final,
            "work": energy_work_final,
        },
        fixed={"carrier_pool": float(carrier_pool), "loss_rate": float(loss_rate),
               "load": float(load), "carrier": str(carrier)},
        n_steps=n_steps,
        n_jobs=n_jobs,
    )
    res.meta["energy_currency_threshold"] = _ENERGY_CURRENCY_THRESHOLD
    # The carrier bond energy marks the drive-axis gate (drive must clear it).
    from .bioenergetics.proto_energetics import CARRIER_BOND_KJMOL
    res.meta["carrier_bond_kjmol"] = CARRIER_BOND_KJMOL.get(str(carrier), 35.0)
    res.meta["carrier"] = str(carrier)
    return res


# ----------------------------------------------------------------------------
# og-growth-division — metabolism → osmotic growth & division : the viable band
# ----------------------------------------------------------------------------
# Decision: a protocell should not merely persist — its chemistry should change its
# physical fate. The internal autocatalytic source makes an osmolyte; its
# accumulation sets the osmotic pressure that pulls water in and grows the
# compartment to the division threshold. The controlling trade-off is the internal
# throughput against the membrane permeability: retain enough product to build the
# osmotic drive, yet leak enough to keep the pressure below the burst tension. Swept
# over (network throughput × membrane permeability); the PASS region is sustained net
# growth leading to DIVISION — a BOUNDED viable band between STARVATION (too
# permeable: product leaks, no osmotic build-up) and LYSIS (too impermeable: pressure
# spikes past the burst tension). outcome_code: 0 starve · 1 grow-no-division · 2
# divide · 3 lysis.
_OSMOTIC_STARVE, _OSMOTIC_GROW, _OSMOTIC_DIVIDE, _OSMOTIC_LYSIS = 0, 1, 2, 3


def growth_divisions_final(rows) -> float:
    """Final cumulative division count — the headline decision metric (>=1 ⇒ the
    compartment's chemistry drove net growth to DIVISION)."""
    return float(rows[-1].get("division_count", 0.0)) if rows else float("nan")


def growth_net_growth_final(rows) -> float:
    """Final net volume growth factor V/V0 (>1 ⇒ the compartment expanded)."""
    return float(rows[-1].get("net_growth", 0.0)) if rows else float("nan")


def growth_lysed_final(rows) -> float:
    """1 if the compartment burst (osmotic pressure exceeded the membrane tension)."""
    return float(rows[-1].get("lysed", 0.0)) if rows else float("nan")


def growth_outcome_final(rows) -> float:
    """Physical fate code: 0 starve · 1 grow-no-division · 2 divide · 3 lysis."""
    return float(rows[-1].get("outcome_code", 0.0)) if rows else float("nan")


def growth_peak_pressure(rows) -> float:
    """Peak osmotic pressure (Pa) over the run — bounded in the viable band, spiking in
    the lysis regime."""
    return max((r.get("osmotic_pressure", 0.0) for r in rows), default=float("nan"))


def growth_division_map(
    *,
    network_throughput=(1.0e-21, 1.0e-18, 16),
    membrane_permeability=(1.0e-10, 1.0e-4, 16),
    autocatalytic_rate: float = 0.5,
    division_threshold: float = 6.4e-17,
    leak_rate: float = 1.0,
    n_steps: int = 100,
    n_jobs: int = 1,
) -> SweepResult:
    """og-growth-division Decision view over (network throughput × membrane permeability).

    Both axes are log (each spans decades) and start strictly above 0.0 on purpose —
    process-bigraph's config merge ignores a falsy 0.0 override, so the true zero-
    throughput / zero-permeability edges are read from the run's cross-run ablation
    arm, not from a 0.0 sweep point. The primary surface is ``divisions`` (the clearest
    witness that chemistry drove net growth to DIVISION); ``outcome`` (0 starve · 1
    grow-no-division · 2 divide · 3 lysis), ``net_growth``, ``lysed`` and
    ``peak_pressure`` are alongside so the figure can draw the bounded viable band
    between starvation and lysis. ``meta['viable_fraction']`` records the share of the
    grid in sustained growth → division. The composite is pure-numpy and fast, so this
    sweeps the real generator with :func:`sweep_grid`; a higher-res grid is the
    artifact runner's job."""
    from .composites.osmotic_growth_division import osmotic_growth_division

    t_lo, t_hi, t_n = network_throughput
    p_lo, p_hi, p_n = membrane_permeability
    axes = {
        "network_throughput": np.geomspace(t_lo, t_hi, int(t_n)),
        "membrane_permeability": np.geomspace(p_lo, p_hi, int(p_n)),
    }
    res = sweep_grid(
        osmotic_growth_division,
        axes,
        reduce={
            "divisions": growth_divisions_final,          # primary decision surface
            "outcome": growth_outcome_final,
            "net_growth": growth_net_growth_final,
            "lysed": growth_lysed_final,
            "peak_pressure": growth_peak_pressure,
        },
        fixed={"autocatalytic_rate": float(autocatalytic_rate),
               "division_threshold": float(division_threshold),
               "leak_rate": float(leak_rate)},
        n_steps=n_steps,
        n_jobs=n_jobs,
    )
    divides = np.asarray(res.surfaces["divisions"], float) >= 1.0
    res.meta["viable_fraction"] = float(np.mean(divides))
    res.meta["outcome_legend"] = {"0": "starve", "1": "grow-no-division",
                                  "2": "divide", "3": "lysis"}
    return res
