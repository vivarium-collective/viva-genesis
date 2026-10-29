"""Protrusion-to-enclosure, the active-protrusion MEMBRANE arm (eukaryogenesis S3).

The higher-fidelity companion to the coarse ``protrusion_enclosure`` budget arm and
the 2D passive-adhesion ``protrusion_enclosure_cpm`` arm. It wraps
:class:`~viva_genesis.membrane_wrapping.MembraneWrappingProcess` — the membrane-wrapping
transition (Deserno/Lipowsky) with an active protrusion force — so the question
"can the observed protrusion mechanics reach STABLE wrapping?" is tested as the
balance of Helfrich bending, adhesion, membrane tension, a finite protrusion-area
reservoir, and the active protrusion work, in 3D. Over a partner-radius ensemble it
emits the enclosure PROBABILITY, the wrapping size window, and the share of
enclosures that need the active force. ``topology`` selects classical engulfment
(external wrap, full 4*pi*R^2 cost) vs inside-out invagination (~half the cost,
Baum & Baum 2014) vs a no-enclosure control.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

_EMIT_PATHS = [
    "enc/enclosure_probability", "enc/wrapped_fraction",
    "enc/size_window_min_um", "enc/size_window_max_um",
    "enc/protrusion_required_fraction", "global_time",
]


@composite_generator(
    name="protrusion_enclosure_membrane",
    methods=["membrane-wrapping transition (Helfrich bending + adhesion + tension + active protrusion force) over a partner-radius ensemble"],
    fidelity="continuum_membrane_energetics",
    description=(
        "Active-protrusion membrane-wrapping mechanics (eukaryogenesis S3, continuum "
        "energetics). Tests whether an actin-driven host protrusion supplies enough work "
        "to carry a lipid membrane over the Helfrich bending barrier to a stable fully "
        "wrapped state around a bacterial partner, given adhesion, membrane tension, and a "
        "finite protrusion-area reservoir. Emits enclosure PROBABILITY over a partner-radius "
        "ensemble and the share of enclosures that require the active force — the mechanism "
        "the question is about, not passive differential adhesion. Validated against the "
        "classic wrapping threshold (reduced adhesion = 2). The next fidelity rung is a "
        "triangulated-mesh run (pbg-mem3dg)."
    ),
    parameters={
        "topology": {"type": "string", "default": "classical_engulfment",
                     "description": "classical_engulfment | inside_out | no_enclosure (control)"},
        "bending_modulus_kT": {"type": "float", "default": 20.0, "description": "Helfrich kappa (lipid bilayer)"},
        "adhesion_per_um2_kT": {"type": "float", "default": 250.0, "description": "specific adhesion energy per area"},
        "tension_per_um2_kT": {"type": "float", "default": 200.0, "description": "membrane tension (low-tension regime)"},
        "protrusion_force_pN": {"type": "float", "default": 10.0, "description": "active protrusion force (actin/Radler 2026 scale)"},
        "max_membrane_area_um2": {"type": "float", "default": 4.0, "description": "membrane area the protrusion can deploy"},
        "partner_radius_min_um": {"type": "float", "default": 0.2, "description": "ensemble min partner radius (um)"},
        "partner_radius_max_um": {"type": "float", "default": 0.8, "description": "ensemble max partner radius (um)"},
    },
    default_n_steps=1,
    preferred_time="1 hour",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def protrusion_enclosure_membrane(core=None, *, topology="classical_engulfment",
                                  bending_modulus_kT=20.0, adhesion_per_um2_kT=250.0,
                                  tension_per_um2_kT=200.0, protrusion_force_pN=10.0,
                                  max_membrane_area_um2=4.0,
                                  partner_radius_min_um=0.2, partner_radius_max_um=0.8):
    if core is None:
        core = build_core()
    return {
        "wrap": {
            "_type": "process",
            "address": "local:MembraneWrappingProcess",
            "config": {"topology": topology, "bending_modulus_kT": bending_modulus_kT,
                       "adhesion_per_um2_kT": adhesion_per_um2_kT,
                       "tension_per_um2_kT": tension_per_um2_kT,
                       "protrusion_force_pN": protrusion_force_pN,
                       "max_membrane_area_um2": max_membrane_area_um2,
                       "partner_radius_min_um": partner_radius_min_um,
                       "partner_radius_max_um": partner_radius_max_um},
            "interval": 1.0,
            "inputs": {},
            "outputs": {"enclosure_probability": ["enc", "enclosure_probability"],
                        "wrapped_fraction": ["enc", "wrapped_fraction"],
                        "size_window_min_um": ["enc", "size_window_min_um"],
                        "size_window_max_um": ["enc", "size_window_max_um"],
                        "protrusion_required_fraction": ["enc", "protrusion_required_fraction"]},
        },
        "enc": {"enclosure_probability": 0.0, "wrapped_fraction": 0.0,
                "size_window_min_um": 0.0, "size_window_max_um": 0.0,
                "protrusion_required_fraction": 0.0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {"enclosure_probability": "float", "wrapped_fraction": "float",
                                "size_window_min_um": "float", "size_window_max_um": "float",
                                "protrusion_required_fraction": "float", "global_time": "float"}},
            "inputs": {"enclosure_probability": ["enc", "enclosure_probability"],
                       "wrapped_fraction": ["enc", "wrapped_fraction"],
                       "size_window_min_um": ["enc", "size_window_min_um"],
                       "size_window_max_um": ["enc", "size_window_max_um"],
                       "protrusion_required_fraction": ["enc", "protrusion_required_fraction"],
                       "global_time": ["global_time"]},
        },
    }
