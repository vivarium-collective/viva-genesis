"""Campaign IV composite — mineral compartments to protocells (og-04).

A reusable mixed-amphiphile protocell module: the coarse-grained vesicle
self-assembly + permeability model (``ProtocellAssemblyProcess``, calibrated to
Jordan 2019) that tests whether organic boundaries enhance persistence without
isolating the individual from the geochemical gradient. One parameterized
generator drives every study condition:

  - favorable       : mixed amphiphiles (mix_fraction 0.4), alkaline vent pH,
                      seawater salt → vesicles form, retention AND access > 0
  - single-FA arm   : mix_fraction ≈ 0 → narrower window, fails on salt tolerance
  - extreme controls: high salt / acidic pH → no vesicles

Emits membrane area, permeability, compartment volume, viable-compartment count,
and the retention / access / individuality-access tradeoff.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

_EMIT_PATHS = [
    "protocell/viable_compartments", "protocell/individuality_access",
    "protocell/retention", "protocell/access",
    "protocell/membrane_area", "protocell/permeability", "protocell/compartment_volume",
    "global_time",
]


@composite_generator(
    name="mixed_amphiphile_protocell",
    description=(
        "A reusable mixed-amphiphile protocell module (Module G). Coarse-grained "
        "vesicle self-assembly + permeability calibrated to Jordan 2019: mixed "
        "single-chain amphiphiles broaden the pH / salt / divalent stability window "
        "and form vesicles that retain chemistry while staying permeable to the "
        "gradient (individuality without isolation). mix_fraction≈0 / high salt / "
        "acidic pH give the controls. Coarse-grained reproduction (not wrapped MD)."
    ),
    parameters={
        "mix_fraction": {"type": "float", "default": 0.4,
                         "description": "Co-surfactant fraction (0 = single fatty acid; higher = broader Jordan window)"},
        "pH": {"type": "float", "default": 9.0, "description": "Environment pH (alkaline vent)"},
        "ionic_strength": {"type": "float", "default": 0.35, "description": "Ionic strength (M); ~seawater 0.35"},
        "temperature": {"type": "float", "default": 318.15, "description": "Temperature (K)"},
    },
    visualizations=[
        {"name": "protocell-window", "address": "local:ProtocellWindowViz",
         "config": {"title": "The protocell window broadens (mixed amphiphiles)"}},
    ],
    default_n_steps=20,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def mixed_amphiphile_protocell(core=None, *, mix_fraction=0.4, pH=9.0,
                               ionic_strength=0.35, temperature=318.15):
    # Clamp an exact 0.0 to a negligible epsilon: process-bigraph's
    # is_empty(Float, 0.0) treats a literal 0.0 as "unset" and refills it with the
    # default (0.4), which would silently turn the single-fatty-acid control into a
    # mixed-amphiphile run. 1e-6 co-surfactant is physically ≈ single-FA but is
    # honored. (The process also reads mix_fraction via a state input for the same
    # reason.)
    mix_fraction = max(float(mix_fraction), 1.0e-6)
    return {
        "membrane": {
            "_type": "process",
            "address": "local:ProtocellAssemblyProcess",
            "config": {"mix_fraction": mix_fraction},
            "interval": 1.0,
            "inputs": {"pH": ["env", "pH"], "ionic_strength": ["env", "ionic_strength"],
                       "temperature": ["env", "temperature"],
                       # via state so an explicit 0.0 (single-FA control) is honored.
                       "mix_fraction": ["env", "mix_fraction"]},
            "outputs": {"membrane_area": ["protocell", "membrane_area"],
                        "permeability": ["protocell", "permeability"],
                        "compartment_volume": ["protocell", "compartment_volume"],
                        "viable_compartments": ["protocell", "viable_compartments"],
                        "retention": ["protocell", "retention"],
                        "access": ["protocell", "access"],
                        "individuality_access": ["protocell", "individuality_access"]},
        },
        "env": {"pH": pH, "ionic_strength": ionic_strength, "temperature": temperature,
                "mix_fraction": mix_fraction},
        "protocell": {"membrane_area": 0.0, "permeability": 0.0, "compartment_volume": 0.0,
                      "viable_compartments": 0, "retention": 0.0, "access": 0.0,
                      "individuality_access": 0.0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {"viable_compartments": "integer", "individuality_access": "float",
                                "retention": "float", "access": "float", "membrane_area": "float",
                                "permeability": "float", "compartment_volume": "float",
                                "global_time": "float"}},
            "inputs": {"viable_compartments": ["protocell", "viable_compartments"],
                       "individuality_access": ["protocell", "individuality_access"],
                       "retention": ["protocell", "retention"], "access": ["protocell", "access"],
                       "membrane_area": ["protocell", "membrane_area"],
                       "permeability": ["protocell", "permeability"],
                       "compartment_volume": ["protocell", "compartment_volume"],
                       "global_time": ["global_time"]},
        },
    }
