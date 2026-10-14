"""Campaign VII composite — cross-feeding metacommunity (og-07, ecology before LUCA).

A reusable metacommunity module (Module L): N connected compartments, each a
coarse-grained capability vector over the protometabolic function set, evolving
under cross-feeding, horizontal transfer and parasite/cooperator roles
(``CrossFeedingMetacommunityProcess``). One parameterized generator drives every
study condition:

  - connected (canonical)  : exchange_rate > 0, hgt_rate > 0 → capabilities spread,
                             redundancy (robustness) emerges above the isolated
                             counterfactual.
  - isolated control       : exchange_rate = 0, hgt_rate = 0 → each compartment holds
                             only its intrinsic capabilities; no emergent redundancy.

Emits the metacommunity robustness, the within-run isolated counterfactual, their
difference, the collective capability diversity and the overlap with the anaerobic
LUCA reconstruction (reported as a boundary). Coarse-grained, deterministic
(reproducible given ``seed``); a reproduction, not a wrapped ALife engine.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

_EMIT_PATHS = [
    "community/metacommunity_robustness", "community/isolated_robustness",
    "community/robustness_gain", "community/capability_diversity",
    "community/luca_capability_overlap", "community/mean_capability",
    "global_time",
]


@composite_generator(
    name="cross_feeding_metacommunity",
    methods=["coarse-grained metacommunity exchange model"],
    fidelity="reproduction",
    description=(
        "A reusable cross-feeding metacommunity module (Module L). N connected "
        "compartments, each a coarse-grained capability vector over a protometabolic "
        "function set, evolving under cross-feeding (byproduct of one feeds the next "
        "capability in a neighbour), horizontal transfer, and parasite/cooperator roles. "
        "Connected heterogeneous populations develop capability redundancy (robustness) "
        "and a collective repertoire single compartments do not; the emergent set's "
        "overlap with the anaerobic H2/CO2/FeS LUCA reconstruction is reported as a "
        "far-end boundary, not a target. Coarse-grained, deterministic reproduction "
        "(not wrapped ALife)."
    ),
    parameters={
        "n_compartments": {"type": "integer", "default": 8, "description": "Number of connected compartments"},
        "exchange_rate": {"type": "float", "default": 0.3, "description": "Cross-feeding strength (use isolated flag, not 0, to disable)"},
        "diversity": {"type": "float", "default": 0.75, "description": "Inter-compartment heterogeneity (0 identical; 1 all different)"},
        "parasite_load": {"type": "float", "default": 0.0, "description": "Fraction of compartments that drain neighbours"},
        "hgt_rate": {"type": "float", "default": 0.1, "description": "Horizontal-transfer rate (0 = no spread)"},
        "isolated": {"type": "boolean", "default": False, "description": "Isolated counterfactual arm: no cross-feeding/HGT/parasitism (use this, not exchange_rate=0)"},
        "seed": {"type": "integer", "default": 1, "description": "RNG seed (reproducible assignment)"},
    },
    visualizations=[
        {"name": "metacommunity-phase-map", "address": "local:MetacommunityPhaseMap",
         "config": {"title": "Where cross-feeding robustness emerges"}},
    ],
    default_n_steps=40,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def cross_feeding_metacommunity(core=None, *, n_compartments=8, exchange_rate=0.3,
                                diversity=0.75, parasite_load=0.0, hgt_rate=0.1,
                                isolated=False, seed=1):
    return {
        "metacommunity": {
            "_type": "process",
            "address": "local:CrossFeedingMetacommunityProcess",
            "config": {"n_compartments": int(n_compartments), "exchange_rate": float(exchange_rate),
                       "diversity": float(diversity), "parasite_load": float(parasite_load),
                       "hgt_rate": float(hgt_rate), "isolated": bool(isolated), "seed": int(seed)},
            "interval": 1.0,
            "inputs": {},
            "outputs": {"metacommunity_robustness": ["community", "metacommunity_robustness"],
                        "isolated_robustness": ["community", "isolated_robustness"],
                        "robustness_gain": ["community", "robustness_gain"],
                        "capability_diversity": ["community", "capability_diversity"],
                        "luca_capability_overlap": ["community", "luca_capability_overlap"],
                        "mean_capability": ["community", "mean_capability"]},
        },
        "community": {"metacommunity_robustness": 0.0, "isolated_robustness": 0.0,
                      "robustness_gain": 0.0, "capability_diversity": 0.0,
                      "luca_capability_overlap": 0.0, "mean_capability": 0.0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {"metacommunity_robustness": "float", "isolated_robustness": "float",
                                "robustness_gain": "float", "capability_diversity": "float",
                                "luca_capability_overlap": "float", "mean_capability": "float",
                                "global_time": "float"}},
            "inputs": {"metacommunity_robustness": ["community", "metacommunity_robustness"],
                       "isolated_robustness": ["community", "isolated_robustness"],
                       "robustness_gain": ["community", "robustness_gain"],
                       "capability_diversity": ["community", "capability_diversity"],
                       "luca_capability_overlap": ["community", "luca_capability_overlap"],
                       "mean_capability": ["community", "mean_capability"],
                       "global_time": ["global_time"]},
        },
    }
