"""Campaign III composite — dilution to localized individuals (og-03).

A reusable thermophoretic-concentration module: the real FiPy thermal-trap
(``ThermophoreticTrapProcess``) that turns a dilute vent feed into a LOCALIZED,
concentrated pocket — the first "individual". One parameterized generator drives
every study condition:

  - favorable trap   : defaults (5 mm × 0.1 mm pore, ΔT 30 K, flow 1e-4 m/s) →
                       Baaske >10^8-fold enrichment
  - no-flow control  : flow_velocity=0 (no convection → no trap)
  - open-pore control: porosity≈1 (feed washes through → no individual)

The ``enrichment_factor`` and ``accumulation_peclet`` are read from the trap's
FiPy solve; ``residence_time`` and the FVM conservation residual come with them.
Requires ``fipy`` installed.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

_EMIT_PATHS = [
    "trap/enrichment_factor", "trap/accumulation_peclet", "trap/residence_time",
    "trap/flux_divergence_residual",
    "global_time",
]


@composite_generator(
    name="thermophoretic_concentration",
    description=(
        "A reusable thermophoretic-concentration module for the Baaske thermal "
        "trap. Module F = genuine FiPy finite-volume accumulation column: "
        "thermophoresis (Soret) + buoyant convection concentrate a dilute feed, "
        "enrichment exponential in pore length (>10^8 favorable, ~1 in controls). "
        "flow_velocity=0 / porosity=1 give the no-trap controls. Requires fipy."
    ),
    parameters={
        "flow_velocity": {"type": "float", "default": 1.0e-4,
                          "description": "Buoyant convective flow in the pore (m/s); 0 = no-convection control"},
        "porosity": {"type": "float", "default": 0.3,
                     "description": "Pore porosity/openness (0-1); ~1 = open-pore (wash-through) control"},
        "temperature": {"type": "float", "default": 333.15, "description": "Mean pore temperature (K)"},
        "pore_length": {"type": "float", "default": 5.0e-3, "description": "Pore length (m); longer = more enrichment"},
        "delta_T": {"type": "float", "default": 30.0, "description": "Cross-pore temperature difference (K)"},
    },
    default_n_steps=30,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def thermophoretic_concentration(core=None, *, flow_velocity=1.0e-4, porosity=0.3,
                                 temperature=333.15, pore_length=5.0e-3, delta_T=30.0):
    return {
        "pore": {
            "_type": "process",
            "address": "local:ThermophoreticTrapProcess",
            "config": {"pore_length": pore_length, "delta_T": delta_T},
            "interval": 1.0,
            "inputs": {"temperature": ["env", "temperature"],
                       "flow_velocity": ["env", "flow_velocity"],
                       "porosity": ["env", "porosity"]},
            "outputs": {"enrichment_factor": ["trap", "enrichment_factor"],
                        "accumulation_peclet": ["trap", "accumulation_peclet"],
                        "residence_time": ["trap", "residence_time"],
                        "flux_divergence_residual": ["trap", "flux_divergence_residual"]},
        },
        "env": {"temperature": temperature, "flow_velocity": flow_velocity, "porosity": porosity},
        "trap": {"enrichment_factor": 1.0, "accumulation_peclet": 0.0,
                 "residence_time": 0.0, "flux_divergence_residual": 0.0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {"enrichment_factor": "float", "accumulation_peclet": "float",
                                "residence_time": "float", "flux_divergence_residual": "float",
                                "global_time": "float"}},
            "inputs": {"enrichment_factor": ["trap", "enrichment_factor"],
                       "accumulation_peclet": ["trap", "accumulation_peclet"],
                       "residence_time": ["trap", "residence_time"],
                       "flux_divergence_residual": ["trap", "flux_divergence_residual"],
                       "global_time": ["global_time"]},
        },
    }
