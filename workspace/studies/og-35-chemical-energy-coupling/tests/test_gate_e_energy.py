"""Behavior tests for og-35 Gate E (chemical energy coupling).

Assertions against the committed artifact (``artifacts/gate_e_energy.json`` from
``sims/compute_gate_e_energy.py``). Back the study's findings: the carrier does work
through the gradient dip where gradient-only starves (persistence), the energy ledger
closes with no hidden inflow, total throughput is NOT improved (the honest
persistence-not-throughput result), and the qualified verdict.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ART = Path(__file__).resolve().parents[1] / "artifacts" / "gate_e_energy.json"


@pytest.fixture(scope="module")
def art():
    if not ART.exists():
        pytest.skip(f"{ART.name} not found — run sims/compute_gate_e_energy.py")
    return json.loads(ART.read_text())


def test_carrier_pays_on_dip_persistence(art):
    """The carrier does useful work through the gradient dip where the matched
    gradient-only control starves."""
    assert art["criteria"]["persistence_pays"] is True
    assert art["carrier_arm"]["dip_useful_work"] > art["gradient_only_arm"]["dip_useful_work"]


def test_energy_ledger_closes_no_hidden_inflow(art):
    """The full free-energy ledger closes in both arms (budget_residual ~ 0) — the
    benefit is real accounting, not a hidden source."""
    assert art["criteria"]["ledger_closes"] is True
    assert art["carrier_arm"]["max_budget_residual"] < 1e-6
    assert art["gradient_only_arm"]["max_budget_residual"] < 1e-6


def test_throughput_not_improved_expected(art):
    """Total useful work is NOT improved — the carrier time-shifts work into the dip
    (and leaks), so the honest result is persistence, not throughput."""
    assert art["criteria"]["throughput_pays"] is False
    assert art["carrier_arm"]["total_useful_work"] <= art["gradient_only_arm"]["total_useful_work"]


def test_cost_benefit_window_located(art):
    """The k_hydrolyze cost/benefit window is swept and reported (here the carrier does
    not beat gradient-only on total at any leak rate — pay_boundary is None)."""
    w = art["k_hydrolyze_window"]
    assert "sweep" in w and len(w["sweep"]) >= 3
    assert any(not b["pays_total"] for b in w["sweep"])     # a real boundary/limit is exercised


def test_verdict_qualified(art):
    assert art["verdict"] == "qualified"


def test_scope_thioester_not_acyl_phosphate(art):
    """Labelled Option B (one specified thioester carrier), NOT acyl-phosphate /
    microkinetic (Option A / og-35a)."""
    c = art["meta"]["carrier"].lower()
    assert "thioester" in c and "option b" in c
    assert "og-35a" in art["meta"]["scope"].lower()
