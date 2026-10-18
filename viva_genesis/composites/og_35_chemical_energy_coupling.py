"""Study 35 (Gate E, optional) — Chemical Energy Coupling.

Does a specified chemical energy carrier (a thioester cycle, tied to the og-12 energy
rebuild) let the protocell do endergonic work when the environmental gradient DIPS,
beating a matched gradient-only control — with a FULL energy ledger that closes and no
hidden inflow? (⚑ Option B: one specified thioester carrier; the alternative carrier /
microkinetic resolution is the follow-on og-35a.)

A :class:`~viva_genesis.bioenergetics.proto_energetics.GeochemicalDriveProcess` supplies
a declining drive free energy (the gradient waning). Against a constant endergonic load:
  carrier=True  — :class:`ThioesterCarrierCycleProcess` CHARGES the carrier while the
                  drive clears the bond, then DISCHARGES the stored free energy to do
                  work when the drive dips (buffered); hydrolysis is an accounted leak.
  carrier=False — matched GRADIENT-ONLY null (:class:`GradientOnlyWorkProcess`): direct
                  drive->work with NO store, so a dip cuts the work immediately.
Both arms see the SAME drive trajectory and load (inputs held equal). The free-energy
ledger closes each step (``budget_residual`` ~ 0) in both arms — no hidden inflow.

The benefit is net useful work + persistence through the dip, IF the carrier's
synthesis/hydrolysis costs are outweighed; a net cost is a reported negative. Guardrail:
the metabolism funded is the sustained A1 carbon-fixing network, not autocatalytic
(A2 refuted). Carrier bond energies are literature values (thioester ~31.5 kJ/mol;
huber1997/buckel2013), a labelled proposed_input, not tuned.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core


@composite_generator(
    name="og_35_chemical_energy_coupling",
    methods=["thioester carrier cycle with a closed free-energy ledger",
             "declining geochemical drive (gradient dip)",
             "matched gradient-only control (direct drive->work, no store)"],
    fidelity="real",
    description=(
        "Gate E energy coupling: does a specified thioester carrier cycle do endergonic work when the "
        "geochemical gradient DIPS, beating a matched gradient-only control, with a FULL closing energy "
        "ledger and no hidden inflow? carrier=True charges/discharges a stored carrier (buffered); "
        "carrier=False is the gradient-only null (direct drive->work, no store). Both see the same declining "
        "drive + load. Carrier chemistry = one specified thioester (Option B; acyl-phosphate / microkinetic "
        "= og-35a). Metabolism = sustained A1 network, NOT autocatalytic (A2 refuted)."
    ),
    parameters={
        "carrier": {"type": "boolean", "default": True,
                    "description": "Thioester carrier cycle (True) vs matched gradient-only null (False)"},
        "g_drive": {"type": "float", "default": 50.0, "description": "Initial geochemical drive free energy (kJ/mol)"},
        "decline_rate": {"type": "float", "default": 0.4, "description": "Drive decline per step (kJ/mol) — the gradient dip"},
        "g_floor": {"type": "float", "default": 2.0, "description": "Drive floor (kJ/mol)"},
        "load": {"type": "float", "default": 30.0, "description": "Endergonic load to lift (kJ/mol)"},
        "bond_energy_kjmol": {"type": "float", "default": 31.5, "description": "Carrier high-energy bond (thioester ~31.5; proposed_input)"},
        "k_hydrolyze": {"type": "float", "default": 0.02, "description": "Carrier hydrolysis leak rate (1/s)"},
        "base_CO2": {"type": "float", "default": 1.0e-3, "description": "Vent feed (provenance for the metabolic regime)"},
        "base_H2": {"type": "float", "default": 1.0e-3, "description": "Vent feed (provenance)"},
        "porosity": {"type": "float", "default": 0.88, "description": "Gate-B pore porosity (provenance)"},
        "max_carbons": {"type": "integer", "default": 4, "description": "Carbon cap (provenance)"},
    },
    default_n_steps=120,
    preferred_time="2 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter",
               "paths": ["work/net_useful_work", "work/budget_residual",
                         "work/acetyl_thioester", "drive_store/drive_free_energy"]}],
)
def og_35_chemical_energy_coupling(
        core=None, *, carrier=True, g_drive=50.0, decline_rate=0.4, g_floor=2.0, load=30.0,
        bond_energy_kjmol=31.5, k_hydrolyze=0.02, base_CO2=1.0e-3, base_H2=1.0e-3,
        porosity=0.88, max_carbons=4):
    if core is None:
        core = build_core()
    doc = {
        "drive": {
            "_type": "process",
            "address": "local:GeochemicalDriveProcess",
            "config": {"g_drive": float(g_drive), "g_floor": float(g_floor),
                       "decline_rate": float(decline_rate)},
            "interval": 1.0,
            "inputs": {},
            "outputs": {"drive_free_energy": ["drive_store", "drive_free_energy"]},
        },
        "env": {"load": float(load)},
        "drive_store": {"drive_free_energy": float(g_drive)},
        "work": {"net_useful_work": 0.0, "work_done": 0.0, "budget_residual": 0.0,
                 "acetyl_thioester": 0.0},
    }
    if carrier:
        doc["engine"] = {
            "_type": "process",
            "address": "local:ThioesterCarrierCycleProcess",
            "config": {"bond_energy_kjmol": float(bond_energy_kjmol), "k_hydrolyze": float(k_hydrolyze)},
            "interval": 1.0,
            "inputs": {"drive_free_energy": ["drive_store", "drive_free_energy"], "load": ["env", "load"],
                       "acetate": ["pools", "acetate"], "thiol": ["pools", "thiol"]},
            "outputs": {"acetyl_thioester": ["work", "acetyl_thioester"],
                        "work_done": ["work", "work_done"],
                        "net_useful_work": ["work", "net_useful_work"],
                        "leak_loss": ["work", "leak_loss"],
                        "budget_residual": ["work", "budget_residual"],
                        "energy_charge_fraction": ["work", "energy_charge_fraction"]},
        }
        doc["pools"] = {"acetate": 1.0e-3, "thiol": 1.0e-3}
        doc["work"]["leak_loss"] = 0.0
        doc["work"]["energy_charge_fraction"] = 0.0
    else:
        doc["engine"] = {
            "_type": "process",
            "address": "local:GradientOnlyWorkProcess",
            "config": {"bond_energy_kjmol": float(bond_energy_kjmol)},
            "interval": 1.0,
            "inputs": {"drive_free_energy": ["drive_store", "drive_free_energy"], "load": ["env", "load"],
                       "acetate": ["pools", "acetate"], "thiol": ["pools", "thiol"]},
            "outputs": {"net_useful_work": ["work", "net_useful_work"],
                        "work_done": ["work", "work_done"],
                        "budget_residual": ["work", "budget_residual"],
                        "acetyl_thioester": ["work", "acetyl_thioester"]},
        }
        doc["pools"] = {"acetate": 1.0e-3, "thiol": 1.0e-3}
    return doc
