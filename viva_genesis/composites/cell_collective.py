"""cell_collective — the multicellularity first-cycle composite (A/B/C comparison).

Drives the reopened-seed first cycle: does ecological selection plus simple clonal adhesion
suffice to produce group FORMATION and a group-level FITNESS advantage, and does oxygen/
transport BOUND it? Three stackable arms configured by parameters:

  A (adhesion only)              -> group_life_cycle_persistence high, group_fitness_advantage ~ 0
  B (adhesion + predation/settling) -> group_fitness_advantage > 0 (ecology rewards groups)
  C (B + oxygen-limited growth)  -> advantage bounded; very large groups lose it (interior starvation)

See viva_genesis.cell_collective.CellCollectiveProcess for the reduced-model rationale and scope.
Store-less observables read the settled trajectory. First-fidelity arm; explicit spatial
agent/mechanics backends (PhysiCell / viva-cpm / Spatio-Flux) are the next fidelity (a capability
gap to build).
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from ..cell_collective import CellCollectiveProcess  # registered via build_core (top-level scan)

_STORES = ["group_fraction", "mean_group_size", "unicell_fitness",
           "group_fitness", "group_fitness_advantage"]


def _settled(rows, key, frac=0.25):
    n = max(1, int(round(len(rows) * frac)))
    t = [float(r.get(key, float("nan"))) for r in rows[-n:]]
    t = [x for x in t if x == x]
    return sum(t) / len(t) if t else float("nan")


@composite_generator(
    name="cell_collective",
    emitters=[{"address": "local:SQLiteEmitter", "paths": ["global_time", *_STORES]}],
    parameters={
        "adhesion": {"type": "float", "default": 0.8, "description": "clonal incomplete separation / bond drive"},
        "fragmentation": {"type": "float", "default": 0.2, "description": "group breakup rate"},
        "division_rate": {"type": "float", "default": 0.5, "description": "per-cell division rate"},
        "base_predation": {"type": "float", "default": 0.4, "description": "size-independent death rate"},
        "predation_size_reward": {"type": "float", "default": 0.8, "description": "ecology: group size reduces predation"},
        "predation_size_threshold": {"type": "float", "default": 3.0, "description": "size at which protection engages"},
        "transport_penalty": {"type": "float", "default": 0.8, "description": "oxygen-limited growth penalty for large groups"},
        "oxygen_size_limit": {"type": "float", "default": 6.0, "description": "size above which interior starves"},
        "size_scale": {"type": "float", "default": 4.0, "description": "adhesion/fragmentation -> mean group size"},
        "relax_rate": {"type": "float", "default": 0.4, "description": "relaxation rate toward equilibrium"},
        "sharpness": {"type": "float", "default": 2.0, "description": "sigmoid sharpness k"},
        "seed": {"type": "integer", "default": 1, "description": "random seed"},
    },
    description="Multicellularity first-cycle model: mean-field unicell/group population under "
                "adhesion, size-dependent predation/settling ecology, and oxygen-limited growth.",
)
def cell_collective(core=None, **params):
    if core is None:
        core = build_core()
    if "CellCollectiveProcess" not in core.link_registry:
        core.register_link("CellCollectiveProcess", CellCollectiveProcess)
    cfg = {k: (int(v) if k == "seed" else float(v)) for k, v in params.items()}
    io = {s: [s] for s in _STORES}
    init = {"group_fraction": 0.05, "mean_group_size": 1.0,
            "unicell_fitness": 0.0, "group_fitness": 0.0, "group_fitness_advantage": 0.0}
    return {
        "collective": {"_type": "process", "address": "local:CellCollectiveProcess",
                       "interval": 1.0, "config": cfg, "inputs": io, "outputs": io},
        **init,
    }


# ── store-less observables ───────────────────────────────────────────────────
def group_life_cycle_persistence(rows) -> float:
    """Settled fraction of the population in persistent clonal groups (S01). >=0.5 ⇒ adhesion
    sustains a group life cycle beyond fragmentation (not a transient aggregate)."""
    return _settled(rows, "group_fraction")


def group_fitness_advantage(rows) -> float:
    """Settled (group fitness − unicell fitness) (S02). >0 ⇒ ecological selection makes groups
    fitter than unicells; ~0 under adhesion alone (formation without a fitness advantage)."""
    return _settled(rows, "group_fitness_advantage")


def mean_group_size(rows) -> float:
    """Settled mean group size (S03) — the transport arm bounds this via interior starvation."""
    return _settled(rows, "mean_group_size")


def group_fitness(rows) -> float:
    return _settled(rows, "group_fitness")


def unicell_fitness(rows) -> float:
    return _settled(rows, "unicell_fitness")
