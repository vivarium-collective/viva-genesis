"""og-precursor-pool: the functional precursor pool on the real C1-C3
reaction-universe engine.

Covers the model functions (degree of reduction, carbon-source attribution,
electron budget), process registration, and the canonical + control composites:
the pool is assembled de novo from CO2 with exact atom balance and a closed
electron budget, lands sub-consumable (the qualified finding), and collapses
under each ablation control.
"""
from __future__ import annotations

import math

import pytest

from process_bigraph import Composite, gather_emitter_results
from viva_genesis.core import build_core
from viva_genesis.protometabolism import universe as U
from viva_genesis.protometabolism.precursor_pool import (
    PrecursorPoolProcess,
    carbon_source_attribution,
    degree_of_reduction,
    electron_budget,
    functional_precursors,
)
from viva_genesis.composites import precursor_pool as PP


# --------------------------------------------------------------------------- #
# Model functions
# --------------------------------------------------------------------------- #
def test_degree_of_reduction_reference():
    # gamma = 4C + H - 2O, referenced so CO2 -> 0 and H2 -> 2.
    assert degree_of_reduction({"C": 1, "O": 2}) == 0.0        # CO2
    assert degree_of_reduction({"H": 2}) == 2.0                # H2
    assert degree_of_reduction({"H": 2, "O": 1}) == 0.0        # H2O
    assert degree_of_reduction({"C": 1, "H": 2, "O": 1}) == 4.0  # formaldehyde CH2O


def _drive(core, n=48, config=None, feed=None):
    cfg = {"max_carbons": 3, "thermo_source": "package", "ammonium_availability": 1.3e-4}
    cfg.update(config or {})
    p = PrecursorPoolProcess(config=cfg, core=core)
    st = p.initial_state()
    st.update(feed or {})
    for _ in range(n):
        p.update(st, 1.0)
    return p


def test_registered_as_local_address():
    core = build_core()
    assert "PrecursorPoolProcess" in core.link_registry


def test_pool_is_atom_balanced_and_de_novo():
    core = build_core()
    p = _drive(core)
    u = p.universe()
    # exact atom balance of the generated universe
    assert u.element_residual()["max_abs"] == 0.0
    # with CO2 the sole carbon feed, the functional pool is de-novo CO2-fixed
    attr = carbon_source_attribution(u, p._fluxes, set(), flux_floor=1.0e-30)
    funcs = functional_precursors(u)
    produced = [s for s in funcs if p._conc.get(s, 0.0) > 1e-30]
    assert produced, "expected some functional precursors above floor"
    # carbon-weighted de-novo CO2-fixed fraction of the functional pool
    num = sum(U.n_carbons(s) * p._conc[s] * attr[s]["co2_fixed"] for s in produced)
    den = sum(U.n_carbons(s) * p._conc[s] for s in produced)
    assert num / den == pytest.approx(1.0, abs=1e-3)


def test_electron_budget_closes():
    core = build_core()
    p = _drive(core)
    eb = electron_budget(p.universe(), p._fluxes)
    # electrons from H2 oxidation are accounted for in the reduced organics
    assert eb["electron_budget_residual"] < 1e-9
    assert eb["electrons_supplied_rate"] > 0.0


def test_attribution_reflects_fed_organics():
    """When an upstream organic is fed, the attribution routes a real fraction of
    that species' carbon to 'fed' — the carbon-source trace is not hard-coded to
    1.0 de-novo. (Formate is both fed AND fixed de novo from CO2, so its carbon is
    an honest blend; the point is the fed share is tracked, not zero.)"""
    core = build_core()
    base = _drive(core)
    base_attr = carbon_source_attribution(base.universe(), base._fluxes, set(),
                                          flux_floor=1.0e-30)
    assert base_attr["X_A"]["fed"] == pytest.approx(0.0, abs=1e-9)  # nothing fed -> 0

    p = _drive(core, feed={"feed_formate": 1.0e-4})
    attr = carbon_source_attribution(p.universe(), p._fluxes, {"X_A"}, flux_floor=1.0e-30)
    # feeding formate routes a real fed share into formate's carbon (a blend, since
    # the network also fixes formate de novo), and the two sources sum to 1.
    assert attr["X_A"]["fed"] > 0.05
    assert attr["X_A"]["co2_fixed"] < 0.95
    assert attr["X_A"]["fed"] + attr["X_A"]["co2_fixed"] == pytest.approx(1.0, abs=1e-6)


# --------------------------------------------------------------------------- #
# Composites
# --------------------------------------------------------------------------- #
def _run_composite(core, fn, n=120):
    sim = Composite({"state": fn(core=core)}, core=core)
    sim.run(float(n))
    return gather_emitter_results(sim)[("emitter",)][-1]


def test_all_four_generators_registered():
    from process_bigraph.composite_generator import _REGISTRY
    import viva_genesis.composites  # noqa: F401  (fires the decorators)
    for g in ("precursor_pool", "precursor_pool_no_h2", "precursor_pool_no_catalyst",
              "precursor_pool_no_gradient"):
        assert f"viva_genesis.composites.precursor_pool.{g}" in _REGISTRY


def test_canonical_composite_delivers_de_novo_pool():
    core = build_core()
    last = _run_composite(core, PP.precursor_pool)
    assert last["element_residual"] == 0.0
    assert last["electron_budget_residual"] < 1e-9
    assert last["pool_cofixed_fraction"] == pytest.approx(1.0, abs=1e-3)
    # the functional pool is real but sub-consumable (the qualified finding)
    assert 0.0 < last["functional_pool_carbon"] < 1.0e-6
    # C:N in the viable band
    assert 1.0 <= last["cn_ratio"] <= 8.0


@pytest.mark.parametrize("ctrl", ["no_h2", "no_catalyst", "no_gradient"])
def test_controls_collapse_functional_pool(ctrl):
    core = build_core()
    can = _run_composite(core, PP.precursor_pool)["functional_pool_carbon"]
    fn = getattr(PP, f"precursor_pool_{ctrl}")
    ctl = _run_composite(core, fn)["functional_pool_carbon"]
    assert ctl < 0.01 * can, f"{ctrl} did not collapse the pool ({ctl:.2e} vs {can:.2e})"
