"""og-growth-division real model: metabolism → osmotic growth & division.

Coarse-grained, units-typed, mass-conserving osmotic-coupling model (no heavy deps) —
runs everywhere and is reproducible.
"""
from __future__ import annotations

from process_bigraph import Composite, gather_emitter_results
from viva_genesis.core import build_core

GEN_ID = "viva_genesis.composites.osmotic_growth_division.osmotic_growth_division"

# Process-bigraph's config merge ignores a falsy 0.0 override, so the zero-throughput
# ablation uses a negligible (~12 orders below favorable) throughput.
_ABLATION_THROUGHPUT = 1.0e-30


def test_process_and_generator_registered():
    reg = build_core().link_registry
    assert "OsmoticGrowthDivisionProcess" in reg
    for viz in ("OsmoticGrowthWorld", "OsmoticCouplingMechanism", "GrowthDivisionMap"):
        assert viz in reg
    from process_bigraph.composite_generator import _REGISTRY
    assert GEN_ID in _REGISTRY, f"{GEN_ID} missing; have {[i for i in _REGISTRY if 'genesis' in i]}"


def _run(n=100, **kw):
    from viva_genesis.composites.osmotic_growth_division import osmotic_growth_division
    core = build_core()
    sim = Composite({"state": osmotic_growth_division(core=core, **kw)}, core=core)
    sim.run(float(n))
    return gather_emitter_results(sim)[("emitter",)]


def test_net_growth_to_division():
    """The favorable (matched) compartment grows under the osmotic load its chemistry
    generates and divides repeatedly — outcome = divide (code 2)."""
    rows = _run()
    last = rows[-1]
    assert last["division_count"] >= 1          # chemistry drove growth → division
    assert last["outcome_code"] == 2            # divide
    assert last["lysed"] == 0
    # the internal concentration (osmotic drive) is drawn down at each division (sawtooth)
    assert any(r["division_event"] for r in rows)


def test_mass_conserved_across_division():
    """Osmolyte mass is conserved to machine precision across growth AND division."""
    rows = _run()
    assert max(abs(r["osmolyte_balance_residual"]) for r in rows) < 1e-18


def test_viable_band_is_bounded_by_starve_and_lyse():
    """The viable growth→division band is bounded: too permeable starves (no osmotic
    build-up, no division), too impermeable lyses (pressure bursts the membrane)."""
    starve = _run(membrane_permeability=1.0e-5)[-1]
    assert starve["division_count"] == 0 and starve["lysed"] == 0   # starvation
    assert starve["net_growth"] < 1.1                               # did not grow
    assert starve["outcome_code"] == 0

    lyse = _run(network_throughput=1.0e-18, membrane_permeability=1.0e-10)[-1]
    assert lyse["lysed"] == 1                                       # burst
    assert lyse["outcome_code"] == 3


def test_ablation_no_throughput_no_growth():
    """Feature ablation: with no autocatalytic source there is no osmotic growth or
    division — the growth is driven by the chemistry, not the compartment physics."""
    fav = _run()[-1]
    ab = _run(network_throughput=_ABLATION_THROUGHPUT)[-1]
    assert fav["division_count"] >= 1
    assert ab["division_count"] == 0
    assert ab["net_growth"] < 1.1


def test_growth_division_phase_map_has_a_bounded_viable_band():
    """The Decision surface over (throughput × permeability) contains all three fates —
    a bounded viable (dividing) band flanked by starvation and lysis."""
    import numpy as np
    from viva_genesis.phase_maps import growth_division_map
    res = growth_division_map(network_throughput=(1e-21, 1e-18, 8),
                              membrane_permeability=(1e-10, 1e-4, 8), n_steps=100)
    outcomes = set(np.unique(res.surfaces["outcome"]).tolist())
    assert {0.0, 2.0, 3.0} <= outcomes          # starve, divide, lyse all present
    assert 0.0 < res.meta["viable_fraction"] < 1.0   # the band is bounded
