"""Campaign 0 composite — the vent-reactor baseline (REDUCED REPRODUCTION).

Wires Module A (``SerpentinizationReproductionProcess``) → Module B
(``VentReactorReproductionProcess``) through shared vent/rates stores: the
serpentinization source feeds H2/alkalinity/heat into a well-mixed vent–ocean
reactor that relaxes T, pH and porosity toward Lost City–like targets. This is
the og-00 study's baseline composite; the processes are reduced reproductions
(not PHREEQC/Reaktoro/FiPy), see ``workspace/notes/modules.md``.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator


@composite_generator(
    name="og_00_vent_reactor_baseline",
    description="Campaign 0 — reduced serpentinization-fed vent–ocean reactor; "
                "settles into the Lost City T/pH window with sustained H2+alkalinity flux.",
    parameters={
        "flow_velocity": {"type": "float", "default": 1.0e-3,
                          "description": "Boundary water flux through the reaction zone (m/s)"},
        "t_target": {"type": "float", "default": 340.0,
                     "description": "Mixing-target temperature (K); Lost City mid-window ~340 K"},
        "h2_rate_max": {"type": "float", "default": 1.0e-3,
                        "description": "Peak H2 source rate at reference flow (mol/s)"},
    },
    default_n_steps=120,
    # Persisted sink so the og-00 behavior tests (T/pH window, sustained flux)
    # can be evaluated from a real parquet store (RAM-only runs stay "blocked").
    emitters=[{
        "address": "local:ParquetEmitter",
        "paths": [
            "vent/temperature", "vent/pH", "vent/porosity",
            "vent/H2", "vent/alkalinity",
            "rates/H2_flux", "rates/alkalinity_flux",
            "global_time",
        ],
    }],
)
def vent_reactor_baseline(core=None, *, flow_velocity=1.0e-3, t_target=340.0, h2_rate_max=1.0e-3):
    return {
        "serpentinization": {
            "_type": "process",
            "address": "local:SerpentinizationReproductionProcess",
            "config": {"h2_rate_max": h2_rate_max},
            "interval": 1.0,
            "inputs": {"temperature": ["vent", "temperature"],
                       "flow_velocity": ["boundary", "flow_velocity"]},
            "outputs": {"H2": ["vent", "H2"], "alkalinity": ["vent", "alkalinity"],
                        "heat": ["vent", "heat"], "H2_flux": ["rates", "H2_flux"],
                        "alkalinity_flux": ["rates", "alkalinity_flux"],
                        "heat_flux": ["rates", "heat_flux"]},
        },
        "reactor": {
            "_type": "process",
            "address": "local:VentReactorReproductionProcess",
            "config": {"t_target": t_target},
            "interval": 1.0,
            "inputs": {"temperature": ["vent", "temperature"], "pH": ["vent", "pH"],
                       "porosity": ["vent", "porosity"], "H2": ["vent", "H2"],
                       "alkalinity": ["vent", "alkalinity"], "heat": ["vent", "heat"]},
            "outputs": {"temperature": ["vent", "temperature"], "pH": ["vent", "pH"],
                        "porosity": ["vent", "porosity"]},
        },
        "vent": {"temperature": 300.0, "pH": 7.2, "porosity": 0.35,
                 "H2": 0.0, "alkalinity": 0.0, "heat": 0.0},
        "boundary": {"flow_velocity": flow_velocity},
        "rates": {"H2_flux": 0.0, "alkalinity_flux": 0.0, "heat_flux": 0.0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {"temperature": "float", "pH": "float", "porosity": "float",
                                "H2": "float", "alkalinity": "float",
                                "H2_flux": "float", "alkalinity_flux": "float",
                                "global_time": "float"}},
            "inputs": {"temperature": ["vent", "temperature"], "pH": ["vent", "pH"],
                       "porosity": ["vent", "porosity"], "H2": ["vent", "H2"],
                       "alkalinity": ["vent", "alkalinity"],
                       "H2_flux": ["rates", "H2_flux"], "alkalinity_flux": ["rates", "alkalinity_flux"],
                       "global_time": ["global_time"]},
        },
    }
