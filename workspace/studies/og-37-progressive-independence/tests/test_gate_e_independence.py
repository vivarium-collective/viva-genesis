"""Behavior tests for og-37 Gate E (progressive independence).

Assertions against the committed artifact (``artifacts/gate_e_independence.json`` from
``sims/compute_gate_e_independence.py``). Back the study's findings: reusing the
validated og-08 budget, each support channel withdrawn ONE AT A TIME is internalizable
with the full innovation set and is causally attributed to its rescuing innovation via a
matched ablation (which og-08's all-at-once relaxation cannot do); heredity is the
irreducible substrate; the gradient channel is budget-sensitive (flips below a pump
efficiency); and the honest caveats (lumped feed, coarse abstraction) + the qualified
verdict.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ART = Path(__file__).resolve().parents[1] / "artifacts" / "gate_e_independence.json"
CHANNELS = ["gradient", "mineral", "feed"]


@pytest.fixture(scope="module")
def art():
    if not ART.exists():
        pytest.skip(f"{ART.name} not found — run sims/compute_gate_e_independence.py")
    return json.loads(ART.read_text())


def test_all_channels_internalizable_with_full_set(art):
    """One-at-a-time, each of the 3 channels is internalizable with the full innovation set."""
    assert art["criteria"]["all_attributed"] is True
    for ch in CHANNELS:
        assert art["profile"][ch]["internalizable"] is True
        assert art["profile"][ch]["survivors_full"] >= art["meta"]["survive_threshold"]


def test_attribution_causal_via_ablation(art):
    """Each support is causally attributed to its rescuing innovation — switching that
    innovation off collapses the lineage (what og-08's joint relaxation cannot isolate)."""
    for ch in CHANNELS:
        p = art["profile"][ch]
        assert p["causal"] is True
        assert p["survivors_ablated"] < art["meta"]["survive_threshold"]
    assert art["profile"]["gradient"]["rescuing_innovation"] == "pump"
    assert art["profile"]["mineral"]["rescuing_innovation"] == "importer"
    assert art["profile"]["feed"]["rescuing_innovation"] == "importer"


def test_heredity_is_irreducible_substrate(art):
    """With heredity off the machinery degrades and every channel collapses — heredity is
    the non-internalizable substrate."""
    assert art["criteria"]["heredity_substrate"] is True
    for ch in CHANNELS:
        assert art["profile"][ch]["survivors_heredity_off"] < art["meta"]["survive_threshold"]


def test_all_at_once_is_the_confound(art):
    """og-08's all-at-once relaxation escapes with the full set but fails if ANY single
    innovation is removed — so it cannot attribute which innovation rescues which support."""
    c = art["all_at_once_confound"]
    assert c["escapes_with_full_set"] is True
    assert c["every_innovation_needed"] is True
    assert art["criteria"]["confound_shown"] is True


def test_gradient_is_budget_sensitive(art):
    """The gradient channel's internalization flips to a hard dependency below a pump
    efficiency (grounded in study-35's limited surplus) — the honest-bar sensitivity flag."""
    assert art["criteria"]["gradient_budget_sensitive"] is True
    sweep = art["pump_affordability_sweep"]["sweep"]
    assert any(not s["internalizable"] for s in sweep)   # flips within the plausible range
    assert any(s["internalizable"] for s in sweep)
    assert art["pump_affordability_sweep"]["boundary"] is not None


def test_margins_transparent_not_knife_edge(art):
    """Per-channel budget margins are reported and comfortably above the floor at nominal
    (transparent, not a knife-edge pass)."""
    for ch in CHANNELS:
        assert "budget_margin" in art["profile"][ch]
        assert art["profile"][ch]["budget_margin"] > 0.05


def test_honest_scope_labels(art):
    """Labelled: feed LUMPED (no per-feedstock resolution), coarse budget abstraction (not a
    demonstrated escape), og-08 reuse, og-37a follow-on."""
    m = art["meta"]
    assert "lump" in m["lumped_feed"].lower() and "og-37a" in m["lumped_feed"].lower()
    assert "og-37a" in m["scope"].lower()
    model = m["model"].lower()
    assert "og-08" in model and ("abstraction" in model or "not a" in model)


def test_verdict_qualified(art):
    assert art["verdict"] == "qualified"
