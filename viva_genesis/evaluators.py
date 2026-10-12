"""Workspace evaluator hook — machine-gradeable readouts for og-00 behavior tests.

``viva_superpowers.study_evaluator`` calls ``register_derived_scalars(reg)`` on
this module (it is imported as ``<package_path>.evaluators``). Each registered
computer ``fn(reader, test, ws_root) -> float`` turns a persisted run store into
a single scalar the evaluator then grades with the study's ``pass_if`` op — so a
``behavior_test`` whose ``measure.path`` names one of these keys auto-grades
PASS/FAIL from real run data, no agent in the loop.

These read the Campaign-0 vent-reactor observables (temperature, pH, H2_flux,
charge_imbalance, flux_divergence_residual) that the ``og_00_vent_reactor_baseline``
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
