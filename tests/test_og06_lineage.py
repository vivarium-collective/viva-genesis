"""og-06 Campaign-VI deep model: agent-based heredity LINEAGE (phenotype tree).

The quasispecies ODE (test_og06_heredity_replicator) is mean-field — no individuals,
no ancestry. This model simulates individuals that divide into a real lineage tree,
each inheriting a chemical phenotype with a module-specific mechanism, and is the
basis for the Decision view (the Eigen error threshold re-derived at the agent level,
and compositional heredity escaping the length catastrophe). Pure numpy — no heavy
deps — so it runs everywhere.
"""
from __future__ import annotations

from process_bigraph import Composite, gather_emitter_results
from viva_genesis.core import build_core
from viva_genesis.heredity.lineage import simulate_lineage

GEN_ID = "viva_genesis.composites.heredity_lineage.heredity_lineage_comparison"
CAP = 220


def _persist(r):
    return r["final_function"] * min(r["final_population"] / CAP, 1.0)


def test_lineage_process_and_generator_registered():
    assert "LineageReplicatorProcess" in build_core().link_registry
    from process_bigraph.composite_generator import _REGISTRY
    assert GEN_ID in _REGISTRY


def test_lineage_produces_a_real_tree_with_heritability():
    """A heritable template lineage builds a multi-generation tree whose offspring
    track their parents (realized heritability near 1)."""
    r = simulate_lineage("template", per_site_fidelity=0.99, length=30, seed=1)
    assert r["n_nodes"] > 500                      # a real, branching lineage
    assert r["series"][-1]["lineage_depth"] >= 30  # many generations deep
    assert r["heritability"] > 0.8                 # offspring resemble parents


def test_non_heritable_control_breaks_heredity():
    """Severing inheritance destroys the parent-offspring correlation and collapses
    the lineage — the control that proves inheritance is doing the work."""
    heritable = simulate_lineage("template", per_site_fidelity=0.99, length=30, seed=1)
    control = simulate_lineage("non-heritable", length=30, seed=1)
    assert control["heritability"] < 0.3
    assert heritable["heritability"] - control["heritability"] > 0.5
    assert _persist(control) < _persist(heritable)


def test_template_error_catastrophe_at_length():
    """Eigen at the agent level: a long, LOW-fidelity template (Q = f^L tiny) loses
    functional persistence relative to the same length at high fidelity."""
    good = simulate_lineage("template", per_site_fidelity=0.99, length=30, seed=1)
    bad = simulate_lineage("template", per_site_fidelity=0.90, length=30, seed=1)
    assert _persist(good) > _persist(bad) + 0.2


def test_compositional_escapes_the_length_catastrophe():
    """Do NOT presume RNA: compositional (GARD) heredity persists — length-independent
    — above the non-heritable control, so heredity need not be a long high-fidelity
    template."""
    comp = simulate_lineage("compositional", capacity=CAP, seed=1)
    control = simulate_lineage("non-heritable", length=30, capacity=CAP, seed=1)
    assert _persist(comp) > 0.35
    assert comp["heritability"] > 0.5
    assert _persist(comp) > _persist(control)


def test_lineage_composite_runs_through_the_engine():
    """The composite runs through the real process-bigraph engine and emits the
    population summary each generation."""
    core = build_core()
    sim = Composite({"state": __import__(
        "viva_genesis.composites.heredity_lineage", fromlist=["heredity_lineage_comparison"]
    ).heredity_lineage_comparison(core=core, module="template", seed=1)}, core=core)
    sim.run(40.0)
    last = gather_emitter_results(sim)[("emitter",)][-1]
    assert last["population"] > 0
    assert 0.0 <= last["mean_function"] <= 1.0
    assert last["lineage_depth"] >= 30
