"""og-03 Campaign-III real model: FiPy thermophoretic thermal trap (Baaske).

Guarded with importorskip so CI without fipy skips (not fails).
"""
from __future__ import annotations

import pytest

from process_bigraph import Composite, gather_emitter_results
from viva_genesis.core import build_core

GEN_ID = "viva_genesis.composites.thermophoretic_concentration.thermophoretic_concentration"


def test_process_and_generator_registered():
    reg = build_core().link_registry
    assert "ThermophoreticTrapProcess" in reg
    from process_bigraph.composite_generator import _REGISTRY
    assert GEN_ID in _REGISTRY, f"{GEN_ID} missing; have {[i for i in _REGISTRY if 'genesis' in i]}"


def _run(n=20, **kw):
    pytest.importorskip("fipy")
    from viva_genesis.composites.thermophoretic_concentration import thermophoretic_concentration
    core = build_core()
    sim = Composite({"state": thermophoretic_concentration(core=core, **kw)}, core=core)
    for _ in range(n):
        sim.run(1)
    return gather_emitter_results(sim)[("emitter",)][-1]


def test_favorable_trap_reproduces_baaske_enrichment():
    """A favorable pore (5 mm × 0.1 mm, ΔT 30 K, convective flow) reproduces
    Baaske-2007 extreme accumulation: >10^8-fold (accumulation Péclet ≳ 18)."""
    r = _run()
    assert r["accumulation_peclet"] >= 18.0            # ln(1e8) ≈ 18.4
    assert r["enrichment_factor"] > 1.0e7
    assert r["flux_divergence_residual"] <= 1e-2       # FVM conserves (Pe_acc low grid)


def test_open_pore_control_does_not_concentrate():
    """An open pore (porosity → 1) lets the feed wash through — no individual."""
    r = _run(porosity=1.0)
    assert r["enrichment_factor"] < 10.0               # essentially no accumulation


def test_shorter_pore_enriches_less():
    """Enrichment is exponential in pore length — a 10× shorter pore enriches far
    less (the geometry threshold Baaske identified)."""
    long_pore = _run()
    short_pore = _run(pore_length=5.0e-4)
    assert short_pore["accumulation_peclet"] < long_pore["accumulation_peclet"]
    assert short_pore["enrichment_factor"] < long_pore["enrichment_factor"] / 100.0
