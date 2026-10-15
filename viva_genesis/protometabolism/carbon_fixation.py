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

    contract = {
        "summary": "Lab-calibrated mineral-catalyzed CO2 reduction, gated by thermodynamic feasibility, proton drive, availability and catalyst.",
        "description": (
            "Emits product concentration increments (additive float deltas - pools "
            "accumulate) for H2-driven CO2 reduction to formate / acetate / pyruvate on "
            "Fe/Ni/S mineral catalysts, with the rate gated by the eQuilibrator "
            "feasibility, the proton-motive drive, substrate availability (H2, CO2), a "
            "temperature window and headroom to the Preiner-calibrated yield caps. Net "
            "organic-carbon flux is an overwrite sensor."
        ),
        "inputs": {
            "H2": "dissolved H2 (molar)", "CO2": "dissolved CO2 (molar)", "temperature": "temperature (K)",
            "pmf": "proton-motive force drive (volt)", "catalyst_activity": "active Fe/Ni/S catalyst in [0,1] (dimensionless; 0 = no-mineral control)",
            "feasible_formate": "feasibility gate (dimensionless)", "feasible_acetate": "feasibility gate (dimensionless)",
            "feasible_pyruvate": "feasibility gate (dimensionless)",
        },
        "outputs": {
            "formate": "formate production delta (molar)", "acetate": "acetate production delta (molar)",
            "pyruvate": "pyruvate production delta (molar)",
            "net_carbon_flux": "net organic-carbon fixation rate (mole/second)",
        },
        "assumptions": [
            "Yields capped at Preiner/Hudson lab values (formate 0.2 M, acetate 1e-4, pyruvate 1e-5).",
            "rate = k * catalyst * feasible * drive(pmf) * avail(H2,CO2) * T-window * headroom.",
        ],
        "math": [
            "rate = k_cat * catalyst * feasible * drive(pmf) * avail(H2, CO2) * window(T) * headroom",
            "drive(pmf) = pmf / (pmf + pmf_half);   avail(x) = x / (x + km_x)",
            "window(T) = exp(-((T - t_opt) / t_width)^2);   headroom = 1 - product / product_cap",
        ],
        "symbols": {
            "pmf_half": "half-max proton-motive drive (volt)",
            "km_h2": "H2 half-saturation constant (molar)", "km_co2": "CO2 half-saturation constant (molar)",
            "t_opt": "optimal temperature (K)", "t_width": "temperature-window width (K)",
            "product_cap": "Preiner/Hudson lab yield ceiling per product",
        },
        "references": ["preiner2020hydrogen", "hudson2020co2", "varma2018native"],
    }

    config_schema = {
        "pmf_half": {"_type": "float", "_default": 0.08, "_units": "volt"},           # V, half-max drive
        "km_h2": {"_type": "float", "_default": 1.0e-4, "_units": "molar"},            # M
        "km_co2": {"_type": "float", "_default": 1.0e-4, "_units": "molar"},          # M
        "t_opt": {"_type": "float", "_default": 373.15, "_units": "kelvin"},           # K (~100 C, Preiner)
        "t_width": {"_type": "float", "_default": 60.0, "_units": "kelvin"},           # K
        "reactor_volume_scale": {"_type": "float", "_default": 1.0, "_units": "liter"},  # L, flux scaling
        # Open-flow washout. 0.0 = closed batch (products relax to the Preiner
        # ceiling; back-compat default for the yield studies). >0 makes the vent
        # the open-flow reactor it physically is: products are flushed at this
        # rate, so each pool reaches a CONDITION-DEPENDENT steady state
        # [product]_ss ~ production_rate / dilution_rate (capped by the ceiling)
        # and net_carbon_flux settles to a genuine SUSTAINED throughput rather
        # than collapsing to zero at saturation. This is what makes the
        # carbon-fixation phase map a real decision surface.
        "dilution_rate": {"_type": "float", "_default": 0.0, "_units": "1/second"},
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

    def gating_factors(self, state) -> dict:
        """The shared multiplicative gates of the rate law for ``state``.

        Returns ``{avail, drive, t_window, cat, vol, dilution}``: substrate
        availability (Michaelis in H2 and CO2), the proton-motive drive
        (Michaelis in pmf), the temperature window, the catalyst activity, the
        volume scale and the washout rate. Exposed so the Phase-2 ``empirical``
        adapter can attribute the limitation without re-deriving the rate law.
        """
        h2 = max(float(state.get("H2", 0.0)), 0.0)
        co2 = max(float(state.get("CO2", 0.0)), 0.0)
        temp_k = float(state.get("temperature", 373.15))
        pmf = max(float(state.get("pmf", 0.0)), 0.0)
        cat = max(float(state.get("catalyst_activity", 0.0)), 0.0)
        km_h2, km_co2 = self.config["km_h2"], self.config["km_co2"]
        avail = (h2 / (h2 + km_h2)) * (co2 / (co2 + km_co2))
        drive = pmf / (pmf + self.config["pmf_half"])          # Michaelis in pmf
        t_opt, t_w = self.config["t_opt"], max(self.config["t_width"], 1.0)
        t_window = math.exp(-((temp_k - t_opt) ** 2) / (2.0 * t_w ** 2))
        vol = max(self.config["reactor_volume_scale"], 1e-12)
        dilution = max(float(self.config.get("dilution_rate", 0.0)), 0.0)  # 1/s washout
        return {"avail": avail, "drive": drive, "t_window": t_window, "cat": cat,
                "vol": vol, "dilution": dilution}

    def update(self, state, interval):
        g = self.gating_factors(state)
        avail, drive, t_window, cat = g["avail"], g["drive"], g["t_window"], g["cat"]
        vol, dilution = g["vol"], g["dilution"]

        deltas = {}
        carbon_rate = 0.0
        for name in ("formate", "acetate", "pyruvate"):
            feasible = max(0.0, min(1.0, float(state.get(f"feasible_{name}", 0.0))))
            product = max(float(state.get(name, 0.0)), 0.0)
            headroom = max(0.0, 1.0 - product / _YIELD_MAX[name])
            rate = (_K_RATE[name] * cat * feasible * drive * avail
                    * t_window * headroom)            # M/s production
            # Open-flow washout, applied as exponential decay so it is stable at
            # ANY dilution (linear D·product·interval overshoots once D·interval>1,
            # and the dilution needed to pull a fast-producing pool below the
            # Preiner ceiling is large). At steady state production balances
            # washout, so the pool reaches a CONDITION-DEPENDENT value
            # ~ production/(1-e^{-D·dt}) instead of the ceiling, and net_carbon_flux
            # settles to a genuine sustained throughput. D=0 → no washout (batch).
            washout = product * (1.0 - math.exp(-dilution * interval))  # M removed, in (0, product]
            deltas[name] = rate * interval - washout
            carbon_rate += _CARBON[name] * rate * vol  # mol/s carbon FIXED (gross production)
        deltas["net_carbon_flux"] = carbon_rate
        return deltas
