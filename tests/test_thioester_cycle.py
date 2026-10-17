"""Explicit thioester/acyl-phosphate carrier cycle (study 12 REBUILD chemistry).

Replaces the abstract charged-pool carrier with named species reacting through a
specified cycle (activation of the high-energy bond by the geochemical drive →
use against an endergonic load → hydrolysis leak), with a full free-energy ledger.
The decision test is "useful coupled work with NO hidden energy inflow": net
useful work > 0 only when the drive ΔG clears the bond, and the energy budget
closes (budget_residual ~ 0).
"""
from process_bigraph import allocate_core
from viva_genesis.bioenergetics.thioester_cycle import ThioesterCarrierCycleProcess


def _p(**cfg):
    return ThioesterCarrierCycleProcess(config=cfg, core=allocate_core())


def _run(p, state, n=20, interval=1.0):
    st = dict(state)
    for _ in range(n):
        out = p.update(st, interval)
        for k, v in out.items():
            # sensors overwrite; pools accumulate the deltas into the state
            st[k] = v if k in ("acetyl_thioester", "net_useful_work", "leak_loss",
                               "budget_residual", "energy_charge_fraction", "work_done") else st.get(k, 0.0)
    return out


def test_ports_and_named_species():
    p = _p()
    assert {"drive_free_energy", "load", "acetate", "thiol"} <= set(p.inputs())
    outs = set(p.outputs())
    assert {"acetyl_thioester", "net_useful_work", "leak_loss", "budget_residual",
            "energy_charge_fraction", "work_done"} <= outs


def test_drive_clears_bond_delivers_useful_work_budget_closes():
    p = _p(bond_energy_kjmol=31.5, k_activate=0.3, k_use=0.3, k_hydrolyze=0.02)
    out = _run(p, {"drive_free_energy": 50.0, "load": 20.0, "acetate": 1.0e-3, "thiol": 1.0e-3})
    assert out["acetyl_thioester"] > 0.0        # the carrier actually charges
    assert out["net_useful_work"] > 0.0         # delivers useful coupled work
    assert abs(out["budget_residual"]) < 1e-6   # NO hidden energy inflow


def test_drive_below_bond_gate_fails_no_useful_work():
    # Drive ΔG (20) can't clear the thioester bond (31.5): activation is gated off.
    p = _p(bond_energy_kjmol=31.5, k_activate=0.3, k_use=0.3)
    out = _run(p, {"drive_free_energy": 20.0, "load": 10.0, "acetate": 1.0e-3, "thiol": 1.0e-3})
    assert out["acetyl_thioester"] < 1e-9       # never charges
    assert out["net_useful_work"] <= 1e-9       # the honest negative/threshold result


def test_hydrolysis_leak_reduces_net_work():
    base = _run(_p(bond_energy_kjmol=31.5, k_activate=0.3, k_use=0.3, k_hydrolyze=0.0),
                {"drive_free_energy": 50.0, "load": 20.0, "acetate": 1e-3, "thiol": 1e-3})
    leaky = _run(_p(bond_energy_kjmol=31.5, k_activate=0.3, k_use=0.3, k_hydrolyze=0.3),
                 {"drive_free_energy": 50.0, "load": 20.0, "acetate": 1e-3, "thiol": 1e-3})
    assert leaky["leak_loss"] > base["leak_loss"]
    assert leaky["net_useful_work"] < base["net_useful_work"]
