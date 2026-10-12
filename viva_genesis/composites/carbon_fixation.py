"""Campaign I composite — geology to reduced carbon (og-01).

Couples three real-tool modules across the Fe(Ni)S barrier / pH gradient:

- ``gradient`` — Module C: real FiPy Nernst-Planck proton electrodiffusion
  (``PhGradientNernstPlanckProcess``) → proton-motive force, current density,
  electric potential. The ``gradient_efficiency`` param is the favorable
  (=1.0) vs Tutolo-2026 in-situ-collapse (<<1) ARM knob.
- ``thermo`` — Module D (thermo): real eQuilibrator ΔG' feasibility gate
  (``EquilibratorThermoStep``) for formate/acetate/pyruvate synthesis.
- ``fixation`` — Module D (kinetics): lab-calibrated mineral-catalyzed CO2
  reduction (``CarbonFixationProcess``), gated by thermo feasibility × pmf drive
  × H2/CO2 availability × catalyst, hitting the Preiner-2020 yield ceilings.

One parameterized generator drives every study condition:
  - favorable baseline   : defaults (gradient_efficiency=1.0)
  - Tutolo-2026 arm       : gradient_efficiency≈0.1 (usable gradient collapses)
  - controls              : catalyst_active=0 / h2≈0 / gradient_efficiency≈0
Requires ``equilibrator_api`` + ``fipy`` installed.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

_EMIT_PATHS = [
    "products/formate", "products/acetate", "products/pyruvate",
    "flux/net_carbon_flux",
    "electro/pmf", "electro/pmf_open", "electro/current_density",
    "electro/electric_potential", "electro/delta_pH", "electro/flux_divergence_residual",
    "electro/charge_state", "electro/proton_reservoir",
    "electro/proton_draw", "electro/proton_supply",
    "gibbs/dg_formate", "gibbs/feasible_formate",
    "global_time",
]


@composite_generator(
    name="hydrothermal_carbon_fixation",
    description=(
        "A reusable H2/pH-driven carbon-fixation module. Module C = genuine FiPy "
        "Nernst-Planck pH-gradient electrochemistry (pmf, current density). "
        "Module D = genuine eQuilibrator ΔG' feasibility gate + lab-calibrated "
        "(Preiner/Hudson) mineral-catalyzed CO2 reduction to formate/acetate/"
        "pyruvate. gradient_efficiency=1.0 is the favorable arm; ~0.1 is the "
        "Tutolo-2026 in-situ collapse. catalyst_active/h2=0 give the controls. "
        "Requires equilibrator_api + fipy."
    ),
    parameters={
        "gradient_efficiency": {"type": "float", "default": 1.0,
                                "description": "Usable fraction of the geochemical ΔpH at in-situ T/P "
                                               "(1.0 favorable; ~0.1 Tutolo-2026 collapse; 0 = no-gradient control)"},
        "catalyst_active": {"type": "float", "default": 1.0,
                            "description": "Active Fe/Ni/S mineral catalyst (0 = no-catalyst control)"},
        "h2": {"type": "float", "default": 5.0e-3,
               "description": "Dissolved H2 feed (M); ~0 = no-H2 control"},
        "co2": {"type": "float", "default": 2.0e-3, "description": "Dissolved CO2 feed (M)"},
        "ph_vent": {"type": "float", "default": 9.5, "description": "Alkaline vent-side pH (from og-00)"},
        "ph_ocean": {"type": "float", "default": 6.0, "description": "Acidic early-ocean-side pH"},
    },
    default_n_steps=120,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def hydrothermal_carbon_fixation(core=None, *, gradient_efficiency=1.0, catalyst_active=1.0,
                                    h2=5.0e-3, co2=2.0e-3, ph_vent=9.5, ph_ocean=6.0):
    return {
        "gradient": {
            "_type": "process",
            "address": "local:PhGradientNernstPlanckProcess",
            "config": {"gradient_efficiency": gradient_efficiency},
            "interval": 1.0,
            "inputs": {"pH_vent": ["env", "pH"], "pH_ocean": ["env", "pH_ocean"],
                       "temperature": ["env", "temperature"]},
            # The gradient's pmf is the OPEN-CIRCUIT (unloaded) drive; the proton
            # budget turns it into the loaded pmf that fixation actually sees.
            "outputs": {"delta_pH": ["electro", "delta_pH"], "pmf": ["electro", "pmf_open"],
                        "electric_potential": ["electro", "electric_potential"],
                        "current_density": ["electro", "current_density"],
                        "flux_divergence_residual": ["electro", "flux_divergence_residual"]},
        },
        "budget": {
            # Conserved proton economy + chemiosmotic back-pressure: the gradient
            # SUPPLIES protons, fixation SPENDS them, the loaded pmf sags under load.
            "_type": "process",
            "address": "local:ProtonBudgetProcess",
            "config": {},
            "interval": 1.0,
            "inputs": {"pmf_open": ["electro", "pmf_open"],
                       "carbon_flux": ["flux", "net_carbon_flux"]},
            "outputs": {"pmf": ["electro", "pmf"],
                        "charge_state": ["electro", "charge_state"],
                        "proton_reservoir": ["electro", "proton_reservoir"],
                        "proton_draw": ["electro", "proton_draw"],
                        "proton_supply": ["electro", "proton_supply"]},
        },
        "thermo": {
            "_type": "step",
            "address": "local:EquilibratorThermoStep",
            "config": {},
            "inputs": {"pH": ["env", "pH"], "ionic_strength": ["env", "ionic_strength"],
                       "temperature": ["env", "temperature"], "H2": ["env", "H2"],
                       "CO2": ["env", "CO2"], "formate": ["products", "formate"],
                       "acetate": ["products", "acetate"], "pyruvate": ["products", "pyruvate"]},
            "outputs": {"dg_formate": ["gibbs", "dg_formate"], "dg_acetate": ["gibbs", "dg_acetate"],
                        "dg_pyruvate": ["gibbs", "dg_pyruvate"],
                        "feasible_formate": ["gibbs", "feasible_formate"],
                        "feasible_acetate": ["gibbs", "feasible_acetate"],
                        "feasible_pyruvate": ["gibbs", "feasible_pyruvate"],
                        "free_energy_logged": ["gibbs", "free_energy_logged"]},
        },
        "fixation": {
            "_type": "process",
            "address": "local:CarbonFixationProcess",
            "config": {},
            "interval": 1.0,
            "inputs": {"H2": ["env", "H2"], "CO2": ["env", "CO2"],
                       "temperature": ["env", "temperature"], "pmf": ["electro", "pmf"],
                       "catalyst_activity": ["catalyst", "active"],
                       "feasible_formate": ["gibbs", "feasible_formate"],
                       "feasible_acetate": ["gibbs", "feasible_acetate"],
                       "feasible_pyruvate": ["gibbs", "feasible_pyruvate"],
                       "formate": ["products", "formate"], "acetate": ["products", "acetate"],
                       "pyruvate": ["products", "pyruvate"]},
            "outputs": {"formate": ["products", "formate"], "acetate": ["products", "acetate"],
                        "pyruvate": ["products", "pyruvate"],
                        "net_carbon_flux": ["flux", "net_carbon_flux"]},
        },
        "env": {"pH": ph_vent, "pH_ocean": ph_ocean, "ionic_strength": 0.25,
                "temperature": 373.15, "H2": h2, "CO2": co2},
        "electro": {"delta_pH": 0.0, "pmf": 0.0, "pmf_open": 0.0, "electric_potential": 0.0,
                    "current_density": 0.0, "flux_divergence_residual": 0.0,
                    "charge_state": 1.0, "proton_reservoir": 0.0,
                    "proton_draw": 0.0, "proton_supply": 0.0},
        "gibbs": {"dg_formate": 0.0, "dg_acetate": 0.0, "dg_pyruvate": 0.0,
                   "feasible_formate": 0.0, "feasible_acetate": 0.0, "feasible_pyruvate": 0.0,
                   "free_energy_logged": False},
        "products": {"formate": 0.0, "acetate": 0.0, "pyruvate": 0.0},
        "flux": {"net_carbon_flux": 0.0},
        "catalyst": {"active": catalyst_active},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {"formate": "float", "acetate": "float", "pyruvate": "float",
                                "net_carbon_flux": "float", "pmf": "float", "pmf_open": "float",
                                "charge_state": "float", "proton_reservoir": "float",
                                "proton_draw": "float", "proton_supply": "float",
                                "current_density": "float", "electric_potential": "float",
                                "delta_pH": "float", "dg_formate": "float",
                                "feasible_formate": "float", "flux_divergence_residual": "float",
                                "global_time": "float"}},
            "inputs": {"formate": ["products", "formate"], "acetate": ["products", "acetate"],
                       "pyruvate": ["products", "pyruvate"],
                       "net_carbon_flux": ["flux", "net_carbon_flux"],
                       "pmf": ["electro", "pmf"], "pmf_open": ["electro", "pmf_open"],
                       "charge_state": ["electro", "charge_state"],
                       "proton_reservoir": ["electro", "proton_reservoir"],
                       "proton_draw": ["electro", "proton_draw"],
                       "proton_supply": ["electro", "proton_supply"],
                       "current_density": ["electro", "current_density"],
                       "electric_potential": ["electro", "electric_potential"],
                       "delta_pH": ["electro", "delta_pH"],
                       "dg_formate": ["gibbs", "dg_formate"],
                       "feasible_formate": ["gibbs", "feasible_formate"],
                       "flux_divergence_residual": ["electro", "flux_divergence_residual"],
                       "global_time": ["global_time"]},
        },
    }
