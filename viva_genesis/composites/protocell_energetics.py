"""A protocell's energy budget — the energy_coupling face inside one individual (Phase 6).

One layer generator, five model classes selected through the typed face
``viva_genesis.models.INTERFACES["energy_coupling"]`` (``model_energy_coupling``):
``passive_gradient`` | ``h_na_gradient_leaky_membrane`` | ``thioester_acyl_phosphate``
| ``polyphosphate`` | ``fe_redox``. The individual is a protocell of radius
``protocell_radius`` whose boundary (``permeability``, area, volume — the
``vg_boundary`` / ``vg_individual`` fields og-04's membrane process publishes)
sits in the vent wall between the two free-energy sources:

* the external ion gradient ``electric_potential`` (the natural pmf; a plain
  store when ``decline_rate`` is 0, og-05's ``EnvironmentalDeclineProcess``
  when it declines — the og-05 scenario);
* the chemical drive ``drive_free_energy`` (og-energy's
  ``GeochemicalDriveProcess``; the H2/CO2 redox drive for four classes, the
  Fe(II)-disproportionation drive for ``fe_redox`` — both from the vg-data
  package ``energy_currencies``).

The class publishes the per-individual power budget and its autonomy; a
:class:`~viva_genesis.ledger.FreeEnergyLedgerProcess` audits
``free_energy_in >= work + dissipated`` with the store every tick.
``coupling_activity`` is the passive -> active axis the Phase-6 study sweeps
(0 = the external tap only; 1 = the full drive turnover coupled into the store).
"""

from __future__ import annotations

import math

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from .. import models
from ..ledger import FREE_ENERGY_LEDGER_KEYS

_BUDGET_PORTS = ("free_energy_in", "external_power", "internal_power", "maintenance_power", "work",
                 "dissipated", "leak_power", "net_power", "energy_stored", "autonomy",
                 "energy_charge_fraction", "store_potential")
_EMIT_PATHS = ([f"budget/{p}" for p in _BUDGET_PORTS] + ["budget/pmf"]
               + [f"ledger/{p}" for p in FREE_ENERGY_LEDGER_KEYS]
               + ["env/electric_potential", "env/drive_free_energy", "global_time"])
_WIRES = {**{p: ["budget", p] for p in _BUDGET_PORTS}, "pmf": ["budget", "pmf"],
          **{p: ["ledger", p] for p in FREE_ENERGY_LEDGER_KEYS},
          "electric_potential": ["env", "electric_potential"], "drive_free_energy": ["env", "drive_free_energy"],
          "global_time": ["global_time"]}

# vg-data energy_currencies nominal values (viva_genesis/data/vg_data/energy_currencies.yaml)
_PMF, _DRIVE, _FE_DRIVE, _PERM, _RADIUS = 0.216, 50.0, 40.0, 1.0e-6, 5.0e-7


@composite_generator(
    name="protocell_energetics",
    methods=["per-individual free-energy power budget", "energy_coupling model-class axis",
             "free-energy ledger (in >= work + dissipated with the store)"],
    fidelity="reproduction",
    description=(
        "A protocell's energy budget with the energy-coupling mechanism as a model CLASS on the "
        "energy_coupling face (model_energy_coupling: passive_gradient | h_na_gradient_leaky_membrane | "
        "thioester_acyl_phosphate | polyphosphate | fe_redox). The individual (radius, membrane permeability) "
        "sits between the external ion gradient (tapped only through its leak) and the chemical drive (H2/CO2 "
        "redox, or Fe(II) disproportionation for fe_redox; vg-data energy_currencies); coupling_activity moves "
        "it from passive to active. Publishes the per-individual power budget (external / internal / "
        "maintenance / leak / net power, the store, autonomy = internal / (internal + external)) audited by a "
        "FreeEnergyLedgerProcess. Coarse-grained deterministic kinetics (reproducible), not a wrapped engine."
    ),
    parameters={
        **models.model_parameters("energy_coupling", defaults={"energy_coupling": "thioester_acyl_phosphate"}),
        "coupling_activity": {"type": "float", "default": 0.5,
                              "description": "Passive -> active axis: fraction of the drive turnover coupled into the internal store (0 = external tap only) [vg-data: hypothetical]"},
        "permeability": {"type": "float", "default": _PERM,
                         "description": "Membrane H+ permeability (m/s): the leak that feeds the external tap and drains the store [vg-data: extrapolated]"},
        "electric_potential": {"type": "float", "default": _PMF,
                               "description": "External ion gradient (V) at t = 0 [vg-data: calibrated to the Phase-1 posterior dpH]"},
        "decline_rate": {"type": "float", "default": 0.0,
                         "description": "External-gradient decline (V/s); 0 = steady (og-05's collapse scenario when > 0)"},
        "gradient_floor": {"type": "float", "default": 0.02, "description": "Floor the declining gradient decays to (V)"},
        "drive_free_energy": {"type": "float", "default": _DRIVE,
                              "description": "Chemical drive free energy per turnover (kJ/mol) [vg-data: inferred]"},
        "fe_drive_free_energy": {"type": "float", "default": _FE_DRIVE,
                                 "description": "Fe(II)-disproportionation drive (kJ/mol), used by the fe_redox class [vg-data: hypothetical]"},
        "protocell_radius": {"type": "float", "default": _RADIUS, "description": "Protocell radius (m) [vg-data: inferred]"},
        "drive_turnover": {"type": "float", "default": 1.0e-21,
                           "description": "Drive turnover per cell at full activity (mol/s) [vg-data: hypothetical]"},
        "maintenance_active": {"type": "float", "default": 5.0e-18,
                               "description": "Machinery upkeep at full activity (W) [vg-data: hypothetical]"},
        "tick_seconds": {"type": "float", "default": 10.0, "description": "Physical seconds per composite tick (store timescales are ~1e3 s); processes run at interval 1"},
    },
    default_n_steps=150,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def protocell_energetics(core=None, *, model_energy_coupling="thioester_acyl_phosphate", coupling_activity=0.5,
                         permeability=_PERM, electric_potential=_PMF, decline_rate=0.0, gradient_floor=0.02,
                         drive_free_energy=_DRIVE, fe_drive_free_energy=_FE_DRIVE, protocell_radius=_RADIUS,
                         drive_turnover=1.0e-21, maintenance_active=5.0e-18, tick_seconds=10.0):
    if core is None:
        core = build_core()
    address = models.resolve_checked(core, "energy_coupling", model_energy_coupling)
    r = float(protocell_radius)
    area = 4.0 * math.pi * r * r
    volume_l = (4.0 / 3.0) * math.pi * r ** 3 * 1.0e3
    dt = float(tick_seconds)
    drive_key = "fe_redox" if model_energy_coupling == "fe_redox" else "chemical"
    config = {"coupling_activity": float(coupling_activity), "drive_turnover": float(drive_turnover),
              "maintenance_active": float(maintenance_active), "seconds_per_tick": dt}
    doc = {
        "coupling": {
            "_type": "process", "address": address, "config": config, "interval": 1.0,
            "inputs": {"electric_potential": ["env", "electric_potential"],
                       "drive_free_energy": ["env", f"drive_{drive_key}"],
                       "permeability": ["boundary", "permeability"],
                       "membrane_area": ["boundary", "membrane_area"],
                       "compartment_volume": ["individual", "compartment_volume"],
                       "temperature": ["env", "temperature"],
                       "catalyst_activity": ["env", "catalyst_activity"]},
            "outputs": {**{p: ["budget", p] for p in _BUDGET_PORTS},
                        **({"pmf": ["budget", "pmf"]} if model_energy_coupling == "h_na_gradient_leaky_membrane" else {})},
        },
        "drive": {
            "_type": "process", "address": "local:GeochemicalDriveProcess",
            "config": {"g_drive": float(drive_free_energy)}, "interval": 1.0,
            "inputs": {}, "outputs": {"drive_free_energy": ["env", "drive_chemical"]},
        },
        "fe_drive": {
            "_type": "process", "address": "local:GeochemicalDriveProcess",
            "config": {"g_drive": float(fe_drive_free_energy)}, "interval": 1.0,
            "inputs": {}, "outputs": {"drive_free_energy": ["env", "drive_fe_redox"]},
        },
        "free_energy_ledger": {
            "_type": "process", "address": "local:FreeEnergyLedgerProcess", "config": {"seconds_per_tick": dt},
            "interval": 1.0,
            "inputs": {"free_energy_in": ["budget", "free_energy_in"], "work": ["budget", "work"],
                       "dissipated": ["budget", "dissipated"], "energy_stored": ["budget", "energy_stored"]},
            "outputs": {p: ["ledger", p] for p in FREE_ENERGY_LEDGER_KEYS},
        },
        "env": {"electric_potential": float(electric_potential), "drive_chemical": float(drive_free_energy),
                "drive_fe_redox": float(fe_drive_free_energy), "temperature": 322.15, "catalyst_activity": 1.0},
        "boundary": {"permeability": float(permeability), "membrane_area": area},
        "individual": {"compartment_volume": volume_l},
        "budget": {**{p: 0.0 for p in _BUDGET_PORTS}, "pmf": 0.0},
        "ledger": {**{p: 0.0 for p in FREE_ENERGY_LEDGER_KEYS}, "free_energy_ledger_ok": 1.0},
        "emitter": {
            "_type": "step", "address": "local:RAMEmitter",
            "config": {"emit": {k: "float" for k in _WIRES}},
            "inputs": {k: list(v) for k, v in _WIRES.items()},
        },
    }
    # The declining-gradient scenario (og-05): a decline process only when it
    # declines — process-bigraph drops a 0.0 decline_rate config and would refill
    # EnvironmentalDeclineProcess's default 0.01 V/s.
    if float(decline_rate) > 0.0:
        doc["decline"] = {
            "_type": "process", "address": "local:EnvironmentalDeclineProcess",
            "config": {"v_start": float(electric_potential), "decline_rate": float(decline_rate) * dt,
                       "v_floor": float(gradient_floor)},
            "interval": 1.0, "inputs": {}, "outputs": {"electric_potential": ["env", "electric_potential"]},
        }
    # Mirror the class's drive into env/drive_free_energy for the emitter (one readout name across classes).
    doc["emitter"]["inputs"]["drive_free_energy"] = ["env", f"drive_{drive_key}"]
    return doc


# --------------------------------------------------------------------------- #
# Reducers (module-level, picklable)
# --------------------------------------------------------------------------- #
def _tail_mean(rows, key, frac=0.2):
    n = max(1, int(round(len(rows) * frac)))
    vals = [float(r.get(key, float("nan"))) for r in rows[-n:]]
    return sum(vals) / len(vals) if vals else float("nan")


def settled_net_power(rows) -> float:
    return _tail_mean(rows, "net_power")


def settled_internal_power(rows) -> float:
    return _tail_mean(rows, "internal_power")


def settled_external_power(rows) -> float:
    return _tail_mean(rows, "external_power")


def settled_maintenance_power(rows) -> float:
    return _tail_mean(rows, "maintenance_power")


def settled_leak_power(rows) -> float:
    return _tail_mean(rows, "leak_power")


def settled_autonomy(rows) -> float:
    return _tail_mean(rows, "autonomy")


def settled_charge_fraction(rows) -> float:
    return _tail_mean(rows, "energy_charge_fraction")


def settled_store_potential(rows) -> float:
    return _tail_mean(rows, "store_potential")


def capture_efficiency_final(rows) -> float:
    return float(rows[-1].get("capture_efficiency", float("nan"))) if rows else float("nan")


def free_energy_residual_max(rows) -> float:
    return float(rows[-1].get("free_energy_residual_max", float("nan"))) if rows else float("nan")


def second_law_margin_min(rows) -> float:
    return float(rows[-1].get("second_law_margin_min", float("nan"))) if rows else float("nan")


def dissipation_min(rows) -> float:
    return float(rows[-1].get("dissipation_min", float("nan"))) if rows else float("nan")


def free_energy_ledger_ok(rows) -> float:
    return float(rows[-1].get("free_energy_ledger_ok", 0.0)) if rows else float("nan")


PHASE6_REDUCERS = {
    "net_power": settled_net_power,
    "internal_power": settled_internal_power,
    "external_power": settled_external_power,
    "maintenance_power": settled_maintenance_power,
    "leak_power": settled_leak_power,
    "autonomy": settled_autonomy,
    "charge_fraction": settled_charge_fraction,
    "store_potential": settled_store_potential,
    "capture_efficiency": capture_efficiency_final,
    "free_energy_residual_max": free_energy_residual_max,
    "second_law_margin_min": second_law_margin_min,
    "dissipation_min": dissipation_min,
    "free_energy_ledger_ok": free_energy_ledger_ok,
}
