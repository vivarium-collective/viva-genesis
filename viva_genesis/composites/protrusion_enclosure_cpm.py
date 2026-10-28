"""Spatial protrusion-to-enclosure composite (eukaryogenesis S3, campaign composite B).

Embeds the real Rust Cellular Potts engine via
:class:`~viva_genesis.protrusion_enclosure_cpm.ProtrusionEnclosureCPMProcess`: a
deformable host and a compact symbiont whose host-symbiont adhesion ``j_hs`` is the
sweepable gate parameter. Running it emits the wrapping observables at ``enc/*``;
sweeping ``j_hs`` across ``j_sM - j_hM`` drives the enclosure transition the S3 gate
(G3 Enclosure) grades. The spatial companion to the analytical ``protrusion_enclosure``
composite — here enclosure is an emergent, measured outcome with real boundaries.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

CPM_ADDR = "local:!viva_genesis.protrusion_enclosure_cpm.ProtrusionEnclosureCPMProcess"


@composite_generator(
    name="protrusion_enclosure_cpm",
    methods=["Cellular Potts (Glazier-Graner-Hogeweg) differential-adhesion wrapping on the Rust cpm engine"],
    fidelity="spatial_dynamics",
    description=(
        "Eukaryogenesis S3 (protrusions to enclosure), SPATIAL campaign composite B. A host and a "
        "symbiont on the real Rust CPM engine with actual boundaries; sweeping host-symbiont "
        "adhesion j_hs across j_sM - j_hM moves the system through the wrapping transition (stable "
        "enclosure -> transient -> partial cup -> free symbiont). Emits enc/enclosure_fraction "
        "(1 = fully enclosed) and enc/enclosed. Enclosure is emergent, not an imposed threshold."
    ),
    parameters={
        "j_hs": {"type": "number", "default": 6.0,
                 "description": "host-symbiont adhesion (low = strong adhesion = enclosure; "
                                "transition at j_sM - j_hM = 12)"},
        "j_sM": {"type": "number", "default": 16.0, "description": "symbiont-medium surface tension"},
        "j_hM": {"type": "number", "default": 4.0,
                 "description": "host-medium surface tension (host cortical tension)"},
        "seed": {"type": "integer", "default": 7, "description": "RNG seed for the realization"},
    },
)
def protrusion_enclosure_cpm(core=None, j_hs=6.0, j_sM=16.0, j_hM=4.0, seed=7):
    return {
        "enclosure": {
            "_type": "process",
            "address": CPM_ADDR,
            "config": {"j_hs": float(j_hs), "j_sM": float(j_sM), "j_hM": float(j_hM),
                       "seed": int(seed), "mcs_per_update": 60},
            "inputs": {},
            "outputs": {
                "enclosure_fraction": ["enc", "enclosure_fraction"],
                "enclosed": ["enc", "enclosed"],
                "host_contact_faces": ["enc", "host_contact_faces"],
                "medium_contact_faces": ["enc", "medium_contact_faces"],
                "sweeps": ["enc", "sweeps"],
            },
        },
        "enc": {},
    }
