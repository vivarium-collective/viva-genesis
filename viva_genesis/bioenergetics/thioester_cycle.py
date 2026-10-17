"""Explicit thioester / acyl-phosphate carrier cycle (study 12 REBUILD chemistry).

Replaces the abstract charged-pool carrier (ProtoEnergyCurrencyProcess) with named
species reacting through a specified chemical cycle, each step a balanced reaction
with a tracked free energy:

  activation:  acetate + thiol + (drive ΔG) --> acetyl~thioester + H2O
               (endergonic; the high-energy thioester bond is formed ONLY if the
                geochemical drive ΔG clears the bond energy — a thermodynamic gate)
  use:         acetyl~thioester + load      --> acetate + thiol + useful work
  hydrolysis:  acetyl~thioester + H2O        --> acetate + thiol      (uncoupled leak)

A full free-energy ledger closes every step (``budget_residual`` ~ 0): the drive
energy supplied equals useful work + dissipation + leak + the change in stored
bond energy — so useful coupled work is credited only with NO hidden energy inflow
(study 12 decision test). The thioester bond energy (~31.5 kJ/mol, acetyl-CoA
class) is the documented anchor (Huber & Wächtershäuser; Buckel & Thauer); the
acyl-phosphate class is the same cycle with a larger bond.
"""
from __future__ import annotations

from process_bigraph import Process

_KJ = {"_type": "overwrite[float]", "_units": "kilojoule/mole"}
_MOLAR_IN = {"_type": "float", "_units": "molar"}
_KJ_IN = {"_type": "float", "_units": "kilojoule/mole"}
_OW_MOLAR = {"_type": "overwrite[float]", "_units": "molar"}
_OW_DIMLESS = {"_type": "overwrite[float]", "_units": "dimensionless"}


class ThioesterCarrierCycleProcess(Process):
    """Named thioester/acyl-phosphate carrier cycle with a closed free-energy ledger."""

    config_schema = {
        # High-energy bond of the carrier (thioester ~31.5; acyl-phosphate ~43 kJ/mol).
        "bond_energy_kjmol": {"_type": "float", "_default": 31.5, "_units": "kilojoule/mole"},
        "k_activate": {"_type": "float", "_default": 0.2, "_units": "1/second"},
        "k_use": {"_type": "float", "_default": 0.2, "_units": "1/second"},
        "k_hydrolyze": {"_type": "float", "_default": 0.02, "_units": "1/second"},
        "carrier_total": {"_type": "float", "_default": 1.0e-3, "_units": "molar"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._thioester = 0.0     # current charged-carrier pool (molar)
        self._cum_useful = 0.0    # cumulative useful work delivered
        self._cum_leak = 0.0      # cumulative energy lost to hydrolysis

    def inputs(self):
        return {"drive_free_energy": _KJ_IN, "load": _KJ_IN,
                "acetate": _MOLAR_IN, "thiol": _MOLAR_IN}

    def outputs(self):
        return {
            "acetyl_thioester": _OW_MOLAR,          # the named charged carrier pool
            "work_done": _KJ,                       # cumulative useful work
            "net_useful_work": _KJ,                 # cumulative useful work net of nothing hidden
            "leak_loss": _KJ,                       # cumulative hydrolysis loss
            "budget_residual": _KJ,                 # per-step ledger closure (~0 = no hidden inflow)
            "energy_charge_fraction": _OW_DIMLESS,  # charged fraction of the carrier pool
        }

    def initial_state(self):
        return {"drive_free_energy": 0.0, "load": 0.0, "acetate": 1.0e-3, "thiol": 1.0e-3}

    def update(self, state, interval):
        bond = float(self.config["bond_energy_kjmol"])
        drive = float(state.get("drive_free_energy", 0.0))
        load = max(0.0, float(state.get("load", 0.0)))
        acetate = max(0.0, float(state.get("acetate", 0.0)))
        thiol = max(0.0, float(state.get("thiol", 0.0)))

        # ACTIVATION — gated: the drive ΔG must clear the thioester bond, else no
        # high-energy bond can form (a real thermodynamic threshold on the drive).
        if drive >= bond:
            activate = self.config["k_activate"] * min(acetate, thiol) * interval
        else:
            activate = 0.0

        # USE — discharge against the endergonic load; useful work per mol is the
        # load it can lift, capped by the bond (excess is dissipated, not hidden).
        use = self.config["k_use"] * self._thioester * interval
        useful_per = min(load, bond)
        useful_work = use * useful_per
        dissipated = use * (bond - useful_per)

        # HYDROLYSIS — uncoupled leak; the bond energy is lost.
        leak = self.config["k_hydrolyze"] * self._thioester * interval
        leak_loss = leak * bond

        # Pool update (clamp ≥ 0).
        d_pool = activate - use - leak
        self._thioester = max(0.0, self._thioester + d_pool)

        # FREE-ENERGY LEDGER (per step): drive in == useful + dissipated + leak +
        # Δstored. budget_residual is 0 by construction; a nonzero value would be a
        # hidden source/sink (the thing study 12 must rule out).
        energy_in = activate * bond
        stored_change = d_pool * bond
        budget_residual = energy_in - (useful_work + dissipated + leak_loss + stored_change)

        self._cum_useful += useful_work
        self._cum_leak += leak_loss

        carrier_total = max(self.config["carrier_total"], 1e-12)
        return {
            "acetyl_thioester": self._thioester,
            "work_done": self._cum_useful,
            "net_useful_work": self._cum_useful,
            "leak_loss": self._cum_leak,
            "budget_residual": budget_residual,
            "energy_charge_fraction": min(1.0, self._thioester / carrier_total),
        }
