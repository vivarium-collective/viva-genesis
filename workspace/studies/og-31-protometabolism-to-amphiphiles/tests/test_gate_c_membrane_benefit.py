"""Behavior tests for og-31 partial Gate C (membrane pays for itself on persistence).

Assertions against the committed artifact
(``artifacts/gate_c_membrane_benefit.json``, from
``sims/compute_gate_c_membrane_benefit.py``). Back the study's findings:
persistence benefit, throughput-not-improved (expected physics), and the
windowed access boundary.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ARTIFACT = Path(__file__).resolve().parents[1] / "artifacts" / "gate_c_membrane_benefit.json"


@pytest.fixture(scope="module")
def art():
    if not ARTIFACT.exists():
        pytest.skip(f"{ARTIFACT.name} not found — run sims/compute_gate_c_membrane_benefit.py")
    return json.loads(ARTIFACT.read_text())


def test_membrane_pays_on_persistence(art):
    """Membrane raises the standing metabolite pool above the ablation
    (membrane-benefit-persistence)."""
    d = art["benefit_demo"]
    assert d["persistence_pays"] is True
    assert d["toc_benefit"] > 1.0
    assert d["membrane"]["total_organic_carbon"] > d["ablation"]["total_organic_carbon"]


def test_throughput_not_improved_expected(art):
    """Throughput (fixation flux) is NOT improved — the physically-expected,
    feed-limited null (membrane-benefit-throughput)."""
    d = art["benefit_demo"]
    assert d["throughput_pays"] is False
    assert d["flux_ratio"] < 1.0


def test_persistence_benefit_windowed(art):
    """The persistence benefit is a bounded access window with a located failure
    boundary (membrane-benefit-access-window)."""
    w = art["access_window"]
    boundary = w["persistence_benefit_access_boundary"]
    assert boundary is not None and 0.0 < boundary < 1.0
    sweep = w["sweep"]
    # at least one access pays and at least one (tighter) does not — a real window
    assert any(s["persistence_pays"] for s in sweep)
    assert any(not s["persistence_pays"] for s in sweep)
    # monotone: every access at/above the boundary pays; below, inverts
    for s in sweep:
        if s["access"] >= boundary:
            assert s["persistence_pays"] is True


def test_verdict_qualified(art):
    assert art["verdict"] == "qualified"
