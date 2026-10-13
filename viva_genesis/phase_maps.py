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
