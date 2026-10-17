"""Study-17 composite: explicit amphiphile chain extension from the vent-carbon feed."""
from process_bigraph import Composite, gather_emitter_results
from viva_genesis.core import build_core
from viva_genesis.composites.og_17_amphiphile_chain_extension import og_17_amphiphile_chain_extension as og17


def test_generator_and_process_registered():
    from process_bigraph.composite_generator import _REGISTRY
    assert any(e.endswith(".og_17_amphiphile_chain_extension") for e in _REGISTRY)
    assert "AmphiphileChainExtensionProcess" in build_core().link_registry


def test_vent_feed_assembles_competent_composition():
    core = build_core()
    sim = Composite({"state": og17(core, acetate_feed=5.0e-2)}, core=core)
    sim.run(40.0)
    last = gather_emitter_results(sim)[("emitter",)][-1]
    assert last["amphiphile_total"] > 0.0          # amphiphiles form from vent carbon alone
    assert last["mean_chain_length"] >= 4.0
    assert last["aggregation_competent"] >= 1.0     # clears the CAC (membrane-competent)


def test_no_feed_no_assembly():
    core = build_core()
    sim = Composite({"state": og17(core, acetate_feed=0.0)}, core=core)
    sim.run(20.0)
    last = gather_emitter_results(sim)[("emitter",)][-1]
    assert last["amphiphile_total"] < 1e-9
    assert last["aggregation_competent"] < 1.0
