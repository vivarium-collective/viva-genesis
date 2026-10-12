"""og-04 Campaign-IV real model: coarse-grained mixed-amphiphile protocells (Jordan 2019).

Pure physico-chemical model (no heavy deps) — runs everywhere.
"""
from __future__ import annotations

from process_bigraph import Composite, gather_emitter_results
from viva_genesis.core import build_core

GEN_ID = "viva_genesis.composites.mixed_amphiphile_protocell.mixed_amphiphile_protocell"


def test_process_and_generator_registered():
    reg = build_core().link_registry
    assert "ProtocellAssemblyProcess" in reg
    from process_bigraph.composite_generator import _REGISTRY
    assert GEN_ID in _REGISTRY, f"{GEN_ID} missing; have {[i for i in _REGISTRY if 'genesis' in i]}"


def _run(n=10, **kw):
    from viva_genesis.composites.mixed_amphiphile_protocell import mixed_amphiphile_protocell
    core = build_core()
    sim = Composite({"state": mixed_amphiphile_protocell(core=core, **kw)}, core=core)
    for _ in range(n):
        sim.run(1)
    return gather_emitter_results(sim)[("emitter",)][-1]


def test_mixed_amphiphiles_form_vesicles_in_window():
    """Favorable (mixed amphiphiles, alkaline vent pH, seawater salt) forms viable
    vesicles that retain chemistry AND keep gradient access (Jordan 2019)."""
    r = _run()
    assert r["viable_compartments"] > 0
    assert r["individuality_access"] > 0.3        # retention × access both nonzero
    assert 0.0 < r["retention"] <= 1.0
    assert 0.0 < r["access"] <= 1.0


def test_single_fatty_acid_fails_on_salt():
    """A single fatty acid (mix_fraction ≈ 0) has a narrower window and does NOT
    tolerate seawater salt — no vesicles (the Jordan mixed-amphiphile advantage)."""
    r = _run(mix_fraction=0.001)
    assert r["viable_compartments"] == 0
    assert r["individuality_access"] == 0.0


def test_extreme_salt_and_acidic_controls_abolish_vesicles():
    assert _run(ionic_strength=1.5)["viable_compartments"] == 0       # salt disrupts
    assert _run(pH=4.0)["viable_compartments"] == 0                   # far from pKa
