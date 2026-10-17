"""Study 12 — Energy Currency (REBUILD chemistry): an explicit thioester/acyl-phosphate cycle.

Replaces the abstract charged-pool currency (proto_energetics / ProtoEnergyCurrencyProcess)
with the explicit ThioesterCarrierCycleProcess: named species reacting through
activation (drive-gated bond formation) → use against a load → hydrolysis leak, with
a closed free-energy ledger. The exergonic GeochemicalDriveProcess supplies the drive
ΔG (same drive as og-05), gating bond formation only when it clears the thioester bond.

Decision test (plan): a full energy accounting supports useful coupled work WITHOUT
hidden energy inflow — observable as net_useful_work > 0 with budget_residual ~ 0.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

_EMIT = ("net_useful_work", "work_done", "leak_loss", "budget_residual",
         "energy_charge_fraction", "acetyl_thioester")
_EMIT_PATHS = ["cell/" + p for p in _EMIT]


@composite_generator(
    name="og_12_energy_carrier_cycle",
    methods=["explicit thioester/acyl-phosphate cycle (named species, balanced steps)",
             "geochemical drive (ΔG gate)", "closed free-energy ledger"],
    fidelity="real",
    description=(
        "Study 12: the energy currency as explicit chemistry. GeochemicalDriveProcess supplies "
        "an exergonic drive ΔG that activates a named thioester carrier only when it clears the "
        "high-energy bond; the carrier does useful work against an endergonic load and leaks by "
        "hydrolysis. A closed free-energy ledger (budget_residual ~ 0) credits useful coupled "
        "work only with no hidden energy inflow — replacing the abstract charged-pool currency."
    ),
    parameters={
        "drive_free_energy": {"type": "float", "default": 50.0,
                              "description": "Geochemical drive ΔG supplied (kJ/mol)"},
        "bond_energy_kjmol": {"type": "float", "default": 31.5,
                              "description": "Carrier high-energy bond (thioester ~31.5; acyl-phosphate ~43)"},
        "load": {"type": "float", "default": 20.0,
                 "description": "Endergonic load the carrier does work against (kJ/mol)"},
        "k_hydrolyze": {"type": "float", "default": 0.02,
                        "description": "Hydrolysis leak rate (1/s)"},
    },
    default_n_steps=120,
    preferred_time="6 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def og_12_energy_carrier_cycle(core=None, *, drive_free_energy=50.0, bond_energy_kjmol=31.5,
                               load=20.0, k_hydrolyze=0.02):
    if core is None:
        core = build_core()
    return {
        "drive": {
            "_type": "process",
            "address": "local:GeochemicalDriveProcess",
            "config": {"g_drive": float(drive_free_energy)},
            "interval": 1.0,
            "inputs": {},
            "outputs": {"drive_free_energy": ["env", "drive_free_energy"]},
        },
        "carrier": {
            "_type": "process",
            "address": "local:ThioesterCarrierCycleProcess",
            "config": {"bond_energy_kjmol": float(bond_energy_kjmol),
                       "k_hydrolyze": float(k_hydrolyze)},
            "interval": 1.0,
            "inputs": {"drive_free_energy": ["env", "drive_free_energy"],
                       "load": ["env", "load"],
                       "acetate": ["feed", "acetate"], "thiol": ["feed", "thiol"]},
            "outputs": {p: ["cell", p] for p in _EMIT},
        },
        "env": {"drive_free_energy": float(drive_free_energy), "load": float(load)},
        "feed": {"acetate": 1.0e-3, "thiol": 1.0e-3},
        "cell": {p: 0.0 for p in _EMIT},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {p: "float" for p in _EMIT}},
            "inputs": {p: ["cell", p] for p in _EMIT},
        },
    }
