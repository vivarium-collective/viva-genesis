"""Behavior tests for og-30 Gate B (concentration-rescues-ignition).

Assertions against the committed discriminator artifact
(``artifacts/gate_b_spatial.json``, produced by
``sims/compute_gate_b_spatial.py --c6-confirm``). They back the study's
findings: pore ignites vs matched control, the bounded (not-broad) porosity
window, the C6 confirmation, and A1 feed-plausibility resolution.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ARTIFACT = Path(__file__).resolve().parents[1] / "artifacts" / "gate_b_spatial.json"


@pytest.fixture(scope="module")
def art():
    if not ARTIFACT.exists():
        pytest.skip(f"{ARTIFACT.name} not found — run sims/compute_gate_b_spatial.py --c6-confirm")
    return json.loads(ARTIFACT.read_text())


def test_pore_ignites_where_wellmixed_control_does_not(art):
    """At equal vent-posterior feed, the concentrating pore ignites; the matched
    well-mixed control does not (pore-vs-wellmixed-ignition)."""
    demo = art["ignition_demo"]
    assert demo["rescued"] is True
    assert demo["feeds_held_equal"] is True
    assert demo["pore"]["connected_ignited"] is True
    assert demo["pore"]["net_carbon_flux"] > 1e-6
    assert demo["control"]["connected_ignited"] is False


def test_ignition_window_bounded_not_broad(art):
    """Connected-ignition occupies a bounded porosity band; net flux is monotone
    in enrichment while network_connected is brittle (bounded window, not broad)."""
    pm = art["porosity_map"]
    window = pm["ignited_physical_window_porosity"]
    assert window, "there must be at least one ignited+physical porosity"
    # bounded: not every swept porosity ignites-physical (sub-threshold below, implausible above)
    assert len(window) < len(pm["sweep"])
    assert pm["flux_monotone_in_enrichment"] is True
    assert pm["network_connected_brittle"] is True


def test_c6_confirmation(art):
    """The C6 network ignites in the demo pore and the C6 control stays dead
    (c6-pore-control-confirmation); the tight pore shows connectivity degradation,
    not flux loss (no flux-washout upper bound)."""
    c6 = art["c6_confirm"]
    assert c6 is not None, "run with --c6-confirm"
    assert c6["pore_demo"]["connected_ignited"] is True
    assert c6["pore_demo"]["net_carbon_flux"] > 1e-6
    assert c6["control"]["connected_ignited"] is False
    # tight pore: high flux but not connected (brittle metric), feed physically implausible
    assert c6["pore_tight"]["net_carbon_flux"] > c6["pore_demo"]["net_carbon_flux"]
    assert c6["pore_tight"]["connected_ignited"] is False
    assert c6["pore_tight"]["physical_feed"] is False


def test_gate_b_met_and_a1_resolved(art):
    """Gate B verdict supported; A1 feed-plausibility resolved in a pore."""
    assert art["verdict"] == "supported"
    assert "firms up" in art["a1_resolution"]
