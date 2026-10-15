"""Agent growth toward division — the driver for the physical-reproduction
lineage (Phase 5, og-growth-alt).

Growth is abstracted to the division trigger: :class:`AgentGrowthStep`
increments every individual's ``division_state`` each step (map-add on the
agents store), so an individual grows to the division threshold, divides (a
``_divide`` structural rewrite, :class:`~viva_genesis.boundary_rewrites.DivisionStep`),
and the daughters grow again — a real multi-generation lineage in the agents
map, with matter halved (conserved) at each division.
"""
from __future__ import annotations

from process_bigraph import Process, Step


class AgentGrowthProcess(Process):
    """Advance every individual toward division by adding ``growth_rate * interval``
    to its ``division_state`` each tick (a map-add merge on the agents store). It
    is a Process (time-driven) so it runs EVERY tick — a Step would fire only when
    an external input changed. It drives the growth→divide cycle; the conserving
    split is DivisionStep's job."""

    config_schema = {"growth_rate": {"_type": "float", "_default": 0.34}}

    def inputs(self):
        return {"agents": "map[vg_individual]"}

    def outputs(self):
        return {"agents": "map[vg_individual]"}

    def update(self, state, interval):
        agents = state.get("agents", {}) or {}
        if not agents:
            return {}
        g = float(self.config["growth_rate"]) * float(interval)
        # map-add: +g onto each existing individual's division_state
        return {"agents": {k: {"division_state": g} for k in agents}}


class LineageStatsProcess(Process):
    """Read-only lineage statistics over the agents map: the population size, the
    deepest generation reached (``persistence`` carries the generation counter),
    and the total volume (conserved across divisions — daughter volumes sum to the
    mother). Drives the og-growth-alt gates."""

    def inputs(self):
        return {"agents": "map[vg_individual]"}

    def outputs(self):
        return {"n_agents": "overwrite[float]", "max_generation": "overwrite[float]",
                "total_volume": "overwrite[float]"}

    def update(self, state, interval):
        agents = {k: v for k, v in (state.get("agents", {}) or {}).items()
                  if isinstance(v, dict) and "internal_amounts" in v}
        gens = [float(a.get("persistence", 0.0)) for a in agents.values()]
        vols = [float(a.get("volume", 0.0)) for a in agents.values()]
        return {
            "n_agents": float(len(agents)),
            "max_generation": max(gens) if gens else 0.0,
            "total_volume": sum(vols),
        }
