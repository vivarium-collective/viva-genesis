"""og-05 Campaign-V real model: bioenergetic internalization under selection (Sojo 2014).

Deterministic replicator dynamics (no heavy deps) — runs everywhere.
"""
from __future__ import annotations

from process_bigraph import Composite, gather_emitter_results
from viva_genesis.core import build_core

GEN_ID = "viva_genesis.composites.bioenergetic_internalization.bioenergetic_internalization"


def test_processes_and_generator_registered():
    reg = build_core().link_registry
    assert "BioenergeticSelectionProcess" in reg
    assert "EnvironmentalDeclineProcess" in reg
    from process_bigraph.composite_generator import _REGISTRY
    assert GEN_ID in _REGISTRY, f"{GEN_ID} missing; have {[i for i in _REGISTRY if 'genesis' in i]}"


def _run(n=40, **kw):
    from viva_genesis.composites.bioenergetic_internalization import bioenergetic_internalization
    core = build_core()
    sim = Composite({"state": bioenergetic_internalization(core=core, **kw)}, core=core)
    for _ in range(n):
        sim.run(1)
    return gather_emitter_results(sim)[("emitter",)]


def test_efficient_pump_internalizes_and_persists():
    """As the external gradient declines, an efficient-pump population internalizes
    gradient generation (pump fraction rises) and persists (survivors ~1)."""
    rows = _run()
    assert rows[0]["internalization"] < 0.2          # starts externally-driven
    assert rows[-1]["internalization"] > 0.6         # internalizes as the gradient falls
    assert rows[-1]["survivors"] > 0.5               # persists
    assert rows[-1]["lineage_fitness"] > 0.0         # net-positive energy flux


def test_weak_pump_collapses_when_gradient_falls():
    """A weak pump cannot internalize — when the external gradient collapses the
    lineage goes extinct (the Sojo leaky-membrane constraint)."""
    rows = _run(catalyst_efficiency=0.3)
    assert rows[-1]["internalization"] < 0.2
    assert rows[-1]["survivors"] < 0.1               # collapses

    # Discriminating: the efficient pump survives where the weak one does not.
    eff = _run()
    assert eff[-1]["survivors"] > rows[-1]["survivors"] + 0.5
