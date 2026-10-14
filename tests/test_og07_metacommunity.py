"""og-07 Campaign-VII model: cross-feeding metacommunity (ecology before LUCA).

A coarse-grained, deterministic (seeded) metacommunity over N connected pore
compartments, each a capability vector over a sparse protometabolic function set.
Pure numpy — no heavy deps — so it runs everywhere. Verifies the process/generator
register, that connectivity builds functional redundancy above the isolated
counterfactual, the robustness-emergence dependence on diversity, parasite drain, the
LUCA-overlap boundary, reproducibility, and the registered derived evaluators.
"""
from __future__ import annotations

from process_bigraph import Composite, gather_emitter_results
from viva_genesis.core import build_core

GEN_ID = "viva_genesis.composites.cross_feeding_metacommunity.cross_feeding_metacommunity"


def _run(core, n=40, **kw):
    from viva_genesis.composites.cross_feeding_metacommunity import cross_feeding_metacommunity
    sim = Composite({"state": cross_feeding_metacommunity(core=core, **kw)}, core=core)
    sim.run(float(n))
    return gather_emitter_results(sim)[("emitter",)]


def test_process_and_generator_registered():
    assert "CrossFeedingMetacommunityProcess" in build_core().link_registry
    from process_bigraph.composite_generator import _REGISTRY
    assert GEN_ID in _REGISTRY, f"{GEN_ID} missing; have {[i for i in _REGISTRY if 'genesis' in i]}"


def test_connectivity_builds_robustness_above_isolated():
    """A connected metacommunity develops functional redundancy (robustness) above the
    isolated counterfactual run on the identical seeded assignment — cross-feeding +
    HGT spread capabilities into >= R-fold coverage."""
    core = build_core()
    conn = _run(core, seed=1)[-1]
    iso = _run(core, seed=1, isolated=True)[-1]
    assert conn["metacommunity_robustness"] > iso["metacommunity_robustness"]
    assert conn["metacommunity_robustness"] > 0.5
    assert conn["robustness_gain"] > 0.0
    # The within-run isolated counterfactual matches the isolated arm (same assignment).
    assert abs(conn["isolated_robustness"] - iso["metacommunity_robustness"]) < 1e-9


def test_connected_beats_isolated_every_seed():
    """Seed-robust: connectivity (not the assignment) builds robustness on every seed."""
    core = build_core()
    for s in range(8):
        conn = _run(core, seed=s)[-1]
        iso = _run(core, seed=s, isolated=True)[-1]
        assert conn["metacommunity_robustness"] > iso["metacommunity_robustness"], f"seed {s}"


def test_low_diversity_has_nothing_to_share():
    """Robustness emergence needs diversity: near-identical compartments leave
    cross-feeding/HGT nothing to share, so robustness stays at the sparse floor even at
    high exchange — well below a diverse connected community."""
    core = build_core()
    low = _run(core, diversity=0.05, exchange_rate=0.8, seed=1)[-1]
    high = _run(core, diversity=0.9, exchange_rate=0.8, seed=1)[-1]
    assert low["metacommunity_robustness"] < 0.35
    assert high["metacommunity_robustness"] > low["metacommunity_robustness"] + 0.2


def test_parasite_load_erodes_robustness():
    """Parasites that drain their neighbours erode the community's functional
    redundancy — heavy parasite load collapses robustness below the cooperative run."""
    core = build_core()
    coop = _run(core, parasite_load=0.0, seed=1)[-1]
    heavy = _run(core, parasite_load=0.75, seed=1)[-1]
    assert heavy["metacommunity_robustness"] < coop["metacommunity_robustness"]


def test_luca_overlap_reported_as_bounded_fraction():
    """The LUCA-core overlap is a bounded fraction in [0,1] (a reported boundary, not a
    target): the collective repertoire overlaps the anaerobic core without being tuned
    to it."""
    core = build_core()
    r = _run(core, seed=1)[-1]
    assert 0.0 <= r["luca_capability_overlap"] <= 1.0
    assert r["luca_capability_overlap"] > 0.0


def test_deterministic_reproducible():
    """Same seed → identical settled robustness (seeded, deterministic)."""
    core = build_core()
    a = _run(core, seed=3)[-1]["metacommunity_robustness"]
    b = _run(core, seed=3)[-1]["metacommunity_robustness"]
    assert a == b


def test_derived_evaluators_registered():
    """The og-07 derived scalars are registered for the study evaluator."""
    from viva_genesis.evaluators import register_derived_scalars
    reg: dict = {}
    register_derived_scalars(reg)
    assert "metacommunity_robustness" in reg
    assert "luca_capability_overlap" in reg


def test_ecology_three_view_registered_and_renders():
    """The complete three-view (World network + Mechanism robustness-vs-connectivity +
    Decision robustness phase map) is registered and renders a Plotly figure."""
    reg = build_core().link_registry
    assert "EcologyMetacommunityThreeView" in reg
    from viva_genesis import phase_maps
    assert hasattr(phase_maps, "ecology_robustness_parasite_map")
    out = reg["EcologyMetacommunityThreeView"](
        config={"n_grid": 5, "n_steps": 20}, core=build_core()).update({})
    html = out["html"]
    assert isinstance(html, str) and "plotly" in html.lower() and len(html) > 5000
