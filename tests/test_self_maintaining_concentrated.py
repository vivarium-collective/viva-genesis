"""og-self-maintaining-concentrated: does spatial concentration close the loop?

The reciprocal-maintenance refutation (og-self-maintaining-individual) left the
amphiphile pool 4-7 orders below CAC. This connected composite couples the real
FiPy Baaske thermophoretic trap (the supported og-spatial-concentration mechanism)
to that loop and asks whether the pore closes the gap — with the matched
non-concentrating control as the no-built-in-gain witness.
"""
from __future__ import annotations

from process_bigraph import Composite, gather_emitter_results

from viva_genesis.core import build_core
from viva_genesis.composites.self_maintaining_concentrated import og_self_maintaining_concentrated


def _run(**kw):
    core = build_core()
    sim = Composite({"state": og_self_maintaining_concentrated(core=core, **kw)}, core=core)
    sim.run(240.0)
    return gather_emitter_results(sim)[("emitter",)][-1]


def test_composite_registered():
    from process_bigraph.composite_generator import _REGISTRY
    import viva_genesis.composites  # noqa: F401
    assert ("viva_genesis.composites.self_maintaining_concentrated.og_self_maintaining_concentrated"
            in _REGISTRY)


def test_control_reproduces_the_refutation():
    """With concentration off, the chemistry's amphiphile pool stays far below CAC
    — the refuted shortfall, reproduced inside the connected composite."""
    r = _run(concentrating=False)
    assert r["aggregation_competent_base"] < 1.0
    assert r["effective_enrichment"] == 1.0
    assert r["aggregation_competent_concentrated"] < 1.0


def test_favorable_trap_closes_the_loop_spatially():
    """Strong amphiphile self-association (Soret 0.10) + a warm cross-pore gradient
    (dT 30 K, 5 mm column) drives the Baaske trap to ~10^8-fold enrichment, which
    clears CAC — the loop closes via spatial concentration, not an assumed membrane."""
    r = _run(concentrating=True, soret_coeff=0.10, delta_T=30.0)
    assert r["enrichment_factor"] > 1.0e6
    assert r["aggregation_competent_concentrated"] >= 1.0


def test_matched_control_does_not_close_at_the_same_geometry():
    """No-built-in-gain witness: at the SAME geometry that closes when concentrating,
    the non-concentrating control (enrichment forced to 1) stays sub-CAC — the pore,
    not an assumed membrane, is the discriminating mechanism."""
    r = _run(concentrating=False, soret_coeff=0.10, delta_T=30.0)
    assert r["effective_enrichment"] == 1.0
    assert r["aggregation_competent_concentrated"] < 1.0


def test_conservative_soret_leaves_a_shortfall():
    """The closure is conditional, not automatic: a conservative amphiphile Soret
    (0.05) at dT 30 K does NOT clear CAC — the refutation holds unless self-
    association is strong enough. This pins the load-bearing uncertainty."""
    r = _run(concentrating=True, soret_coeff=0.05, delta_T=30.0)
    assert r["aggregation_competent_concentrated"] < 1.0
