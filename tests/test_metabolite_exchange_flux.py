"""S2 calibration guard: pore exchange registers as cross-lineage flux, and proximity matters."""
from __future__ import annotations

from process_bigraph import Composite
from viva_genesis.core import build_core


def _flux(placement, n=250):
    from viva_genesis.composites.metabolite_exchange_community import metabolite_exchange_community
    core = build_core()
    sim = Composite({"state": metabolite_exchange_community(
        core=core, lineages="fixer:4,reducer:4", coupling="shared", model_proto_ecology="reaction_universe",
        p_diacid=1e-8, p_monoacid=1e-7, k_wash=0.01, placement=placement, k_diffusion=0.001)}, core=core)
    sim.run(float(n))
    return float(sim.state["exchange"]["cross_lineage_flux_total"])


def test_mixed_flux_nonzero_and_22x_over_segregated():
    mixed, seg = _flux("mixed"), _flux("segregated")
    assert mixed > 1e-22, mixed  # S2 pass threshold
    assert 3e-22 < mixed < 5e-22, mixed  # calibration 4.005e-22
    assert 15 < mixed / seg < 30, (mixed, seg)  # calibration ratio ~22x
