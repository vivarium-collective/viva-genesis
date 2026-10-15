"""Module A — serpentinization geochemical energy supply (REDUCED REPRODUCTION).

**This is NOT a wrap of PHREEQC / Reaktoro.** It is a clean-room, deliberately
reduced parameterized stand-in for Campaign 0 of the origins-of-life vent
campaign (see ``workspace/notes/modules.md``, Module A). It produces H2,
alkalinity and heat *source rates* as smooth functions of temperature and water
flux — right order of magnitude and sign — so the vent-reactor composite runs
end to end and settles into a Lost City–like window. The eventual Campaign-0
model replaces this reproduction with a real Reaktoro/PHREEQC bridge.
"""
from __future__ import annotations

import math

from process_bigraph import Process

_K = {"_type": "float", "_units": "kelvin"}
_PA = {"_type": "float", "_units": "pascal"}
_MPS = {"_type": "float", "_units": "meter/second"}
_MOLS = {"_type": "float", "_units": "mole/second"}
_W = {"_type": "float", "_units": "watt"}
_MOLAR = {"_type": "float", "_units": "molar"}


class SerpentinizationReproductionProcess(Process):
    """Reduced serpentinization source: ``(T, flow) -> H2 / alkalinity / heat``.

    REDUCED REPRODUCTION, not PHREEQC/Reaktoro. Each tick it (a) adds the
    integrated H2 + alkalinity + heat it produced over the interval to the vent
    stores (bare ``float`` deltas, so they accumulate and compose), and (b)
    publishes the instantaneous source *rates* as ``overwrite[float]`` sensor
    readings for observability. Production peaks in a temperature window and
    scales with water flux (serpentinization is water–rock-reaction limited).
    """

    contract = {
        "summary": "Reduced serpentinization source (clean-room stand-in, NOT PHREEQC): (T, flow) -> H2, alkalinity, heat source rates.",
        "description": (
            "Deliberately reduced parameterized reproduction of the serpentinizing source for "
            "Campaign 0 - the real model is PhreeqcSerpentinizationProcess. Each tick it adds the "
            "integrated H2 + alkalinity + heat produced over the interval to the vent stores "
            "(additive float deltas) and publishes the instantaneous source rates as overwrite "
            "sensors. Production peaks in a Gaussian temperature window and saturates with water "
            "flux (serpentinization is water-rock-reaction limited) - right order of magnitude and "
            "sign, so the vent composite runs end to end and settles into a Lost City-like window."
        ),
        "inputs": {
            "temperature": "vent fluid temperature (K)",
            "flow_velocity": "boundary water flow speed (meter/second)",
        },
        "outputs": {
            "H2": "integrated H2 source delta (molar)", "alkalinity": "integrated alkalinity source delta (molar)",
            "heat": "integrated serpentinization heat delta (W)",
            "H2_flux": "instantaneous H2 source rate (mol/s)",
            "alkalinity_flux": "instantaneous alkalinity source rate (mol/s)",
            "heat_flux": "instantaneous heat source rate (W)",
        },
        "assumptions": [
            "Reduced reproduction, not a geochemical solver: a smooth parameterized source, right magnitude/sign only.",
            "activity = Gaussian temperature window * saturating flow dependence; rate = rate_max * activity.",
        ],
        "math": [
            "activity(T, flow) = exp(-(T - t_opt)^2 / (2 t_width^2)) * flow / (flow + flow_ref)",
            "rate_i = rate_max_i * activity;   pool_i += rate_i * dt",
        ],
        "symbols": {
            "t_opt": "optimal temperature (K)", "t_width": "temperature-window width (K)",
            "flow_ref": "flow half-saturation (m/s)",
            "h2_rate_max": "peak H2 source rate (mol/s)", "alk_rate_max": "peak alkalinity source rate (mol/s)",
            "heat_rate_max": "peak heat source rate (W)",
        },
        "references": ["kelley2005serpentinite", "schwander2023serpentinization"],
    }

    config_schema = {
        # Peak source rates at the reference flow, inside the optimal T window.
        "h2_rate_max": {"_type": "float", "_default": 1.0e-3},    # mol/s
        "alk_rate_max": {"_type": "float", "_default": 8.0e-4},   # mol/s
        "heat_rate_max": {"_type": "float", "_default": 25.0},    # W
        "t_opt": {"_type": "float", "_default": 340.0},           # K (~67 C)
        "t_width": {"_type": "float", "_default": 70.0},          # K
        "flow_ref": {"_type": "float", "_default": 1.0e-3},       # m/s
    }

    def inputs(self):
        return {"temperature": _K, "flow_velocity": _MPS}

    def outputs(self):
        return {
            # Accumulating pools (bare float deltas — compose additively).
            "H2": _MOLAR,
            "alkalinity": _MOLAR,
            "heat": _W,
            # Instantaneous source rates (current-reading sensors).
            "H2_flux": "overwrite[float]",
            "alkalinity_flux": "overwrite[float]",
            "heat_flux": "overwrite[float]",
        }

    def initial_state(self):
        return {"temperature": 300.0, "flow_velocity": 1.0e-3}

    def _activity(self, temperature: float, flow_velocity: float) -> float:
        """Dimensionless 0..1 serpentinization activity: a Gaussian temperature
        window times a saturating flow dependence."""
        t_opt = self.config["t_opt"]
        t_width = max(self.config["t_width"], 1.0)
        temp_term = math.exp(-((temperature - t_opt) ** 2) / (2.0 * t_width ** 2))
        flow_ref = max(self.config["flow_ref"], 1e-12)
        flow_term = flow_velocity / (flow_velocity + flow_ref)
        return max(0.0, temp_term * flow_term)

    def update(self, state, interval):
        act = self._activity(float(state["temperature"]), float(state["flow_velocity"]))
        h2_rate = self.config["h2_rate_max"] * act
        alk_rate = self.config["alk_rate_max"] * act
        heat_rate = self.config["heat_rate_max"] * act
        return {
            # Integrated production over the interval (accumulates in the vent).
            "H2": h2_rate * interval,
            "alkalinity": alk_rate * interval,
            "heat": heat_rate * interval,
            # Current rates for observability / the behavior-test flux check.
            "H2_flux": h2_rate,
            "alkalinity_flux": alk_rate,
            "heat_flux": heat_rate,
        }
