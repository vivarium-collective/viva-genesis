"""NEW B — og-operating-window: the honest rescue test for A's thin precursor pool.

Covers the real pore (FiPy Soret trap) + membrane (ProtocellAssembly retention)
coupling onto A's reactor: enrichment is real (>1 with a gradient, ~1 without),
membrane retention is viable, and under DEFENSIBLE small-molecule Soret the
enriched+retained pool stays sub-consumable (the refuted rescue) while a
large-biomolecule Soret does cross it (so the model is not trivially always-fail).
"""
from __future__ import annotations

import pytest

from process_bigraph import Composite, gather_emitter_results
from viva_genesis.core import build_core
from viva_genesis.composites import operating_window as OW

CONSUMABLE = 1.0e-6


def _run(core, **kw):
    sim = Composite({"state": OW.og_operating_window(core=core, **kw)}, core=core)
    sim.run(120.0)
    r = gather_emitter_results(sim)[("emitter",)][-1]
    return r, r["functional_pool_carbon"] * r["enrichment_factor"]


def test_generator_registered():
    from process_bigraph.composite_generator import _REGISTRY
    import viva_genesis.composites  # noqa: F401
    assert "viva_genesis.composites.operating_window.og_operating_window" in _REGISTRY


def test_membrane_retention_real_and_viable():
    core = build_core()
    retention, access, indiv = OW.membrane_retention(core)
    assert 0.5 <= retention <= 0.99      # chemistry held
    assert access > 0.0                  # still permeable
    assert indiv > 0.0                   # individuality without isolation


def test_trap_enrichment_real_with_gradient_and_collapses_without():
    core = build_core()
    r_grad, _ = _run(core, soret_coeff=1.0e-2, delta_T=30.0)
    assert r_grad["enrichment_factor"] > 1.0          # real trap enriches
    r_flat, _ = _run(core, soret_coeff=1.0e-2, delta_T=1.0e-6)
    assert r_flat["enrichment_factor"] == pytest.approx(1.0, abs=1e-6)  # no-gradient control


def test_defensible_soret_does_not_rescue():
    """Under defensible small-molecule Soret the enriched+retained pool stays below
    the consumable threshold — the refuted rescue."""
    core = build_core()
    for S in (1.0e-3, 1.0e-2):
        r, enriched = _run(core, soret_coeff=S, delta_T=30.0, feed_CO2=2.0e-3, membrane=True)
        assert enriched < CONSUMABLE, f"S_T={S} unexpectedly rescued ({enriched:.2e} M)"


def test_large_biomolecule_soret_crosses_threshold():
    """Sanity: the model is NOT trivially always-fail — at the (non-defensible)
    large-biomolecule Soret the window does open, which is exactly why S_T is the
    pivotal discriminating quantity."""
    core = build_core()
    _, enriched = _run(core, soret_coeff=1.0e-1, delta_T=30.0, feed_CO2=2.0e-3, membrane=True)
    assert enriched >= CONSUMABLE


def test_membrane_off_null_has_no_retention():
    core = build_core()
    r, _ = _run(core, soret_coeff=1.0e-2, membrane=False)
    assert r["retention"] == pytest.approx(0.0, abs=1e-9)


def test_both_levers_exceed_each_single_regime():
    core = build_core()
    _, both = _run(core, soret_coeff=5.0e-3, delta_T=30.0, feed_CO2=2.0e-3, membrane=True)
    _, pore_only = _run(core, soret_coeff=5.0e-3, delta_T=30.0, feed_CO2=2.0e-3, membrane=False)
    _, memb_only = _run(core, soret_coeff=5.0e-3, delta_T=1.0e-6, feed_CO2=2.0e-3, membrane=True)
    assert both > pore_only and both > memb_only
    assert both < CONSUMABLE          # yet still short at defensible Soret
