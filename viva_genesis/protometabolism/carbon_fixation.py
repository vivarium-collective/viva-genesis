"""Module D (kinetics) — mineral-catalyzed, gradient-driven CO2 reduction.

Lab-calibrated heterogeneous kinetics for H2-driven CO2 fixation to formate,
acetate and pyruvate over Fe/Ni/S minerals (greigite / magnetite / awaruite),
calibrated to the Preiner-2020 and Hudson-2020 benchmarks (the hypothesis
explicitly calls for lab-calibrated rates, not first-principles surface kinetics).

The rate of each product is GATED by the four things that actually control
origins-of-life carbon fixation, so the controls kill it honestly:

  rate = k · catalyst · feasible(ΔG', eQuilibrator) · drive(pmf) · avail(H2,CO2)
           · T-window · (1 − product/product_max)

- ``feasible`` comes from the real eQuilibrator thermo gate (Module D thermo):
  fixation stops where ΔG' ≥ 0 (product inhibition / infeasible region).
- ``drive(pmf)`` ties formate to the pH-gradient proton-motive force (Hudson
  2020: remove the gradient and formate vanishes) — Michaelis in pmf.
- ``avail`` needs both H2 and CO2; ``catalyst`` needs an active mineral.
- product ceilings reproduce the Preiner yields (formate ≲200 mM, acetate
  ≲100 µM, pyruvate ≲10 µM at 100 C).

``net_carbon_flux`` sums the carbon fixed per second (1·formate + 2·acetate +
3·pyruvate rates) — zero in every control and in the Tutolo-collapsed arm.
"""
from __future__ import annotations

import math

from process_bigraph import Process

_MOLAR = {"_type": "float", "_units": "molar"}
_K = {"_type": "float", "_units": "kelvin"}
_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_V = {"_type": "float", "_units": "volt"}
_MOLS = {"_type": "float", "_units": "mole/second"}

# Preiner-2020 product ceilings (molar) at ~100 C.
_YIELD_MAX = {"formate": 0.2, "acetate": 1.0e-4, "pyruvate": 1.0e-5}
# Rate constants (per second) — calibrated so the favorable arm approaches the
# ceilings over a ~120-step run and the ratios match the benchmark hierarchy.
_K_RATE = {"formate": 0.05, "acetate": 2.5e-5, "pyruvate": 2.5e-6}
_CARBON = {"formate": 1, "acetate": 2, "pyruvate": 3}


class CarbonFixationProcess(Process):
    """Lab-calibrated mineral-catalyzed CO2 reduction, gated by thermodynamic
    feasibility, proton-motive drive, substrate availability and catalyst.

    Emits product concentration increments (bare ``float`` deltas — pools
    accumulate) and the net organic-carbon flux (overwrite sensor)."""

    config_schema = {
        "pmf_half": {"_type": "float", "_default": 0.08},           # V, half-max drive
        "km_h2": {"_type": "float", "_default": 1.0e-4},            # M
        "km_co2": {"_type": "float", "_default": 1.0e-4},          # M
        "t_opt": {"_type": "float", "_default": 373.15},           # K (~100 C, Preiner)
        "t_width": {"_type": "float", "_default": 60.0},           # K
        "reactor_volume_scale": {"_type": "float", "_default": 1.0},  # L, flux scaling
    }

    def inputs(self):
        return {
            "H2": _MOLAR, "CO2": _MOLAR, "temperature": _K, "pmf": _V,
            # Active Fe/Ni/S mineral catalyst (0 = no mineral — a control; a
            # store, not config, so an explicit 0.0 is honored rather than
            # swallowed by the is_empty(Float, 0.0) config-fill default).
            "catalyst_activity": _DIMLESS,
            "feasible_formate": _DIMLESS, "feasible_acetate": _DIMLESS,
            "feasible_pyruvate": _DIMLESS,
            "formate": _MOLAR, "acetate": _MOLAR, "pyruvate": _MOLAR,
        }

    def outputs(self):
        return {
            "formate": _MOLAR, "acetate": _MOLAR, "pyruvate": _MOLAR,
            "net_carbon_flux": {"_type": "overwrite[float]", "_units": "mole/second"},
        }

    def initial_state(self):
        return {"H2": 5.0e-3, "CO2": 2.0e-3, "temperature": 373.15, "pmf": 0.2,
                "catalyst_activity": 1.0,
                "feasible_formate": 1.0, "feasible_acetate": 1.0, "feasible_pyruvate": 1.0,
                "formate": 0.0, "acetate": 0.0, "pyruvate": 0.0}

    def update(self, state, interval):
        h2 = max(float(state.get("H2", 0.0)), 0.0)
        co2 = max(float(state.get("CO2", 0.0)), 0.0)
        temp_k = float(state.get("temperature", 373.15))
        pmf = max(float(state.get("pmf", 0.0)), 0.0)
        cat = max(float(state.get("catalyst_activity", 0.0)), 0.0)

        # Shared gating factors.
        km_h2, km_co2 = self.config["km_h2"], self.config["km_co2"]
        avail = (h2 / (h2 + km_h2)) * (co2 / (co2 + km_co2))
        drive = pmf / (pmf + self.config["pmf_half"])          # Michaelis in pmf
        t_opt, t_w = self.config["t_opt"], max(self.config["t_width"], 1.0)
        t_window = math.exp(-((temp_k - t_opt) ** 2) / (2.0 * t_w ** 2))
        vol = max(self.config["reactor_volume_scale"], 1e-12)

        deltas = {}
        carbon_rate = 0.0
        for name in ("formate", "acetate", "pyruvate"):
            feasible = max(0.0, min(1.0, float(state.get(f"feasible_{name}", 0.0))))
            product = max(float(state.get(name, 0.0)), 0.0)
            headroom = max(0.0, 1.0 - product / _YIELD_MAX[name])
            rate = (_K_RATE[name] * cat * feasible * drive * avail
                    * t_window * headroom)            # M/s
            deltas[name] = rate * interval
            carbon_rate += _CARBON[name] * rate * vol  # mol/s (carbon atoms)
        deltas["net_carbon_flux"] = carbon_rate
        return deltas
