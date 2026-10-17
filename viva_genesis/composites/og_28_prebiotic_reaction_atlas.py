"""Study 28 — Prebiotic Reaction Atlas (the shared data-asset build).

Study 28's baseline composite. Unlike the sim composites, this one BUILDS the
versioned reaction atlas: it runs ReactionAtlasBuildProcess (real extract ->
validate pipeline from reaction_atlas.build) over the measured-tier seed and
emits coverage + the zero-leakage guarantee. The decision test — "no unexplained
precursor or unbalanced reaction enters an accepted model" — is observable here as
``accepted_balance_violations == 0`` while an unbalanced candidate is held back
(``balance_violations_held`` > 0).

Produces the shared asset at ``workspace/datasets/prebiotic-reaction-atlas/``;
feeds studies 29/30/31 (the 28->29 handoff: canonical species, balanced
stoichiometry, confidence tiers).
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

_ATLAS_PORTS = ("n_accepted", "n_proposed", "n_measured", "n_inferred",
                "n_hypothetical", "balance_violations_held",
                "accepted_balance_violations", "carbon_species_covered")
_EMIT_PATHS = ["atlas/" + p for p in _ATLAS_PORTS]


@composite_generator(
    name="og_28_prebiotic_reaction_atlas",
    methods=["RDKit canonicalization + balancing", "eQuilibrator ΔG feasibility (opt-in)",
             "write-time balance/charge/provenance validator (zero-leakage gate)"],
    fidelity="real",
    description=(
        "Study 28: build the versioned Prebiotic Reaction Atlas. Runs the real "
        "extract->validate pipeline over the measured-tier carbon-fixation seed and "
        "reports coverage + the zero-leakage guarantee: accepted_balance_violations == 0 "
        "while an unbalanced candidate is held back in proposed. Produces the shared "
        "data asset consumed by studies 29/30/31."
    ),
    parameters={
        "run_feasibility": {"type": "boolean", "default": False,
                            "description": "Attach eQuilibrator ΔG feasibility (advisory; needs the real bridge)"},
    },
    default_n_steps=1,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def og_28_prebiotic_reaction_atlas(core=None, *, run_feasibility=False):
    if core is None:
        core = build_core()
    return {
        "atlas_build": {
            "_type": "process",
            "address": "local:ReactionAtlasBuildProcess",
            "config": {"run_feasibility": bool(run_feasibility)},
            "interval": 1.0,
            "inputs": {},
            "outputs": {p: ["atlas", p] for p in _ATLAS_PORTS},
        },
        "atlas": {p: 0.0 for p in _ATLAS_PORTS},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {p: "float" for p in _ATLAS_PORTS}},
            "inputs": {p: ["atlas", p] for p in _ATLAS_PORTS},
        },
    }
