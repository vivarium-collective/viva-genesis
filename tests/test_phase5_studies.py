"""The two Phase-5 studies' composites + their gates (og-04-alt, og-growth-alt)."""
import pytest
from process_bigraph import Composite, gather_emitter_results

from viva_genesis.core import build_core


def _run(gen, t, **kw):
    core = build_core()
    sim = Composite({"state": gen(core, **kw)}, core=core)
    sim.run(float(t))
    return gather_emitter_results(sim)[("emitter",)][-1]


def test_endogenous_boundary_gate_forms_vs_ablated():
    from viva_genesis.composites.endogenous_boundary import endogenous_boundary
    fav = _run(endogenous_boundary, 40, k_synth=5e-2)
    abl = _run(endogenous_boundary, 40, k_synth=1e-12)  # ablated (0.0 would hit is_empty)
    assert fav["n_agents"] >= 1 and fav["rewrite_ok"] == 1.0
    assert abl["n_agents"] == 0
    assert fav["amphiphile"] > abl["amphiphile"]


def test_physical_reproduction_lineage_and_conservation():
    from viva_genesis.composites.physical_reproduction import physical_reproduction
    r = _run(physical_reproduction, 30, growth_per_step=0.4, founder_volume=8e-12)
    assert r["max_generation"] >= 3                     # >=3-generation lineage
    assert r["total_volume"] == pytest.approx(8e-12, abs=1e-15)  # volume conserved
    assert r["partition_residual_max"] == pytest.approx(0.0, abs=1e-9)
    assert r["rewrite_ok"] == 1.0


def test_phase5_derived_scalars_registered():
    from viva_genesis import evaluators
    reg = {}
    evaluators.register_derived_scalars(reg)
    assert {"rewrite_ok", "max_generation", "partition_residual_max"} <= set(reg)


def test_phase5_composites_discoverable():
    core = build_core()
    # the two study composites are registered generators resolvable by build_core
    for cls in ("EndogenousBoundaryViz", "PhysicalReproductionViz",
                "AgentGrowthProcess", "LineageStatsProcess"):
        assert cls in core.link_registry
