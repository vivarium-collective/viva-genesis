"""Gradient-only energy coupling — the matched null for study 35.

Does endergonic work DIRECTLY from the environmental gradient with NO carrier store
to buffer a gradient dip: useful work tracks the instantaneous drive, so when the
drive dips below the load the work falls immediately (no stored free energy to
spend). This is the matched gradient-only control for the thioester carrier cycle
(:class:`~viva_genesis.bioenergetics.thioester_cycle.ThioesterCarrierCycleProcess`),
seeing the SAME ``GeochemicalDriveProcess`` drive and the same load. The free-energy
ledger closes by construction (``budget_residual`` ~ 0): drive in == useful +
dissipated, nothing stored, no hidden inflow.
"""
from __future__ import annotations

from process_bigraph import Process

_KJ_IN = {"_type": "float", "_units": "kilojoule/mole"}
_KJ = {"_type": "overwrite[float]", "_units": "kilojoule/mole"}


class GradientOnlyWorkProcess(Process):
    """Direct gradient-to-work coupling with no carrier store (study-35 matched null)."""

    config_schema = {
        # Mirrors ThioesterCarrierCycleProcess activation throughput (same k_activate,
        # k_use basis + bond) so the two arms are matched in scale — the ONLY difference
        # is that this arm has no store: it activates and immediately uses in the same
        # step, so a drive dip below the bond cuts the work (nothing buffered).
        "k_activate": {"_type": "float", "_default": 0.2, "_units": "1/second"},
        "k_use": {"_type": "float", "_default": 0.2, "_units": "1/second"},
        "bond_energy_kjmol": {"_type": "float", "_default": 31.5, "_units": "kilojoule/mole"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._cum_useful = 0.0

    def inputs(self):
        return {"drive_free_energy": _KJ_IN, "load": _KJ_IN,
                "acetate": {"_type": "float", "_units": "molar"},
                "thiol": {"_type": "float", "_units": "molar"}}

    def outputs(self):
        return {
            "net_useful_work": _KJ,       # cumulative useful work (no store)
            "work_done": _KJ,
            "budget_residual": _KJ,       # per-step ledger closure (~0, direct coupling)
            "acetyl_thioester": {"_type": "overwrite[float]", "_units": "molar"},  # 0: no carrier store
        }

    def initial_state(self):
        return {"drive_free_energy": 0.0, "load": 0.0, "acetate": 1.0e-3, "thiol": 1.0e-3}

    def update(self, state, interval):
        drive = max(0.0, float(state.get("drive_free_energy", 0.0)))
        load = max(0.0, float(state.get("load", 0.0)))
        acetate = max(0.0, float(state.get("acetate", 0.0)))
        thiol = max(0.0, float(state.get("thiol", 0.0)))
        bond = float(self.config["bond_energy_kjmol"])
        k_act = float(self.config["k_activate"])
        # Direct charge-and-immediately-use, NO store. Gated by the drive clearing the
        # bond, exactly like the carrier's activation — but with no buffered pool, so
        # when the drive dips below the bond the useful work drops to zero at once.
        if drive >= bond:
            turnover = k_act * min(acetate, thiol) * interval
        else:
            turnover = 0.0
        useful_per = min(load, bond)
        useful_work = turnover * useful_per
        dissipated = turnover * (bond - useful_per)
        energy_in = turnover * bond
        budget_residual = energy_in - (useful_work + dissipated)   # 0 by construction
        self._cum_useful += useful_work
        return {
            "net_useful_work": self._cum_useful,
            "work_done": self._cum_useful,
            "budget_residual": budget_residual,
            "acetyl_thioester": 0.0,
        }
