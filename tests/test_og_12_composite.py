"""Study-12 composite: explicit thioester carrier cycle driven by the geochemical drive."""
from process_bigraph import Composite, gather_emitter_results
from viva_genesis.core import build_core
from viva_genesis.composites.og_12_energy_carrier_cycle import og_12_energy_carrier_cycle as og12


def test_generator_and_process_registered():
    from process_bigraph.composite_generator import _REGISTRY
    assert any(e.endswith(".og_12_energy_carrier_cycle") for e in _REGISTRY)
    assert "ThioesterCarrierCycleProcess" in build_core().link_registry


def test_useful_work_with_closed_budget():
    core = build_core()
    sim = Composite({"state": og12(core, drive_free_energy=50.0, bond_energy_kjmol=31.5, load=20.0)}, core=core)
    sim.run(20.0)
    last = gather_emitter_results(sim)[("emitter",)][-1]
    assert last["net_useful_work"] > 0.0          # delivers useful coupled work
    assert abs(last["budget_residual"]) < 1e-6    # no hidden energy inflow


def test_drive_below_bond_no_useful_work():
    core = build_core()
    # drive 20 can't clear the 31.5 bond -> gated off -> honest negative result
    sim = Composite({"state": og12(core, drive_free_energy=20.0, bond_energy_kjmol=31.5, load=10.0)}, core=core)
    sim.run(20.0)
    last = gather_emitter_results(sim)[("emitter",)][-1]
    assert last["net_useful_work"] <= 1e-9
