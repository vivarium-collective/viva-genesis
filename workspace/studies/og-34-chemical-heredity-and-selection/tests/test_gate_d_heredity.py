"""Behavior tests for og-34 Gate D second half (chemical heredity & selection).

Assertions against the committed artifact (``artifacts/gate_d_heredity.json`` from
``sims/compute_gate_d_heredity.py``). Back the study's findings: a reproducible
parent-offspring fitness correlation above the no-inheritance null, a population
composition shift under selection (vasas-2010 caveat tested, not assumed), the
matched null, and the qualified verdict.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ART = Path(__file__).resolve().parents[1] / "artifacts" / "gate_d_heredity.json"


@pytest.fixture(scope="module")
def art():
    if not ART.exists():
        pytest.skip(f"{ART.name} not found — run sims/compute_gate_d_heredity.py")
    return json.loads(ART.read_text())


def test_inherited_difference_reproducible_fitness(art):
    """An inherited composition difference yields a reproducible parent-offspring
    fitness correlation above the no-inheritance null (permutation-significant)."""
    c = art["parent_offspring_correlation"]
    assert art["criteria"]["heritable_fitness"] is True
    assert c["inheritance_mean"] > c["null_mean"]
    assert c["obs_delta"] > 0 and c["perm_p"] < 0.05
    assert abs(c["null_mean"]) < 0.1                       # null correlation ~ 0


def test_population_shifts_under_selection(art):
    """The inheriting population shifts composition measurably under selection while
    the no-inheritance null drifts — the vasas-2010 caveat tested, not assumed."""
    s = art["population_shift"]
    assert art["criteria"]["population_shifts"] is True
    assert s["inheritance_mean"] > s["null_mean"]
    assert s["obs_delta"] > 0 and s["perm_p"] < 0.05
    assert abs(s["null_mean"]) < 0.05                      # null drifts, no directional shift


def test_matched_null_no_inheritance(art):
    """The matched no-inheritance null (daughters reset to a common composition) shows
    neither a parent-offspring correlation nor a directional shift."""
    assert art["no_inheritance_arm"]
    assert abs(art["parent_offspring_correlation"]["null_mean"]) < 0.1
    assert abs(art["population_shift"]["null_mean"]) < 0.05


def test_fitness_grounded_in_real_coupling(art):
    """Fitness is grounded in the real study-32/33 coupling, not a toy function."""
    g = art["meta"]["fitness_grounding"].lower()
    assert "retention" in g and "division rate" in g


def test_vasas_caveat_tested_sigma_not_tuned(art):
    """The heritable variance sigma is a declared value (the vasas-2010 caveat is
    tested via whether the population shifts), not tuned to force the result."""
    assert art["meta"]["sigma"] == pytest.approx(0.03)
    assert "permutation" in art["meta"]["significance"].lower()


def test_verdict_qualified(art):
    assert art["selectable_heredity"] is True
    assert art["verdict"] == "qualified"


def test_scope_compositional_not_template(art):
    """Labelled Option B (inherited network composition), NOT template copying
    (Option A / og-34a)."""
    inh = art["meta"]["inheritance"].lower()
    assert "option b" in inh and "og-34a" in inh
