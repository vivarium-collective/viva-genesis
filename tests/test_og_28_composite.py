"""Study-28 composite: the Prebiotic Reaction Atlas build + zero-leakage gate."""
from process_bigraph import Composite, gather_emitter_results

from viva_genesis.core import build_core
from viva_genesis.composites.og_28_prebiotic_reaction_atlas import (
    og_28_prebiotic_reaction_atlas as og28,
)


def test_generator_is_registered():
    from process_bigraph.composite_generator import _REGISTRY
    assert any(eid.endswith(".og_28_prebiotic_reaction_atlas") for eid in _REGISTRY)


def test_process_is_registered():
    assert "ReactionAtlasBuildProcess" in build_core().link_registry


def test_build_run_reports_coverage_and_zero_leakage():
    core = build_core()
    sim = Composite({"state": og28(core)}, core=core)
    sim.run(1.0)
    rows = gather_emitter_results(sim)[("emitter",)]
    assert rows
    last = rows[-1]
    # The two balanced measured reactions enter the atlas; the unbalanced one is held.
    assert last["n_accepted"] == 2.0
    assert last["n_measured"] == 2.0
    assert last["balance_violations_held"] >= 1.0   # unbalanced candidate kept OUT
    # The zero-leakage guarantee: nothing unbalanced ever reaches the accepted atlas.
    assert last["accepted_balance_violations"] == 0.0
    # Carbon coverage: CO2 + formate + acetate present in the accepted set.
    assert last["carbon_species_covered"] >= 3.0
