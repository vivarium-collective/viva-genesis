"""The Phase-1 posterior figure renders from the committed ensemble artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_ART = Path(__file__).resolve().parents[1] / "workspace" / "studies" / "og-vent-environment" / "artifacts" / "og-cal-vent-environment"


def test_vent_environment_posterior_figure_renders():
    if not (_ART / "vent_environment_report.json").exists():
        pytest.skip("og-cal-vent-environment artifacts not present on this branch")
    from viva_genesis.viz_uq import vent_environment_posterior_figure
    ens = json.loads((_ART / "vent_environment_ensemble.json").read_text())
    rep = json.loads((_ART / "vent_environment_report.json").read_text())
    html = vent_environment_posterior_figure(ens, rep, title="t")
    assert "plotly" in html, "figure should embed a Plotly chart"
    assert "posterior" in html, "headline frames the Lost-City-conditioned posterior"
    assert "not an origin-of-life claim" in html, "caption keeps the no-origin-claim honesty"


def test_visualization_class_registered():
    from viva_genesis.core import build_core
    assert "VentEnvironmentPosterior" in build_core().link_registry
