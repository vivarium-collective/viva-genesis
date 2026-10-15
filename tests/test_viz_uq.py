"""The Phase-1 posterior figure renders from the committed ensemble artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_ART = Path(__file__).resolve().parents[1] / "workspace" / "studies" / "og-cal-vent-environment" / "artifacts"


def test_vent_environment_posterior_figure_renders():
    if not (_ART / "vent_environment_report.json").exists():
        pytest.skip("og-cal-vent-environment artifacts not present on this branch")
    from viva_genesis.viz_uq import vent_environment_posterior_figure
    ens = json.loads((_ART / "vent_environment_ensemble.json").read_text())
    rep = json.loads((_ART / "vent_environment_report.json").read_text())
    html = vent_environment_posterior_figure(ens, rep, title="t")
    assert "plotly" in html and "feasible=" in html


def test_visualization_class_registered():
    from viva_genesis.core import build_core
    assert "VentEnvironmentPosterior" in build_core().link_registry
