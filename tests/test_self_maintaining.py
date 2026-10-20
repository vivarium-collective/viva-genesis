"""og-self-maintaining-individual: the reciprocal-maintenance loop.

Covers the no-built-in-gain construction (retention gated on the chemistry's actual
aggregation competence), the coupled A->synthesis composite, and the central result:
the chemistry's amphiphile pool does not clear CAC endogenously (no membrane without
assuming one), while the gate is NOT trivially always-zero (enough acetate does
earn a membrane) — so the refutation is a real concentration failure, not a rigged gate.
"""
from __future__ import annotations

import pytest

from process_bigraph import Composite, gather_emitter_results
from viva_genesis.core import build_core
from viva_genesis.composites.self_maintaining import (
    og_self_maintaining_individual, gated_retention, _EARNED_RETENTION,
)
from viva_genesis.membranes.amphiphile_chain_extension import AmphiphileChainExtensionProcess


def test_gated_retention_no_built_in_gain():
    # No membrane below CAC clearance; earned (og_32 long-chain) value only when competent.
    assert gated_retention(0.0) == 0.0
    assert gated_retention(0.5) == 0.0
    assert gated_retention(1.0) == pytest.approx(_EARNED_RETENTION)
    assert gated_retention(50.0) == pytest.approx(_EARNED_RETENTION)
    assert 0.0 < _EARNED_RETENTION < 1.0


def test_composite_registered():
    from process_bigraph.composite_generator import _REGISTRY
    import viva_genesis.composites  # noqa: F401
    assert "viva_genesis.composites.self_maintaining.og_self_maintaining_individual" in _REGISTRY


def test_canonical_loop_produces_acetate_but_no_membrane():
    core = build_core()
    sim = Composite({"state": og_self_maintaining_individual(core=core, feed_CO2=2.0e-3, k_wash_eff=0.05)}, core=core)
    sim.run(180.0)
    r = gather_emitter_results(sim)[("emitter",)][-1]
    assert r["acetate"] > 0.0                        # chemistry->membrane arrow carries signal
    assert r["aggregation_competent"] < 1.0          # but no membrane forms endogenously
    # so the gated retention is 0 — the loop cannot close without assuming the membrane
    assert gated_retention(r["aggregation_competent"]) == 0.0


def test_gate_is_not_trivially_zero():
    """Enough acetate DOES earn a membrane — the refutation is a real concentration
    shortfall, not a gate rigged to always fail."""
    core = build_core()
    ce = AmphiphileChainExtensionProcess(config={}, core=core)
    st = ce.initial_state(); st["acetate"] = 1.0e-3; st["temperature"] = 330.0
    last = {}
    for _ in range(240):
        last = ce.update(st, 1.0)
    assert last["aggregation_competent"] >= 1.0
    assert gated_retention(last["aggregation_competent"]) > 0.0


def test_built_in_gain_does_not_create_a_real_membrane():
    """Forcing retention to the earned value (the built-in gain) does NOT make the
    amphiphile pool clear CAC — aggregation_competent is independent of the assumed
    retention, so a 'closure' under the gain is assumed-only (the false closure)."""
    core = build_core()
    # low acetate -> not competent regardless of any downstream retention assumption
    ce = AmphiphileChainExtensionProcess(config={}, core=core)
    st = ce.initial_state(); st["acetate"] = 1.0e-9; st["temperature"] = 330.0
    last = {}
    for _ in range(240):
        last = ce.update(st, 1.0)
    assert last["aggregation_competent"] < 1.0   # membrane not real even if retention is assumed
