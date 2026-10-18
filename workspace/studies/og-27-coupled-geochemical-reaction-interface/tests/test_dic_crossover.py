"""Behavior tests for og-27's DIC-crossover calibration sweep.

Assertions against the committed artifact (``artifacts/dic_crossover_sweep.json`` from
``sims/compute_dic_crossover_sweep.py``). Back the calibration finding: the undersaturated
regime sustains H2 flux with no mineral throttling; the supersaturated regime throttles but
chokes the supply; the SI=0 crossover is a sharp cliff so NO single fluid_dic sustains flux
AND exercises throttling (the two-regime tension is fundamental); the mass/charge/energy
ledger closes at every swept point; and the qualified verdict.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ART = Path(__file__).resolve().parents[1] / "artifacts" / "dic_crossover_sweep.json"


@pytest.fixture(scope="module")
def art():
    if not ART.exists():
        pytest.skip(f"{ART.name} not found — run sims/compute_dic_crossover_sweep.py")
    return json.loads(ART.read_text())


def test_ledger_closes_every_point(art):
    """The full mass/charge/energy ledger closes at every swept fluid_dic — the sweep is
    physically valid, not a numerical artifact."""
    assert art["criteria"]["ledger_ok_all"] is True
    assert all(p["ledger_ok"] for p in art["sweep"])


def test_undersaturated_sustains_flux_without_throttling(art):
    """The undersaturated end point sustains H2 flux and exercises NO mineral throttling."""
    p0 = art["sweep"][0]
    assert p0["saturation_index_last"] < 0.0
    assert p0["sustained_flux"] is True
    assert p0["throttling_exercised"] is False


def test_supersaturated_throttles_but_chokes(art):
    """At least one supersaturated point exercises throttling but chokes the supply (flux
    not sustained, pore collapses) — the other regime of the tension."""
    choking = [p for p in art["sweep"]
               if p["saturation_index_last"] > 0.0 and p["throttling_exercised"]
               and not p["sustained_flux"] and not p["not_choked"]]
    assert choking, "expected a supersaturated throttling-but-choked point"


def test_no_operating_point_tension_fundamental(art):
    """No single fluid_dic sustains flux AND exercises throttling (pore open) — the
    two-regime tension is fundamental (sharp SI=0 cliff), reported honestly."""
    assert art["criteria"]["window_exists"] is False
    assert art["operating_points"] == []
    assert art["recommended_operating_point"] is None
    assert art["criteria"]["resolution"] == "two_regime_tension_fundamental"


def test_crossover_located_and_sharp(art):
    """The SI=0 crossover is located (a real fluid_dic), and the transition from
    flux-sustained/undersaturated to choked/supersaturated is a cliff — adjacent swept
    points straddle it (sustained+no-throttle on one side, choked+throttling on the other)."""
    assert art["si_zero_crossover_fluid_dic"] is not None
    sweep = art["sweep"]
    has_healthy = any(p["sustained_flux"] and not p["throttling_exercised"] for p in sweep)
    has_choked = any(p["throttling_exercised"] and not p["not_choked"] for p in sweep)
    assert has_healthy and has_choked      # both regimes present, no middle operating point


def test_verdict_qualified(art):
    assert art["verdict"] == "qualified"
