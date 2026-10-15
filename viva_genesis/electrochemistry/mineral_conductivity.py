"""Mineral conductivity — ``gradient_efficiency`` derived from circuit physics (Phase 2).

og-01 carried the usable fraction of the geochemical pH gradient as a scalar
knob (``gradient_efficiency``: 1.0 favorable, ~0.1 the Tutolo-2026 in-situ
collapse). The Model Upgrade plan asks for that number to be *derived*: the
vent wall is an electrical circuit, and the fraction of the open-circuit emf
that appears across the catalytic interfaces — rather than being dropped
inside the mineral or shunted through the pores — is a voltage-divider
statement about the wall's conductivity, thickness and porosity.

:class:`MineralConductivityProcess` computes, every tick,

* ``R_e = L / σ_e`` — the areal electronic resistance of the mineral layer
  (thickness ``L``, electronic conductivity ``σ_e``; sulfide-rich walls are
  conductors, brucite / silicate walls are insulators);
* ``R_ion = L / (σ_f(I, T) φ^1.5)`` — the ionic return path through the pore
  fluid (ionic strength ``I``, Bruggeman tortuosity on the porosity ``φ``);
* ``R_ct = (RT/F)(1/j0_a + 1/j0_c)`` — the small-signal charge-transfer
  resistance of the two electrodes (the exchange currents of the
  Butler-Volmer class, scaled by catalyst activity, Ni fraction and T);
* a parallel shunt ``G_shunt`` (proton leak that dissipates the gradient
  without electron transfer; hypothetical, default 0),

and publishes ``gradient_efficiency = R_ct / (R_ct + R_e + R_ion) · (1 −
shunt_fraction)``. The ``empirical`` carbon-fixation class in the Phase-2
composite runs the og-01 Nernst-Planck gradient at *this* efficiency instead
of the knob; the Butler-Volmer class carries the same resistances inside its
circuit solve, so for it the published value is a small-signal prediction of
the fraction it actually delivers (reported beside the realised value).
"""

from __future__ import annotations

import math

from process_bigraph import Process

from .butler_volmer import F, R, T_REF, ButlerVolmerCarbonFixationProcess, ni_activity_gain

_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_SM = {"_type": "float", "_units": "siemens/meter"}
_M = {"_type": "float", "_units": "meter"}
_K = {"_type": "float", "_units": "kelvin"}
_MOLAR = {"_type": "float", "_units": "molar"}
_OVW = {"_type": "overwrite[float]", "_units": "dimensionless"}
_OVW_R = {"_type": "overwrite[float]", "_units": "ohm*meter**2"}

_BV = ButlerVolmerCarbonFixationProcess.config_schema


def circuit_efficiency(*, conductivity, layer_thickness, porosity=0.35, ionic_strength=0.25,
                       temperature=T_REF, catalyst_activity=1.0, ni_fraction=0.75,
                       j0_h2_ref=_BV["j0_h2_ref"]["_default"], j0_co2_ref=_BV["j0_co2_ref"]["_default"],
                       activation_energy=_BV["activation_energy"]["_default"], ni_gain=_BV["ni_gain"]["_default"],
                       ni_reference=_BV["ni_reference"]["_default"],
                       fluid_conductivity_per_molar=_BV["fluid_conductivity_per_molar"]["_default"],
                       bruggeman_exponent=_BV["bruggeman_exponent"]["_default"],
                       shunt_conductance=0.0) -> dict:
    """The voltage-divider efficiency of the vent-wall circuit and its parts (pure function)."""
    T = max(float(temperature), 250.0)
    r_e = float(layer_thickness) / max(float(conductivity), 1e-30)
    sigma_ion = (float(fluid_conductivity_per_molar) * max(float(ionic_strength), 1e-6)
                 * (1.0 + 0.02 * (T - 298.15)) * max(float(porosity), 1e-6) ** float(bruggeman_exponent))
    r_ion = float(layer_thickness) / max(sigma_ion, 1e-30)
    arrh = math.exp(-float(activation_energy) / R * (1.0 / T - 1.0 / T_REF))
    gain = ni_activity_gain(ni_fraction, ni_gain) / ni_activity_gain(ni_reference, ni_gain)
    cat = max(float(catalyst_activity), 1e-12)
    j0_a = float(j0_h2_ref) * cat * gain * arrh
    j0_c = float(j0_co2_ref) * cat * gain * arrh
    r_ct = (R * T / F) * (1.0 / max(j0_a, 1e-30) + 1.0 / max(j0_c, 1e-30))
    r_series = r_ct + r_e + r_ion
    g_shunt = max(float(shunt_conductance), 0.0)
    shunt_fraction = g_shunt / (g_shunt + 1.0 / r_series) if g_shunt > 0.0 else 0.0
    eff = (r_ct / r_series) * (1.0 - shunt_fraction)
    return {"gradient_efficiency": eff, "areal_resistance": r_e + r_ion,
            "charge_transfer_resistance": r_ct, "electronic_resistance": r_e,
            "ionic_resistance": r_ion, "shunt_fraction": shunt_fraction}


class MineralConductivityProcess(Process):
    """Derives the usable fraction of the geochemical gradient from the wall's circuit:
    charge-transfer resistance of the two electrodes vs the ohmic electronic +
    ionic path, with an optional proton-leak shunt. Overwrite sensors."""

    contract = {
        "summary": "gradient_efficiency from circuit physics: R_ct / (R_ct + L/sigma_e + L/(sigma_f phi^1.5)) x (1 - shunt).",
        "description": (
            "Each tick computes the areal electronic resistance of the mineral layer "
            "(thickness / conductivity), the ionic return-path resistance through the "
            "pore fluid (Bruggeman tortuosity on porosity, conductivity from ionic strength "
            "and temperature) and the small-signal charge-transfer resistance of the two "
            "electrodes (from the Butler-Volmer exchange currents scaled by catalyst "
            "activity, Ni fraction and temperature), and publishes the voltage-divider "
            "fraction of the open-circuit emf that falls across the catalytic interfaces. "
            "This replaces og-01's gradient_efficiency knob: an insulating or shunted wall "
            "collapses the usable gradient (the Tutolo-2026 arm) as a consequence, not a "
            "parameter."
        ),
        "inputs": {
            "conductivity": "electronic conductivity of the mineral layer (siemens/meter)",
            "layer_thickness": "mineral layer thickness (meter)", "porosity": "pore fraction",
            "ionic_strength": "pore-fluid ionic strength (molar)", "temperature": "temperature (K)",
            "catalyst_activity": "active-catalyst fraction", "ni_fraction": "Ni mole fraction of the Fe/Ni phase",
        },
        "outputs": {
            "gradient_efficiency": "usable fraction of the emf across the interfaces (dimensionless)",
            "areal_resistance": "ohmic electronic + ionic areal resistance (ohm*meter**2)",
            "charge_transfer_resistance": "small-signal electrode resistance (ohm*meter**2)",
            "shunt_fraction": "fraction of the current lost through the proton-leak shunt",
        },
        "assumptions": [
            "Small-signal (linearised Butler-Volmer) charge-transfer resistance.",
            "Bruggeman tortuosity for the ionic path; fluid conductivity linear in ionic strength with 2 %/K.",
        ],
        "math": ["eff = R_ct / (R_ct + R_e + R_ion) * (1 - G_shunt / (G_shunt + 1/(R_ct + R_e + R_ion)))",
                 "R_e = L / sigma_e;  R_ion = L / (sigma_f phi^1.5);  R_ct = (RT/F)(1/j0_a + 1/j0_c)"],
        "references": ["commchem2026currentproducing", "altair2025electrochemical", "tutolo2026rethinking"],
    }

    config_schema = {
        "j0_h2_ref": dict(_BV["j0_h2_ref"]),
        "j0_co2_ref": dict(_BV["j0_co2_ref"]),
        "activation_energy": dict(_BV["activation_energy"]),
        "ni_gain": dict(_BV["ni_gain"]),
        "ni_reference": dict(_BV["ni_reference"]),
        "fluid_conductivity_per_molar": dict(_BV["fluid_conductivity_per_molar"]),
        "bruggeman_exponent": dict(_BV["bruggeman_exponent"]),
        "shunt_conductance": {"_type": "float", "_default": 0.0, "_units": "siemens/meter**2",
                              "_provenance": "hypothetical"},
    }

    def inputs(self):
        return {"conductivity": _SM, "layer_thickness": _M, "porosity": _DIMLESS, "ionic_strength": _MOLAR,
                "temperature": _K, "catalyst_activity": _DIMLESS, "ni_fraction": _DIMLESS}

    def outputs(self):
        return {"gradient_efficiency": _OVW, "areal_resistance": _OVW_R,
                "charge_transfer_resistance": _OVW_R, "shunt_fraction": _OVW}

    def initial_state(self):
        return {"conductivity": 1.0e-3, "layer_thickness": 1.0e-3, "porosity": 0.35, "ionic_strength": 0.25,
                "temperature": T_REF, "catalyst_activity": 1.0, "ni_fraction": 0.75}

    def update(self, state, interval):
        c = self.config
        out = circuit_efficiency(
            conductivity=state.get("conductivity", 1e-3), layer_thickness=max(float(state.get("layer_thickness", 1e-3)), 1e-9),
            porosity=state.get("porosity", 0.35), ionic_strength=state.get("ionic_strength", 0.25),
            temperature=state.get("temperature", T_REF), catalyst_activity=state.get("catalyst_activity", 1.0),
            ni_fraction=state.get("ni_fraction", 0.75),
            j0_h2_ref=c["j0_h2_ref"], j0_co2_ref=c["j0_co2_ref"], activation_energy=c["activation_energy"],
            ni_gain=c["ni_gain"], ni_reference=c["ni_reference"],
            fluid_conductivity_per_molar=c["fluid_conductivity_per_molar"],
            bruggeman_exponent=c["bruggeman_exponent"], shunt_conductance=c["shunt_conductance"])
        return {k: out[k] for k in ("gradient_efficiency", "areal_resistance",
                                    "charge_transfer_resistance", "shunt_fraction")}


__all__ = ["MineralConductivityProcess", "circuit_efficiency"]
