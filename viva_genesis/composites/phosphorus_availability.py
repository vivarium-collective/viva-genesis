"""Phosphorus-availability composite — the phosphorus bottleneck (enrichment §6).

A single real-tool module: ``speciation`` = the genuine libRoadRunner/Tellurium
SBML P-speciation network (``PhosphorusSpeciationProcess``) run against a
dissolved-phosphate supply, a thermal-gradient pore enrichment (coupled from the
og-03 trap) and a pore temperature. The emergent observables — the standing
reactive-P pool, reactive-P production vs precipitation/adsorption loss, and the
precipitated fraction — test whether reactive phosphorus becomes *available*
before phosphate precipitates, and whether the pore co-concentrates P alongside
carbon.

One parameterized generator drives every study condition:

  - favorable pore : defaults (pore_enrichment 30, loss_rate 0.08) -> reactive P
                     is produced faster than it precipitates (net > 0)
  - open-pore / no-gradient control : ``pore_enrichment = 1`` -> precipitation
                     dominates, reactive P collapses (the ablation control)

The speciation network is a genuine libRoadRunner/Tellurium SBML ODE integration
(needs ``tellurium``).
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

_EMIT_PATHS = [
    "P/phosphate", "P/polyphosphate", "P/reactive_P", "P/mineral_P",
    "flux/reactive_P_production", "flux/phosphate_loss", "flux/net_reactive_P",
    "flux/precipitated_fraction", "flux/p_mass_residual",
    "global_time",
]


@composite_generator(
    name="phosphorus_availability",
    methods=["libRoadRunner/Tellurium SBML P-speciation ODE"],
    fidelity="real",
    description=(
        "A reusable phosphorus-availability module. A genuine libRoadRunner/Tellurium "
        "SBML ODE integration (needs tellurium) of a P-speciation network (phosphate "
        "<-> polyphosphate <-> reactive-P with a precipitation/adsorption mineral sink) "
        "driven by a dissolved-phosphate supply, the og-03 thermal-gradient pore "
        "enrichment, and pore temperature. Emergent: the standing reactive-P pool, "
        "reactive-P production vs precipitation loss (net availability), and the "
        "precipitated fraction — does reactive P become available before phosphate "
        "precipitates?"
    ),
    parameters={
        "phosphate_supply": {"type": "float", "default": 1.0e-4,
                             "description": "Dissolved orthophosphate supply / initial pool (M)"},
        "pore_enrichment": {"type": "float", "default": 30.0,
                            "description": "Thermal-gradient pore enrichment from the og-03 trap (>=1; 1 = open pore / no gradient control)"},
        "temperature": {"type": "float", "default": 333.15,
                        "description": "Mean pore temperature (K)"},
        "loss_rate": {"type": "float", "default": 0.08,
                      "description": "Precipitation / adsorption loss rate k_prec (1/s) — the mineral-sink bottleneck"},
    },
    visualizations=[
        {"name": "phosphorus-speciation", "address": "local:PhosphorusSpeciationViz",
         "config": {"title": "Phosphorus bottleneck — P-species trajectories"}},
        {"name": "phosphorus-mechanism", "address": "local:PhosphorusMechanismViz",
         "config": {"title": "Phosphorus bottleneck — reactive-P production vs loss"}},
    ],
    default_n_steps=120,
    preferred_time="24 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def phosphorus_availability(core=None, *, phosphate_supply=1.0e-4,
                            pore_enrichment=30.0, temperature=333.15, loss_rate=0.08):
    return {
        "speciation": {
            "_type": "process",
            "address": "local:PhosphorusSpeciationProcess",
            "config": {"k_prec": loss_rate},
            "interval": 1.0,
            "inputs": {"phosphate_supply": ["env", "phosphate_supply"],
                       "pore_enrichment": ["env", "pore_enrichment"],
                       "temperature": ["env", "temperature"]},
            "outputs": {"phosphate": ["P", "phosphate"], "polyphosphate": ["P", "polyphosphate"],
                        "reactive_P": ["P", "reactive_P"], "mineral_P": ["P", "mineral_P"],
                        "reactive_P_production": ["flux", "reactive_P_production"],
                        "phosphate_loss": ["flux", "phosphate_loss"],
                        "net_reactive_P": ["flux", "net_reactive_P"],
                        "precipitated_fraction": ["flux", "precipitated_fraction"],
                        "p_mass_residual": ["flux", "p_mass_residual"]},
        },
        "env": {"phosphate_supply": phosphate_supply, "pore_enrichment": pore_enrichment,
                "temperature": temperature},
        "P": {"phosphate": 0.0, "polyphosphate": 0.0, "reactive_P": 0.0, "mineral_P": 0.0},
        "flux": {"reactive_P_production": 0.0, "phosphate_loss": 0.0, "net_reactive_P": 0.0,
                 "precipitated_fraction": 0.0, "p_mass_residual": 0.0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {"phosphate": "float", "polyphosphate": "float",
                                "reactive_P": "float", "mineral_P": "float",
                                "reactive_P_production": "float", "phosphate_loss": "float",
                                "net_reactive_P": "float", "precipitated_fraction": "float",
                                "p_mass_residual": "float", "global_time": "float"}},
            "inputs": {"phosphate": ["P", "phosphate"], "polyphosphate": ["P", "polyphosphate"],
                       "reactive_P": ["P", "reactive_P"], "mineral_P": ["P", "mineral_P"],
                       "reactive_P_production": ["flux", "reactive_P_production"],
                       "phosphate_loss": ["flux", "phosphate_loss"],
                       "net_reactive_P": ["flux", "net_reactive_P"],
                       "precipitated_fraction": ["flux", "precipitated_fraction"],
                       "p_mass_residual": ["flux", "p_mass_residual"],
                       "global_time": ["global_time"]},
        },
    }
