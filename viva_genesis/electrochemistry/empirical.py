"""The ``empirical`` carbon-fixation class — og-01's kinetics on the Phase-2 face.

:class:`EmpiricalCarbonFixationProcess` is og-01's lab-calibrated
:class:`~viva_genesis.protometabolism.carbon_fixation.CarbonFixationProcess`
(the same rate law, the same Preiner / Hudson calibration, the same additive
product deltas and open-flow washout — ``update`` delegates to the parent)
adapted to the ``carbon_fixation`` face so it can be swept against the
electrochemical classes:

* an optional ``ni_fraction`` input scales the catalyst activity with the same
  Ni gain the Butler-Volmer class uses (Preiner-2020: awaruite > magnetite >
  greigite), so the Ni/Fe axis of the Phase-2 study reaches this class too;
* it publishes the **failure-mode attribution** from its own gating factors —
  the headroom in each multiplicative gate: ``1 − feasible`` (thermodynamic,
  the eQuilibrator ΔG' gate), ``1 − drive(pmf)`` (electrical: the delivered
  proton-motive force, which carries the circuit-derived gradient efficiency
  and the chemiosmotic back-pressure), ``1 − catalyst × Ni gain`` (catalytic)
  and ``1 − availability(H2, CO2)`` (transport). Unlike the Butler-Volmer
  partition these are independent headrooms, not shares of one budget — that
  difference is exactly what the Phase-2 gate tests;
* it publishes the electron-balance witnesses (``electron_flux`` =
  ``carbon_electron_flux`` = the electrons implied by the product rates;
  ``her_electron_flux`` = 0; ``faradaic_efficiency`` = 1) so the same charge
  ledger audits it. The empirical class has no competing hydrogen evolution,
  so its faradaic efficiency is 1 by construction — stated, not hidden.
"""

from __future__ import annotations

from ..protometabolism.carbon_fixation import CarbonFixationProcess, _K_RATE, _YIELD_MAX
from .butler_volmer import LIMITATION_CODES, N_ELECTRONS, limitation_label, ni_activity_gain

_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_OVW = {"_type": "overwrite[float]", "_units": "dimensionless"}
_OVW_RATE = {"_type": "overwrite[float]", "_units": "mole/second"}


class EmpiricalCarbonFixationProcess(CarbonFixationProcess):
    """og-01's lab-calibrated gated kinetics, adapted to the carbon_fixation
    face: Ni-scaled catalyst activity, the four loss headrooms + limitation
    code, and the electron-balance witnesses (faradaic efficiency 1 — no
    competing hydrogen evolution in the empirical rate law)."""

    contract = dict(
        CarbonFixationProcess.contract,
        summary="og-01 empirical kinetics on the carbon_fixation face: Ni-scaled catalyst, loss headrooms, electron witnesses.",
        description=(
            CarbonFixationProcess.contract["description"]
            + " Phase-2 adapter: the catalyst activity is scaled by the Fe/Ni phase's Ni fraction "
            "(same gain as the Butler-Volmer class); the headroom of each gate is published as "
            "loss_thermodynamic (1 - feasible), loss_electrical (1 - drive(pmf)), loss_catalytic "
            "(1 - catalyst x Ni gain) and loss_transport (1 - availability), with the largest as "
            "limitation_code; electron_flux = carbon_electron_flux = electrons implied by the "
            "product rates (2 formate, 8 acetate, 10 pyruvate), her_electron_flux = 0 and "
            "faradaic_efficiency = 1 by construction."
        ),
        inputs={**CarbonFixationProcess.contract["inputs"],
                "ni_fraction": "Ni mole fraction of the Fe/Ni catalytic phase (dimensionless)"},
        outputs={**CarbonFixationProcess.contract["outputs"],
                 "loss_thermodynamic": "1 - feasible_formate", "loss_electrical": "1 - drive(pmf)",
                 "loss_catalytic": "1 - catalyst x Ni gain", "loss_transport": "1 - availability(H2, CO2)",
                 "limitation_code": "0 thermodynamic, 1 electrical, 2 catalytic, 3 transport",
                 "electron_flux": "electrons implied by the product rates (mole/second)",
                 "carbon_electron_flux": "same (mole/second)", "her_electron_flux": "0 (no H2 evolution)",
                 "faradaic_efficiency": "1 by construction"},
        references=CarbonFixationProcess.contract["references"] + ["altair2025carbon"],
    )

    config_schema = {
        **{k: dict(v, _provenance=v.get("_provenance", "calibrated")) for k, v in CarbonFixationProcess.config_schema.items()},
        "ni_gain": {"_type": "float", "_default": 3.0, "_units": "dimensionless", "_provenance": "hypothetical"},
        "ni_reference": {"_type": "float", "_default": 0.75, "_units": "dimensionless", "_provenance": "inferred"},
    }

    def inputs(self):
        return {**super().inputs(), "ni_fraction": _DIMLESS}

    def outputs(self):
        return {**super().outputs(),
                "loss_thermodynamic": _OVW, "loss_electrical": _OVW, "loss_catalytic": _OVW,
                "loss_transport": _OVW, "limitation_code": _OVW,
                "electron_flux": _OVW_RATE, "carbon_electron_flux": _OVW_RATE,
                "her_electron_flux": _OVW_RATE, "faradaic_efficiency": _OVW}

    def initial_state(self):
        return {**super().initial_state(), "ni_fraction": float(self.config["ni_reference"])}

    def ni_scale(self, ni_fraction: float) -> float:
        gain = float(self.config["ni_gain"])
        return ni_activity_gain(ni_fraction, gain) / ni_activity_gain(float(self.config["ni_reference"]), gain)

    def update(self, state, interval):
        x_ni = float(state.get("ni_fraction", self.config["ni_reference"]))
        cat_raw = max(float(state.get("catalyst_activity", 0.0)), 0.0)
        scaled = dict(state)
        scaled["catalyst_activity"] = cat_raw * self.ni_scale(x_ni)
        out = super().update(scaled, interval)

        g = self.gating_factors(scaled)
        gain = float(self.config["ni_gain"])
        cat_norm = min(cat_raw * ni_activity_gain(x_ni, gain) / ni_activity_gain(1.0, gain), 1.0)
        feasible = max(0.0, min(1.0, float(state.get("feasible_formate", 0.0))))
        losses = {"thermodynamic": 1.0 - feasible, "electrical": 1.0 - g["drive"],
                  "catalytic": 1.0 - cat_norm, "transport": 1.0 - g["avail"]}

        # electrons implied by the GROSS production rates (not the washed-out pool)
        electrons = 0.0
        for name, n_e in N_ELECTRONS.items():
            product = max(float(state.get(name, 0.0)), 0.0)
            headroom = max(0.0, 1.0 - product / _YIELD_MAX[name])
            feas = max(0.0, min(1.0, float(state.get(f"feasible_{name}", 0.0))))
            rate = _K_RATE[name] * g["cat"] * feas * g["drive"] * g["avail"] * g["t_window"] * headroom
            electrons += n_e * rate * g["vol"]
        out.update({
            "loss_thermodynamic": losses["thermodynamic"], "loss_electrical": losses["electrical"],
            "loss_catalytic": losses["catalytic"], "loss_transport": losses["transport"],
            "limitation_code": float(LIMITATION_CODES[limitation_label(losses, 1.0)]),
            "electron_flux": electrons, "carbon_electron_flux": electrons, "her_electron_flux": 0.0,
            "faradaic_efficiency": 1.0,
        })
        return out


__all__ = ["EmpiricalCarbonFixationProcess"]
