"""Behavior tests for og-08-alt's per-driver one-at-a-time withdrawal rebuild.

Assertions against the committed artifact (``artifacts/per_driver_withdrawal.json`` from
``sims/compute_per_driver_withdrawal.py``). Back the rebuild finding: withdrawing each
geological driver ALONE (the other two held at full) yields a DIFFERENTIAL per-driver
survivability that the original lumped all-at-once withdrawal could not attribute — the
vent pmf gradient is an irreducible dependency (no innovation subset rescues its
withdrawal), while mineral access / feed are differentially survivable. Resolves the
attribution confound; verdict qualified.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ART = Path(__file__).resolve().parents[1] / "artifacts" / "per_driver_withdrawal.json"
DRIVERS = ("gradient", "mineral", "feed")


@pytest.fixture(scope="module")
def art():
    if not ART.exists():
        pytest.skip(f"{ART.name} not found — run sims/compute_per_driver_withdrawal.py")
    return json.loads(ART.read_text())


def test_all_three_drivers_withdrawn_separately(art):
    """Each of the three geological drivers is withdrawn one at a time (characterised on
    its own), which the lumped all-at-once run could not do."""
    pd = art["per_driver"]
    for d in DRIVERS:
        assert d in pd
        assert pd[d]["full_set_persistence_fraction"] is not None


def test_confound_resolved_differential_survivability(art):
    """The confound is resolved: the per-driver full-set persistence fractions DIFFER, so
    each driver's withdrawal is attributed separately (not a single lumped collapse)."""
    assert art["criteria"]["confound_resolved"] is True
    assert art["criteria"]["differential_survivability"] is True
    fracs = [art["full_set_persistence_fraction_by_driver"][d] for d in DRIVERS]
    assert max(fracs) - min(fracs) > 0.01


def test_gradient_is_hard_dependency(art):
    """The vent pmf gradient is the hard dependency — the full innovation set rescues its
    withdrawal in only a small fraction of structures (<=10%), consistent with study 37's
    budget-sensitive gradient."""
    assert "gradient" in art["hard_dependencies"]
    assert art["survivability_by_driver"]["gradient"] == "hard_dependency"
    assert art["full_set_persistence_fraction_by_driver"]["gradient"] <= 0.10


def test_other_drivers_more_survivable_than_gradient(art):
    """Mineral and feed withdrawal are more survivable than gradient withdrawal — the
    differential that establishes per-driver attribution."""
    g = art["full_set_persistence_fraction_by_driver"]["gradient"]
    assert art["full_set_persistence_fraction_by_driver"]["mineral"] > g
    assert art["full_set_persistence_fraction_by_driver"]["feed"] >= g


def test_verdict_qualified(art):
    assert art["verdict"] == "qualified"
    assert art["resolution"] == "confound_resolved_per_driver_attribution"


def test_method_is_per_driver_one_at_a_time(art):
    """Labelled: one-at-a-time per-driver withdrawal (floor config, others held full),
    the rich-world analogue of study 37 — not the original lumped all-at-once."""
    m = art["meta"]
    assert "one-at-a-time" in m["method"].lower()
    assert m["held_support"] == 1.0
    assert set(m["drivers"]) == set(DRIVERS)
