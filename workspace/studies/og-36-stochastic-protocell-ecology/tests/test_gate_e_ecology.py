"""Behavior tests for og-36 Gate E (stochastic protocell ecology).

Assertions against the committed artifact (``artifacts/gate_e_ecology.json`` from
``sims/compute_gate_e_ecology.py``). Back the study's findings: a cross-feeding
community out-produces the BEST single lineage at equal feed (margin), the margin
is causally cross-feeding (knockout collapses it), coexistence is stabilised (not
assumed) by the byproduct pools, low-count stochastic dynamics materially change
the outcome versus the mean-field (the community is NOT more robust than a
monoculture — productivity, not robustness), and the qualified verdict.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ART = Path(__file__).resolve().parents[1] / "artifacts" / "gate_e_ecology.json"


@pytest.fixture(scope="module")
def art():
    if not ART.exists():
        pytest.skip(f"{ART.name} not found — run sims/compute_gate_e_ecology.py")
    return json.loads(ART.read_text())


def test_community_beats_best_single_lineage(art):
    """At equal feed, the SSA community out-produces the best single lineage — in the
    mean and in most seeds."""
    assert art["criteria"]["margin_positive"] is True
    s = art["stochastic"]
    assert s["community"]["mean"] > s["best_single"]["mean"]
    assert s["margin"] > 0
    assert s["frac_seeds_positive"] >= 0.5


def test_margin_causally_cross_feeding(art):
    """Knocking out cross-feeding (same feed) collapses the margin — the benefit is
    cross-feeding, not mere diversity."""
    assert art["criteria"]["cross_feeding_causal"] is True
    assert art["stochastic"]["ko_margin_fraction"] < 0.15


def test_coexistence_stabilized_not_assumed(art):
    """Deterministically all lineages coexist (byproduct-pool negative frequency
    dependence), and the knockout excludes down — coexistence is produced, not assumed."""
    det = art["deterministic"]
    k = art["meta"]["n_lineages"]
    assert det["community"]["n_alive"] == k
    assert det["knockout"]["n_alive"] < k


def test_stochastic_materially_changes_low_count(art):
    """Low-count stochastic dynamics materially differ from the mean-field, and the
    divergence (extinctions, margin erosion) GROWS as counts fall in the Omega sweep."""
    assert art["criteria"]["stochastic_material"] is True
    assert art["divergence_grows_at_low_counts"] is True
    assert art["stochastic"]["community"]["extinction_frac"] > 0.0
    sweep = art["omega_sweep"]
    assert len(sweep) >= 3
    low, high = sweep[0], sweep[-1]
    assert low["omega"] < high["omega"]
    assert low["extinction_frac"] >= high["extinction_frac"]
    assert low["rel_margin_gap"] >= high["rel_margin_gap"]


def test_community_not_more_robust_than_monoculture(art):
    """The honest result: the community is NOT more robust than the best single lineage
    — it is MORE variable under demographic noise (productivity, not robustness)."""
    assert art["criteria"]["community_more_robust"] is False
    assert art["stochastic"]["community"]["cv"] > art["stochastic"]["best_single"]["cv"]


def test_verdict_qualified(art):
    assert art["verdict"] == "qualified"


def test_scope_option_b_not_gillespy(art):
    """Labelled Option B (dependency-free SSA), NOT GillesPy2/COBRApy (Option A / og-36a)."""
    model = art["meta"]["model"].lower()
    assert "option b" in model and "ssa" in model
    assert "og-36a" in art["meta"]["scope"].lower()
    assert "equal" in art["meta"]["equal_feed"].lower()
