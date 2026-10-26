"""Follow-up models for pore-concentrated self-maintenance.

#1 (grounded Soret): under both measured ionic-strength scaling laws, the
thermophoretic trap closes the loop in freshwater but not at marine salinity.
#2 (gas-bubble): the heated-interface accumulator is magnitude-limited and does
not close the gap.
"""
from __future__ import annotations

from process_bigraph import Composite, gather_emitter_results

from viva_genesis.core import build_core
from viva_genesis.composites.self_maintaining_concentrated import og_self_maintaining_concentrated
from viva_genesis.composites.self_maintaining_bubble import og_self_maintaining_bubble
from viva_genesis.membranes import amphiphile_soret as S


def _run(doc_fn, **kw):
    core = build_core()
    sim = Composite({"state": doc_fn(core=core, **kw)}, core=core)
    sim.run(240.0)
    return gather_emitter_results(sim)[("emitter",)][-1]


def test_grounded_soret_closes_in_freshwater_not_marine():
    for law in (S.soret_piazza_guarino, S.soret_duhr_braun):
        fresh = _run(og_self_maintaining_concentrated, concentrating=True,
                     soret_coeff=law(0.01), delta_T=45.0)
        marine = _run(og_self_maintaining_concentrated, concentrating=True,
                      soret_coeff=law(0.6), delta_T=45.0)
        assert fresh["aggregation_competent_concentrated"] >= 1.0      # freshwater closes
        assert marine["aggregation_competent_concentrated"] < 1.0      # marine excluded


def test_gas_bubble_is_magnitude_limited_and_does_not_close():
    r = _run(og_self_maintaining_bubble, concentrating=True, delta_T=40.0)
    assert r["aggregation_competent_concentrated"] < 1.0               # ~4000x ceiling << gap
    ctrl = _run(og_self_maintaining_bubble, concentrating=False, delta_T=40.0)
    assert ctrl["effective_enrichment"] == 1.0                         # matched control
