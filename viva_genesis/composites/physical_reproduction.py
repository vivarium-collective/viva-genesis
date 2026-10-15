"""og-growth-alt — physical reproduction: a multi-generation lineage in the
agents map (Phase 5).

A single individual grows (:class:`~viva_genesis.growth_rewrites.AgentGrowthStep`
drives its ``division_state`` to threshold), divides (a ``_divide`` structural
rewrite, :class:`~viva_genesis.boundary_rewrites.DivisionStep`, halving matter +
volume), and the daughters grow and divide in turn — a real >=3-generation
lineage in the ``agents`` map. The :class:`~viva_genesis.ledger.RewriteLedgerProcess`
audits that every division conserves matter (partition residual 0) and
:class:`~viva_genesis.growth_rewrites.LineageStatsProcess` reports the deepest
generation and the total volume (constant across divisions — the daughters'
volumes sum to the mother's).
"""
from __future__ import annotations

from viva_superpowers.composite_generator import composite_generator

from ..core import build_core

_EMIT_PATHS = [
    "stats/n_agents", "stats/max_generation", "stats/total_volume",
    "ledger/partition_residual_max", "ledger/rewrite_residual_max", "ledger/rewrite_ok",
    "global_time",
]
_EMIT_TYPES = {
    "n_agents": "float", "max_generation": "float", "total_volume": "float",
    "partition_residual_max": "float", "rewrite_residual_max": "float",
    "rewrite_ok": "float", "global_time": "float",
}


def _seed_agent(volume, amounts):
    return {"id": "founder", "volume": float(volume),
            "internal_amounts": {k: float(v) for k, v in amounts.items()},
            "boundary": {"area": 1.0, "integrity": 1.0},
            "division_state": 0.0, "persistence": 0.0}


@composite_generator(
    name="physical_reproduction",
    methods=["growth -> division_state", "_divide structural rewrite (matter halved)",
             "lineage over agents map", "rewrite + partition conservation ledger"],
    fidelity="reproduction",
    description=(
        "og-growth-alt: a founder individual grows to a division threshold and divides "
        "by a _divide structural rewrite (matter + volume halved); the daughters grow "
        "and divide in turn, building a >=3-generation lineage in the agents map. A "
        "RewriteLedgerProcess audits that every division conserves matter (partition "
        "residual 0) and LineageStatsProcess reports the deepest generation + the total "
        "volume, which stays constant across divisions (the daughters' volumes sum to "
        "the mother's)."
    ),
    parameters={
        "growth_per_step": {"type": "number", "default": 0.34,
                            "description": "division_state added per step (growth to the division threshold) [vg-data: division_threshold]"},
        "founder_volume": {"type": "number", "default": 8.0e-12, "description": "Founder individual volume (liter)"},
        "founder_formate": {"type": "number", "default": 8.0, "description": "Founder internal formate (mol)"},
        "founder_acetate": {"type": "number", "default": 4.0, "description": "Founder internal acetate (mol)"},
    },
    default_n_steps=30,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def physical_reproduction(core=None, *, growth_per_step=0.34, founder_volume=8.0e-12,
                          founder_formate=8.0, founder_acetate=4.0):
    if core is None:
        core = build_core()
    founder = _seed_agent(founder_volume, {"formate": founder_formate, "acetate": founder_acetate})
    return {
        "agents": {"founder": founder},
        "diag": {"pr": 0.0, "rm": 0.0},
        "grow": {
            "_type": "process", "address": "local:AgentGrowthProcess",
            "config": {"growth_rate": float(growth_per_step)},
            "inputs": {"agents": ["agents"]}, "outputs": {"agents": ["agents"]},
        },
        "div": {
            "_type": "step", "address": "local:DivisionStep", "config": {},
            "inputs": {"agents": ["agents"]},
            "outputs": {"agents": ["agents"], "division_count": ["diag", "division_count"],
                        "partition_residual": ["diag", "pr"]},
        },
        "rewrite_ledger": {
            "_type": "process", "address": "local:RewriteLedgerProcess", "config": {},
            "inputs": {"agents": ["agents"], "localized": ["localized"],
                       "partition_residual": ["diag", "pr"], "removed_matter": ["diag", "rm"]},
            "outputs": {"rewrite_residual_max": ["ledger", "rewrite_residual_max"],
                        "partition_residual_max": ["ledger", "partition_residual_max"],
                        "rewrite_ok": ["ledger", "rewrite_ok"],
                        "rewrite_residual": ["ledger", "rewrite_residual"],
                        "agent_matter": ["ledger", "agent_matter"], "n_agents": ["ledger", "na"]},
        },
        "lineage_stats": {
            "_type": "process", "address": "local:LineageStatsProcess", "config": {},
            "inputs": {"agents": ["agents"]},
            "outputs": {"n_agents": ["stats", "n_agents"], "max_generation": ["stats", "max_generation"],
                        "total_volume": ["stats", "total_volume"]},
        },
        "localized": {},
        "ledger": {"rewrite_residual_max": 0.0, "partition_residual_max": 0.0, "rewrite_ok": 1.0,
                   "rewrite_residual": 0.0, "agent_matter": 0.0, "na": 0.0},
        "stats": {"n_agents": 1.0, "max_generation": 0.0, "total_volume": float(founder_volume)},
        "emitter": {
            "_type": "step", "address": "local:RAMEmitter",
            "config": {"emit": dict(_EMIT_TYPES)},
            "inputs": {
                "n_agents": ["stats", "n_agents"], "max_generation": ["stats", "max_generation"],
                "total_volume": ["stats", "total_volume"],
                "partition_residual_max": ["ledger", "partition_residual_max"],
                "rewrite_residual_max": ["ledger", "rewrite_residual_max"],
                "rewrite_ok": ["ledger", "rewrite_ok"], "global_time": ["global_time"],
            },
        },
    }
