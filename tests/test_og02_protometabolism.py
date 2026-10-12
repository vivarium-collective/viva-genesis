"""og-02 Campaign-II real model: libRoadRunner rTCA-fragment autocatalytic CSTR.

Guarded with importorskip so CI without tellurium/networkx skips (not fails).
"""
from __future__ import annotations

import pytest

from process_bigraph import Composite, allocate_core, gather_emitter_results
from viva_genesis.core import build_core

GEN_ID = "viva_genesis.composites.campaign2.og_02_reduced_carbon_to_protometabolism"


def test_process_and_viz_registered():
    reg = build_core().link_registry
    assert "RoadRunnerNetworkProcess" in reg
    assert "ProtometabolismViz" in reg


def test_generator_registered():
    from process_bigraph.composite_generator import _REGISTRY
    assert GEN_ID in _REGISTRY, f"{GEN_ID} missing; have {[i for i in _REGISTRY if 'genesis' in i]}"


def test_real_network_sustains_throughput_and_autocatalysis():
    pytest.importorskip("tellurium")
    pytest.importorskip("networkx")
    from viva_genesis.protometabolism.network import RoadRunnerNetworkProcess
    p = RoadRunnerNetworkProcess(config={}, core=allocate_core())
    st = {"feed_pyruvate": 1e-4, "feed_CO2": 2e-3}
    o = None
    for _ in range(120):
        o = p.update(st, 1.0)
    # Real libRoadRunner ODE network: sustained throughput, autocatalytic gain>1,
    # connected network, products present.
    assert o["net_carbon_flux"] > 1e-6
    assert o["autocatalytic_gain"] > 1.0
    assert o["network_connected"] == 1.0
    assert o["acetate"] > 0.0 and o["OAA"] > 0.0


def test_no_carbon_control_collapses():
    pytest.importorskip("tellurium")
    from viva_genesis.protometabolism.network import RoadRunnerNetworkProcess
    p = RoadRunnerNetworkProcess(config={}, core=allocate_core())
    o = None
    for _ in range(120):
        o = p.update({"feed_pyruvate": 1e-4, "feed_CO2": 1e-12}, 1.0)
    assert o["net_carbon_flux"] < 1e-6          # no carbon -> no throughput
    assert o["autocatalytic_gain"] < 1.0        # autocatalysis collapses


def test_favorable_composite_emerges_metabolism():
    pytest.importorskip("tellurium")
    pytest.importorskip("networkx")
    from viva_genesis.composites.campaign2 import og_02_reduced_carbon_to_protometabolism
    core = build_core()
    sim = Composite({"state": og_02_reduced_carbon_to_protometabolism(core)}, core=core)
    sim.run(120.0)
    last = gather_emitter_results(sim)[("emitter",)][-1]
    assert last["net_carbon_flux"] > 1e-6
    assert last["autocatalytic_gain"] >= 1.0
    assert last["network_connected"] == 1.0
