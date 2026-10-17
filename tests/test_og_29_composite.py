"""Study-29 composite: endogenous (vent-fed) autocatalysis + Gate A matched null.

Asserts the generator is discoverable, that the reaction network is fed from the
upstream supply store (the 27->29 handoff) rather than the prescribed open-network
feed, that matched_null swaps the degree-preserving null on the SAME supply, and
that a short real run produces the autocatalysis observables.
"""
import pytest

from process_bigraph import Composite, gather_emitter_results

from viva_genesis.core import build_core
from viva_genesis.composites.og_29_endogenous_autocatalysis import (
    og_29_endogenous_autocatalysis as og29,
)


def test_generator_is_registered():
    from process_bigraph.composite_generator import _REGISTRY
    assert any(eid.endswith(".og_29_endogenous_autocatalysis") for eid in _REGISTRY)


def test_network_is_fed_from_the_endogenous_supply():
    doc = og29(build_core(), supply_H2=2.0e-3, supply_CO2=3.0e-3)
    # Carbon + H2 feed come from the supply store (27->29 handoff), not ["feed", ...].
    assert doc["network"]["inputs"]["feed_CO2"] == ["supply", "CO2"]
    assert doc["network"]["inputs"]["feed_H2"] == ["supply", "H2"]
    assert doc["supply"] == {"H2": 2.0e-3, "CO2": 3.0e-3}


def test_matched_null_swaps_the_null_network_on_same_supply():
    core = build_core()
    real = og29(core, matched_null=False)
    null = og29(core, matched_null=True, supply_H2=1.5e-3)
    assert real["network"]["address"] != null["network"]["address"]
    assert "null" in null["network"]["address"].lower()
    # Null runs on the SAME endogenous supply wiring (fluxes held equal).
    assert null["network"]["inputs"]["feed_CO2"] == ["supply", "CO2"]
    assert null["supply"]["H2"] == 1.5e-3


def test_short_run_produces_autocatalysis_observables():
    core = build_core()
    sim = Composite({"state": og29(core, max_carbons=3)}, core=core)
    sim.run(3.0)
    rows = gather_emitter_results(sim)[("emitter",)]
    assert rows
    last = rows[-1]
    for k in ("net_carbon_flux", "autocatalytic_gain", "network_connected", "supply_H2"):
        assert k in last
