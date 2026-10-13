"""og-08 Campaign-VIII real model: off-gradient persistence + the minimum innovation set.

Deterministic co-limited free-energy + resource budget (no RNG, no heavy deps) — runs
everywhere and is reproducible.
"""
from __future__ import annotations

from process_bigraph import Composite, gather_emitter_results
from viva_genesis.core import build_core

GEN_ID = "viva_genesis.composites.off_gradient_persistence.off_gradient_persistence"


def test_processes_and_generator_registered():
    reg = build_core().link_registry
    assert "OffGradientPersistenceProcess" in reg
    assert "EnvironmentalRelaxationProcess" in reg
    from process_bigraph.composite_generator import _REGISTRY
    assert GEN_ID in _REGISTRY, f"{GEN_ID} missing; have {[i for i in _REGISTRY if 'genesis' in i]}"


def _run(n=60, **kw):
    from viva_genesis.composites.off_gradient_persistence import off_gradient_persistence
    core = build_core()
    sim = Composite({"state": off_gradient_persistence(core=core, **kw)}, core=core)
    sim.run(float(n))
    return gather_emitter_results(sim)[("emitter",)]


def test_full_set_persists_off_gradient():
    """The full innovation set (pump + importer + heredity) persists as geological
    support is withdrawn (survivors ~1 at support -> 0)."""
    rows = _run()
    assert rows[0]["survivors"] == 1.0
    assert rows[-1]["gradient_support"] < 1e-6        # support fully withdrawn
    assert rows[-1]["survivors"] >= 0.5               # persists off-gradient
    assert rows[-1]["lineage_fitness"] > 0.0          # net-positive budget off-gradient


def test_each_innovation_is_necessary():
    """The budget is co-limited, so the set is irreducible: removing ANY single
    innovation collapses off-gradient persistence (the minimum robust set is all three)."""
    full = _run()[-1]["survivors"]
    assert full >= 0.5
    for kw in ({"has_pump": 0}, {"has_importer": 0}, {"has_heredity": 0}):
        rows = _run(**kw)
        assert rows[-1]["survivors"] < 0.1, f"knockout {kw} should collapse off-gradient"
        # discriminating: the full set persists where each knockout does not
        assert full > rows[-1]["survivors"] + 0.4


def test_heredity_loss_degrades_machinery():
    """Without heredity the adaptive machinery degrades over the run (error
    catastrophe), so the pump/importer cannot be held and persistence collapses."""
    rows = _run(has_heredity=0)
    assert rows[0]["machinery_integrity"] > 0.9
    assert rows[-1]["machinery_integrity"] < 0.1      # machinery lost
    assert rows[-1]["survivors"] < 0.1


def test_survival_frontier_monotone_in_support():
    """The off-gradient lineage model: the full set's survival frontier reaches
    support -> 0, while each knockout requires strictly more support (is lifted off
    the gradient)."""
    from viva_genesis.phase_maps import off_gradient_phase_map
    res = off_gradient_phase_map(support=(0.0, 1.0, 16), n_steps=60)
    fr = res.meta["frontier"]
    assert fr["full"] == 0.0
    for ko in ("-pump", "-importer", "-heredity"):
        assert fr[ko] is not None and fr[ko] > 0.0
