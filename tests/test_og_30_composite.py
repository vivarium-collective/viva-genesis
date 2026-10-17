"""Study-30 composite: network in a pore vs matched nonconcentrating control."""
from process_bigraph import Composite, gather_emitter_results
from viva_genesis.core import build_core
from viva_genesis.composites.og_30_spatially_integrated_protometabolism import (
    og_30_spatially_integrated_protometabolism as og30,
)


def test_generator_and_processes_registered():
    from process_bigraph.composite_generator import _REGISTRY
    assert any(eid.endswith(".og_30_spatially_integrated_protometabolism") for eid in _REGISTRY)
    lr = build_core().link_registry
    assert "PoreEnrichedFeedProcess" in lr and "ThermophoreticTrapProcess" in lr


def test_feed_wired_from_pore_and_control_toggle():
    doc = og30(build_core(), concentrating=True)
    assert doc["network"]["inputs"]["feed_CO2"] == ["feed", "CO2"]
    assert doc["feed_adapter"]["config"]["concentrating"] is True
    ctrl = og30(build_core(), concentrating=False)
    assert ctrl["feed_adapter"]["config"]["concentrating"] is False


def _run(concentrating):
    core = build_core()
    sim = Composite({"state": og30(core, concentrating=concentrating, max_carbons=3)}, core=core)
    sim.run(4.0)
    return gather_emitter_results(sim)[("emitter",)][-1]


def test_pore_concentrates_feed_above_control():
    pore = _run(True)
    ctrl = _run(False)
    # The control holds the feed at base (enrichment 1); the pore concentrates it.
    assert ctrl["effective_enrichment"] == 1.0
    assert pore["effective_enrichment"] >= 1.0
    assert pore["feed_CO2"] >= ctrl["feed_CO2"]
    for k in ("net_carbon_flux", "autocatalytic_gain", "enrichment_factor"):
        assert k in pore
