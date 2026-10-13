"""og-06 Campaign-VI real model: quasispecies heredity replicator (Eigen error threshold).

Guarded with importorskip so CI without tellurium/libroadrunner skips (not fails).
"""
from __future__ import annotations

import pytest

from process_bigraph import Composite, gather_emitter_results
from viva_genesis.core import build_core

GEN_ID = "viva_genesis.composites.heredity_module_comparison.heredity_module_comparison"


def test_process_and_generator_registered():
    reg = build_core().link_registry
    assert "HeredityReplicatorProcess" in reg
    from process_bigraph.composite_generator import _REGISTRY
    assert GEN_ID in _REGISTRY, f"{GEN_ID} missing; have {[i for i in _REGISTRY if 'genesis' in i]}"


def _run(module="rna-like", n=50):
    pytest.importorskip("tellurium")
    from viva_genesis.composites.heredity_module_comparison import heredity_module_comparison
    core = build_core()
    sim = Composite({"state": heredity_module_comparison(core=core, module=module)}, core=core)
    for _ in range(n):
        sim.run(1)
    return gather_emitter_results(sim)[("emitter",)][-1]


def test_inheritance_beats_non_inheritance():
    """A high-fidelity heredity module retains functional information and outscores
    the non-heritable control (whose function degrades away)."""
    rna = _run("rna-like")
    none = _run("non-heritable")
    assert rna["information_retention"] > 0.4
    assert rna["lineage_fitness"] > 0.1
    assert rna["lineage_fitness"] > none["lineage_fitness"] + 0.1


def test_heredity_modules_ranked_head_to_head():
    """Two viable modules are compared; RNA-like (long, high-fidelity) outscores the
    cheaper, lower-fidelity peptide module — an evidence-based ranking."""
    rna, pep = _run("rna-like"), _run("peptide")
    assert rna["lineage_fitness"] > 0.0 and pep["lineage_fitness"] > 0.0   # both viable
    assert rna["lineage_fitness"] > pep["lineage_fitness"]                 # RNA wins
    assert pep["polymer_length"] < rna["polymer_length"]


def test_error_threshold_catastrophe():
    """Below the Eigen error threshold (low per-site fidelity × long sequence),
    functional information is lost — retention collapses and fitness goes negative."""
    low = _run("low-fidelity")
    assert low["information_retention"] < 0.1
    assert low["lineage_fitness"] < 0.0
