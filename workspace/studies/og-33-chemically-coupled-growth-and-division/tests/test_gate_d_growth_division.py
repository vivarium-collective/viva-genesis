"""Behavior tests for og-33 Gate D first half (growth & division, Option B).

Assertions against the committed artifact (``artifacts/gate_d_growth_division.json``
from ``sims/compute_gate_d_growth_division.py``). Back the study's findings: growth
from metabolism (division rate scales with flux) vs a flux-independent decoupled null,
division at a measured area-doubling geometry (not imposed), viable daughters, and the
qualified verdict.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ART = Path(__file__).resolve().parents[1] / "artifacts" / "gate_d_growth_division.json"


@pytest.fixture(scope="module")
def art():
    if not ART.exists():
        pytest.skip(f"{ART.name} not found — run sims/compute_gate_d_growth_division.py")
    return json.loads(ART.read_text())


def test_growth_from_metabolism_division_rate_scales_with_flux(art):
    """Coupled division rate rises with metabolic flux (slope > 0); the matched
    growth-decoupled null is flux-independent (slope ~ 0)."""
    assert art["criteria"]["growth_from_metabolism"] is True
    assert art["coupled_slope"] > 0
    c = art["coupled"]
    assert c[-1]["division_rate"] > c[0]["division_rate"]          # rate rises with flux
    d = art["decoupled"]
    assert d[0]["division_rate"] == pytest.approx(d[-1]["division_rate"], rel=1e-6)  # flat


def test_division_at_measured_geometry_not_imposed(art):
    """Division triggers at the measured area-doubling budding geometry (no imposed
    event) in the coupled/decoupled arms; the imposed-division arm is a timer null."""
    assert art["criteria"]["division_at_geometry"] is True
    assert "area-doubling" in art["meta"]["division_geometry"].lower()
    assert all(r["division_count"] >= 1 for r in art["coupled"])


def test_daughters_viable(art):
    """Daughters resume the study-32 self-maintenance criterion across the sweep."""
    assert art["criteria"]["daughters_viable"] is True
    assert all(r["daughter_viable"] >= 1.0 for r in art["coupled"])


def test_beats_matched_nulls(art):
    """At the top feed the metabolism-coupled arm exceeds the flux-independent
    decoupled null — growth/division is a margin over the matched null."""
    assert art["criteria"]["beats_null"] is True
    assert art["coupled"][-1]["division_rate"] > art["decoupled"][-1]["division_rate"]


def test_verdict_qualified(art):
    assert art["verdict"] == "qualified"


def test_scope_measured_geometry_not_cg_mechanics(art):
    """Labelled measured-geometry first cut (Option B), NOT CG membrane mechanics
    (Option A / og-33a)."""
    coupling = art["meta"]["coupling"].lower()
    assert "not cg membrane mechanics" in coupling or "og-33a" in coupling
