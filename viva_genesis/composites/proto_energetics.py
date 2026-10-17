"""Proto-energetics composite — a transferable energy currency before modern pumping.

A reusable energy-currency module that sits BEFORE modern-style ion pumping
(og-05): an exergonic geochemical drive (``GeochemicalDriveProcess``) charges a
transferable carrier pool whose charge/discharge/hydrolysis is tracked as an
explicit FREE-ENERGY LEDGER (``ProtoEnergyCurrencyProcess``). The composite asks
whether a primitive system can CAPTURE environmental free energy into a store it
can spend on endergonic work under load — not merely run reactions downhill.

One parameterized generator drives every study condition:

  - favorable          : a strong drive + efficient coupling -> currency stays
                         charged under load; a large fraction of the geochemical
                         free energy becomes stored usable work.
  - no-coupling control: coupling_efficiency -> 0 -> nothing is captured; the
                         carrier never charges (ablation).
  - no-drive control   : drive_free_energy below the carrier bond -> the drive
                         cannot clear the bond -> currency collapses (ablation).

Emits the carrier charge/discharge/loss fluxes and the full free-energy ledger
(input / work / stored / dissipated). Coarse-grained, deterministic (reproducible).
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

_EMIT_PATHS = [
    "pool/energy_charge", "pool/energy_charge_fraction",
    "pool/energy_charge_flux", "pool/energy_discharge_flux", "pool/energy_loss_flux",
    "pool/energy_input", "pool/energy_work", "pool/energy_stored", "pool/energy_dissipated",
    "pool/energy_stored_work_fraction", "pool/energy_ledger_residual",
    "env/drive_free_energy",
    "global_time",
]


@composite_generator(
    name="proto_energetics",
    methods=["coarse-grained energy-currency bookkeeping"],
    fidelity="reproduction",
    description=(
        "A transferable energy currency before modern pumping (pre-og-05). An exergonic "
        "geochemical drive charges a carrier pool (thioester / acyl-phosphate class) that is "
        "discharged for endergonic work under load and bled by hydrolysis, all tracked in a "
        "conserved free-energy ledger (input = work + stored + dissipated). Tests whether the "
        "system captures environmental free energy into a transferable store, and what fraction "
        "becomes stored usable work. drive_free_energy / coupling_efficiency set the arm; "
        "coupling->0 or drive below the carrier bond collapses the currency (ablations). "
        "Coarse-grained, deterministic reproduction (not a wrapped engine)."
    ),
    parameters={
        "drive_free_energy": {"type": "float", "default": 50.0,
                              "description": "Exergonic geochemical drive ΔG available (kJ/mol); below the carrier bond the drive cannot charge it"},
        "coupling_efficiency": {"type": "float", "default": 0.6,
                                "description": "Fraction of tapped drive free energy coupled into the carrier bond (0 = no coupling ablation)"},
        "carrier_pool": {"type": "float", "default": 1.0e-3,
                         "description": "Total carrier concentration (molar), charged + free"},
        "loss_rate": {"type": "float", "default": 0.05,
                      "description": "First-order hydrolysis / loss rate of charged carrier (per tick)"},
        "load": {"type": "float", "default": 0.20,
                 "description": "Endergonic work demand as a fraction of the carrier pool per tick"},
        "carrier": {"type": "string", "default": "thioester",
                    "description": "Primitive carrier chemistry (thioester / acyl_phosphate / polyphosphate / reduced_metal)"},
    },
    visualizations=[
        {"name": "proto-energetics-world", "address": "local:ProtoEnergeticsWorldViz",
         "config": {"title": "Proto-energetics — charging and spending the currency"}},
    ],
    default_n_steps=60,
    preferred_time="12 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def proto_energetics(core=None, *, drive_free_energy=50.0, coupling_efficiency=0.6,
                     carrier_pool=1.0e-3, loss_rate=0.05, load=0.20, carrier="thioester"):
    return {
        "drive": {
            "_type": "process",
            "address": "local:GeochemicalDriveProcess",
            "config": {"g_drive": drive_free_energy},
            "interval": 1.0,
            "inputs": {},
            "outputs": {"drive_free_energy": ["env", "drive_free_energy"]},
        },
        "currency": {
            "_type": "process",
            "address": "local:ProtoEnergyCurrencyProcess",
            "config": {"carrier": carrier, "carrier_pool": carrier_pool,
                       "coupling_efficiency": coupling_efficiency,
                       "loss_rate": loss_rate, "load": load},
            "interval": 1.0,
            "inputs": {"drive_free_energy": ["env", "drive_free_energy"],
                       "coupling_efficiency": ["env", "coupling_efficiency"],
                       "load": ["env", "load"]},
            "outputs": {
                "energy_charge": ["pool", "energy_charge"],
                "energy_charge_fraction": ["pool", "energy_charge_fraction"],
                "energy_charge_flux": ["pool", "energy_charge_flux"],
                "energy_discharge_flux": ["pool", "energy_discharge_flux"],
                "energy_loss_flux": ["pool", "energy_loss_flux"],
                "energy_input": ["pool", "energy_input"],
                "energy_work": ["pool", "energy_work"],
                "energy_stored": ["pool", "energy_stored"],
                "energy_dissipated": ["pool", "energy_dissipated"],
                "energy_stored_work_fraction": ["pool", "energy_stored_work_fraction"],
                "energy_ledger_residual": ["pool", "energy_ledger_residual"],
            },
        },
        "env": {"drive_free_energy": drive_free_energy,
                "coupling_efficiency": coupling_efficiency, "load": load},
        "pool": {"energy_charge": 0.0, "energy_charge_fraction": 0.0,
                 "energy_charge_flux": 0.0, "energy_discharge_flux": 0.0, "energy_loss_flux": 0.0,
                 "energy_input": 0.0, "energy_work": 0.0, "energy_stored": 0.0,
                 "energy_dissipated": 0.0, "energy_stored_work_fraction": 0.0,
                 "energy_ledger_residual": 0.0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {
                "energy_charge": "float", "energy_charge_fraction": "float",
                "energy_charge_flux": "float", "energy_discharge_flux": "float",
                "energy_loss_flux": "float", "energy_input": "float", "energy_work": "float",
                "energy_stored": "float", "energy_dissipated": "float",
                "energy_stored_work_fraction": "float", "energy_ledger_residual": "float",
                "drive_free_energy": "float", "global_time": "float"}},
            "inputs": {
                "energy_charge": ["pool", "energy_charge"],
                "energy_charge_fraction": ["pool", "energy_charge_fraction"],
                "energy_charge_flux": ["pool", "energy_charge_flux"],
                "energy_discharge_flux": ["pool", "energy_discharge_flux"],
                "energy_loss_flux": ["pool", "energy_loss_flux"],
                "energy_input": ["pool", "energy_input"],
                "energy_work": ["pool", "energy_work"],
                "energy_stored": ["pool", "energy_stored"],
                "energy_dissipated": ["pool", "energy_dissipated"],
                "energy_stored_work_fraction": ["pool", "energy_stored_work_fraction"],
                "energy_ledger_residual": ["pool", "energy_ledger_residual"],
                "drive_free_energy": ["env", "drive_free_energy"],
                "global_time": ["global_time"]},
        },
    }
