"""og-proto-energetics real model: a transferable energy currency before modern pumping.

An exergonic geochemical drive charges a pre-ATP carrier pool that is discharged for
endergonic work under load and bled by hydrolysis, under a conserved free-energy
ledger. Deterministic reduced kinetics (no heavy deps) — runs everywhere.
"""
from __future__ import annotations

from process_bigraph import Composite, gather_emitter_results
from viva_genesis.core import build_core

GEN_ID = "viva_genesis.composites.proto_energetics.proto_energetics"


def test_processes_and_generator_registered():
    reg = build_core().link_registry
    assert "ProtoEnergyCurrencyProcess" in reg
    assert "GeochemicalDriveProcess" in reg
    assert "ProtoEnergeticsWorldViz" in reg
    assert "ProtoEnergeticsProvenanceViz" in reg
    assert "ProtoEnergeticsMap" in reg
    from process_bigraph.composite_generator import _REGISTRY
    assert GEN_ID in _REGISTRY, f"{GEN_ID} missing; have {[i for i in _REGISTRY if 'genesis' in i]}"


def _run(n=60, **kw):
    from viva_genesis.composites.proto_energetics import proto_energetics
    core = build_core()
    sim = Composite({"state": proto_energetics(core=core, **kw)}, core=core)
    sim.run(float(n))
    return gather_emitter_results(sim)[("emitter",)]


def test_free_energy_ledger_conserved():
    """Free-energy accounting is a contract invariant: input = work + stored +
    dissipated to machine precision, every tick (the conservation witness)."""
    rows = _run()
    assert max(abs(r["energy_ledger_residual"]) for r in rows) < 1e-9


def test_currency_maintained_and_captures_free_energy():
    """At the favourable operating point the carrier stays charged under continuous
    load (the currency is maintained) and a substantial fraction of the geochemical
    free energy is captured as transferable usable work."""
    rows = _run()
    assert rows[0]["energy_charge_fraction"] < 0.05       # starts empty
    assert rows[-1]["energy_charge_fraction"] > 0.25      # maintained under load
    assert rows[-1]["energy_stored_work_fraction"] > 0.30  # captures free energy
    assert rows[-1]["energy_work"] > 0.0                   # useful work delivered


def test_ablations_collapse_the_currency():
    """No coupling (coupling_efficiency -> 0) or no drive (drive ΔG below the carrier
    bond) -> nothing is captured, the carrier never charges (the ablations)."""
    no_coupling = _run(coupling_efficiency=0.0)
    no_drive = _run(drive_free_energy=10.0)       # below the 35 kJ/mol thioester bond
    assert no_coupling[-1]["energy_charge_fraction"] < 0.02
    assert no_drive[-1]["energy_charge_fraction"] < 0.02

    # Discriminating: the favourable arm maintains a currency where the ablations cannot.
    fav = _run()
    assert fav[-1]["energy_charge_fraction"] > no_coupling[-1]["energy_charge_fraction"] + 0.2
    assert fav[-1]["energy_charge_fraction"] > no_drive[-1]["energy_charge_fraction"] + 0.2


def test_phase_map_has_bounded_pass_region():
    """The Decision view is a phase map, not a single run: over (drive × coupling
    efficiency) the currency is maintained above threshold only in a bounded region —
    neither the whole grid nor none of it."""
    from viva_genesis.phase_maps import _ENERGY_CURRENCY_THRESHOLD, proto_energetics_map
    res = proto_energetics_map(drive_free_energy=(15.0, 70.0, 7),
                               coupling_efficiency=(0.05, 1.0, 7), n_steps=40, n_jobs=1)
    cf = res.surfaces["charge_fraction"]
    passed = (cf >= _ENERGY_CURRENCY_THRESHOLD).mean()
    assert 0.05 < float(passed) < 0.95          # a real boundary, not degenerate
    # the low-drive / low-efficiency corner fails; the high / high corner passes.
    assert cf[0, 0] < _ENERGY_CURRENCY_THRESHOLD
    assert cf[-1, -1] >= _ENERGY_CURRENCY_THRESHOLD
