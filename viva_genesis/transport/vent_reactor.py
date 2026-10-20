"""Module B — hydrothermal vent–ocean reactor (REDUCED REPRODUCTION).

**Not a wrap of FiPy / a reactive-transport solver.** A clean-room, reduced
well-mixed reactor standing in for Campaign 0 (see ``workspace/notes/modules.md``,
Module B). It reads the serpentinization source (H2, alkalinity, heat) and
relaxes the interface temperature, pH and porosity toward Lost City–like targets,
so a short run settles into the field window (~45–90 C, pH ~9–10.8) with a
sustained reducing supply. The eventual Campaign-0 model replaces this with a
real FiPy advection–diffusion–reaction coupling.
"""
from __future__ import annotations

import math

from process_bigraph import Process

from bigraph_schema.contract import ProcessContract, narrow_condition

_K = {"_type": "float", "_units": "kelvin"}
_W = {"_type": "float", "_units": "watt"}
_MOLAR = {"_type": "float", "_units": "molar"}
_DIMLESS = {"_type": "float", "_units": "dimensionless"}


class VentReactorReproductionProcess(Process):
    """Reduced vent–ocean mixing reactor.

    Read–modify–write: reads the current ``temperature``/``pH``/``porosity`` plus
    the serpentinization drivers, and emits first-order relaxation **deltas**
    toward field-constrained targets (bare ``float`` ports, so the deltas compose
    additively and a sibling process could also contribute).
    """

    contract = ProcessContract(**{
        "summary": "Reduced vent-ocean mixing reactor (clean-room stand-in, NOT FiPy): relaxes T / pH / porosity toward Lost City-like field targets.",
        "description": (
            "Deliberately reduced well-mixed reactor reproduction for Campaign 0 - the real model is "
            "FipyReactiveTransportProcess. Read-modify-write: reads the current temperature / pH / "
            "porosity and the serpentinization drivers and emits first-order relaxation deltas toward "
            "field-constrained targets (additive float ports), so a short run settles into the Lost "
            "City window (~45-90 C, pH ~9-10.8) with a sustained reducing supply. Temperature is "
            "nudged by accumulated serpentinization heat; pH tracks an alkalinity-driven target; "
            "porosity evolves toward a precipitation-set value (clamped to [0, 1])."
        ),
        "inputs": {
            "temperature": "interface temperature (K)", "pH": "interface pH (dimensionless)",
            "porosity": "pore fraction (dimensionless)", "H2": "H2 source (molar)",
            "alkalinity": "alkalinity source (molar)", "heat": "heat source (W)",
        },
        "outputs": {
            "temperature": "temperature relaxation delta (K)", "pH": "pH relaxation delta (dimensionless)",
            "porosity": "porosity relaxation delta (dimensionless)",
        },
        "assumptions": [
            "Reduced reproduction, not a reactive-transport solver: well-mixed first-order relaxation to field targets.",
            "Targets field-constrained to the Lost City window; porosity clamped to [0, 1].",
        ],
        "math": [
            "dT = k_temperature * (t_target + heat_gain*tanh(heat/50)*20 - T) * dt",
            "dpH = k_ph * (ph_base + (ph_max - ph_base) * alk/(alk + alk_scale) - pH) * dt",
            "d(porosity) = k_porosity * (porosity_target - porosity) * dt,  clamped to [0, 1]",
        ],
        "symbols": {
            "t_target": "mixing temperature target (K)", "k_temperature": "temperature relaxation rate",
            "heat_gain": "heat-to-temperature coupling (K per W, saturating)",
            "ph_base": "low-alkalinity pH target", "ph_max": "high-alkalinity pH target",
            "k_ph": "pH relaxation rate", "alk_scale": "alkalinity half-saturation (molar)",
            "porosity_target": "precipitation-set porosity", "k_porosity": "porosity relaxation rate",
        },
        "references": ["kelley2001offaxis", "ludwig2006formation"],
    })
    # Validity preconditions, checked against the auto-filled face (interface())
    # at resolve time. The face carries the units: temperature K, H2/alkalinity
    # molar, heat W, pH/porosity dimensionless.
    contract = narrow_condition(contract, "pre", "inputs.temperature > 0",
                                name="positive absolute temperature")
    contract = narrow_condition(contract, "pre", "inputs.porosity >= 0",
                                name="non-negative porosity")
    contract = narrow_condition(contract, "pre", "inputs.H2 >= 0",
                                name="non-negative H2 concentration")
    contract = narrow_condition(contract, "pre", "inputs.alkalinity >= 0",
                                name="non-negative alkalinity")

    config_schema = {
        "t_target": {"_type": "float", "_default": 340.0},    # K (~67 C), Lost City mid-window
        "k_temperature": {"_type": "float", "_default": 0.05},
        "heat_gain": {"_type": "float", "_default": 0.2},     # K per W accumulated, capped
        "ph_base": {"_type": "float", "_default": 9.1},
        "ph_max": {"_type": "float", "_default": 10.6},
        "k_ph": {"_type": "float", "_default": 0.09},
        "alk_scale": {"_type": "float", "_default": 0.02},    # molar scale for pH response
        "porosity_target": {"_type": "float", "_default": 0.25},
        "k_porosity": {"_type": "float", "_default": 0.02},
    }

    def inputs(self):
        return {
            "temperature": _K,
            "pH": _DIMLESS,
            "porosity": _DIMLESS,
            "H2": _MOLAR,
            "alkalinity": _MOLAR,
            "heat": _W,
        }

    def outputs(self):
        return {"temperature": _K, "pH": _DIMLESS, "porosity": _DIMLESS}

    def initial_state(self):
        return {"temperature": 300.0, "pH": 7.2, "porosity": 0.35,
                "H2": 0.0, "alkalinity": 0.0, "heat": 0.0}

    def update(self, state, interval):
        temperature = float(state["temperature"])
        ph = float(state["pH"])
        porosity = float(state["porosity"])
        heat = float(state["heat"])
        alkalinity = float(state["alkalinity"])

        # Temperature relaxes toward the mixing target, nudged up by accumulated
        # serpentinization heat (saturating so it stays in the field window).
        heat_bump = self.config["heat_gain"] * math.tanh(heat / 50.0) * 20.0
        t_target = self.config["t_target"] + heat_bump
        d_temperature = self.config["k_temperature"] * (t_target - temperature) * interval

        # pH relaxes toward an alkalinity-driven target between base and max.
        alk_term = alkalinity / (alkalinity + self.config["alk_scale"])
        ph_target = self.config["ph_base"] + (self.config["ph_max"] - self.config["ph_base"]) * alk_term
        d_ph = self.config["k_ph"] * (ph_target - ph) * interval

        # Porosity evolves toward a precipitation-set value, clamped to [0, 1].
        d_porosity = self.config["k_porosity"] * (self.config["porosity_target"] - porosity) * interval
        if porosity + d_porosity < 0.0:
            d_porosity = -porosity
        elif porosity + d_porosity > 1.0:
            d_porosity = 1.0 - porosity

        return {"temperature": d_temperature, "pH": d_ph, "porosity": d_porosity}
