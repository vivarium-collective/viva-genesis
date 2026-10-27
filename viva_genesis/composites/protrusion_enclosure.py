"""Protrusion-to-enclosure composite (eukaryogenesis S3).

Wraps :class:`~viva_genesis.membrane_enclosure.MembraneEnclosureProcess` into a one-process
composite that, over an ensemble of partner radii, emits the enclosure probability, the membrane
area-conservation residual, and the wrapped fraction. ``topology`` selects the arm — classical
engulfment, inside-out wrapping, or a no-enclosure control — so physical enclosure can be judged
as a separate hurdle from any metabolic benefit (S1/S2): morphology alone does not demonstrate
engulfment, the area + bending-energy budget does.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

_EMIT_PATHS = [
    "enc/enclosure_probability", "enc/membrane_area_conservation_residual",
    "enc/wrapped_fraction", "global_time",
]


@composite_generator(
    name="protrusion_enclosure",
    methods=["coarse-grained membrane area + Helfrich bending-energy budget over a partner-radius ensemble"],
    fidelity="geometric_feasibility",
    description=(
        "Protrusion-to-enclosure membrane mechanics (eukaryogenesis S3). A host protrusion of "
        "finite membrane area extends at an observed rate and attempts to wrap a bacterial "
        "partner; enclosure succeeds, per partner radius, only when the available area covers the "
        "partner AND adhesion clears the Helfrich bending cost. Over a partner-radius ensemble it "
        "emits an enclosure PROBABILITY, so morphology alone does not imply engulfment. topology "
        "selects classical engulfment, inside-out wrapping, or a no-enclosure control. "
        "Deterministic, coarse-grained first fidelity."
    ),
    parameters={
        "topology": {"type": "string", "default": "classical_engulfment",
                     "description": "classical_engulfment | inside_out | no_enclosure (control)"},
        "protrusion_area_um2": {"type": "float", "default": 4.0,
                                "description": "Membrane area the host protrusion can deploy (um^2)"},
        "bending_modulus_kT": {"type": "float", "default": 20.0, "description": "Helfrich bending modulus (kT)"},
        "adhesion_energy_kT": {"type": "float", "default": 600.0,
                               "description": "Total adhesion energy available on wrapping (kT); must clear 8*pi*kappa"},
        "partner_radius_min_um": {"type": "float", "default": 0.2, "description": "Ensemble min partner radius (um)"},
        "partner_radius_max_um": {"type": "float", "default": 0.8, "description": "Ensemble max partner radius (um)"},
    },
    default_n_steps=30,
    preferred_time="1 hour",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def protrusion_enclosure(core=None, *, topology="classical_engulfment", protrusion_area_um2=4.0,
                         bending_modulus_kT=20.0, adhesion_energy_kT=600.0,
                         partner_radius_min_um=0.2, partner_radius_max_um=0.8):
    if core is None:
        core = build_core()
    return {
        "enclosure": {
            "_type": "process",
            "address": "local:MembraneEnclosureProcess",
            "config": {"topology": topology, "protrusion_area_um2": protrusion_area_um2,
                       "bending_modulus_kT": bending_modulus_kT, "adhesion_energy_kT": adhesion_energy_kT,
                       "partner_radius_min_um": partner_radius_min_um,
                       "partner_radius_max_um": partner_radius_max_um},
            "interval": 1.0,
            "inputs": {},
            "outputs": {"enclosure_probability": ["enc", "enclosure_probability"],
                        "membrane_area_conservation_residual": ["enc", "membrane_area_conservation_residual"],
                        "wrapped_fraction": ["enc", "wrapped_fraction"]},
        },
        "enc": {"enclosure_probability": 0.0, "membrane_area_conservation_residual": 0.0,
                "wrapped_fraction": 0.0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {"enclosure_probability": "float",
                                "membrane_area_conservation_residual": "float",
                                "wrapped_fraction": "float", "global_time": "float"}},
            "inputs": {"enclosure_probability": ["enc", "enclosure_probability"],
                       "membrane_area_conservation_residual": ["enc", "membrane_area_conservation_residual"],
                       "wrapped_fraction": ["enc", "wrapped_fraction"],
                       "global_time": ["global_time"]},
        },
    }
