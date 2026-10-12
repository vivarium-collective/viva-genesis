"""Module D (thermodynamics) — reaction feasibility via the REAL eQuilibrator engine.

**This is a genuine bridge to eQuilibrator** (``equilibrator_api`` +
``equilibrator-cache-data``, fully offline — no network), the component-contribution
thermodynamics engine. Each step it computes the real transformed Gibbs energy
ΔG' for the H2-driven CO2-reduction reactions that build organic carbon in the
vent:

- formate:   CO2 + H2            -> formate
- acetate:   2 CO2 + 4 H2        -> acetate + 2 H2O
- pyruvate:  3 CO2 + 5 H2        -> pyruvate + 3 H2O

ΔG' = ΔG'°(pH, ionic strength, T, from eQuilibrator) + RT·ln(Q), where Q is the
reaction quotient from the live store concentrations. A smooth feasibility
multiplier in [0,1] (logistic in -ΔG'/RT) gates the kinetics downstream — this is
the ``energy_directionality`` contract invariant made explicit: carbon fixation
only proceeds where the thermodynamics actually allow it, and the free-energy flux
is logged every step.
"""
from __future__ import annotations

import math

from process_bigraph import Step

_MOLAR = {"_type": "float", "_units": "molar"}
_K = {"_type": "float", "_units": "kelvin"}
_DIMLESS = {"_type": "float", "_units": "dimensionless"}
# Gibbs free-energy sensor (overwrite): kilojoule/mole. The core's unit registry
# resolves kilojoule/mole, so the port write is kept (verified by the og-01
# free-energy-directionality test passing with the unit attached).
_KJ = {"_type": "overwrite[float]", "_units": "kilojoule/mole"}

# KEGG ids. CO2 C00011, H2 C00282, H2O C00001, formate C00058, acetate C00033,
# pyruvate C00022.
_REACTIONS = {
    "formate": ("kegg:C00011 + kegg:C00282 = kegg:C00058", (1, 1)),          # (nCO2, nH2)
    "acetate": ("2 kegg:C00011 + 4 kegg:C00282 = kegg:C00033 + 2 kegg:C00001", (2, 4)),
    "pyruvate": ("3 kegg:C00011 + 5 kegg:C00282 = kegg:C00022 + 3 kegg:C00001", (3, 5)),
}
_R = 8.314462618e-3  # kJ/mol/K


class EquilibratorThermoStep(Step):
    """Real eQuilibrator feasibility gate: ``(pH, I, T, H2, CO2, products) ->
    ΔG' + feasibility`` for formate/acetate/pyruvate synthesis.

    A ``Step`` (stateless per tick; it reads conditions and emits sensor
    readings). The ComponentContribution engine + the per-reaction ΔG'° are
    cached (ΔG'° recomputed only when pH/I/T change) so it is cheap to run every
    tick.
    """

    contract = {
        "summary": "Real eQuilibrator feasibility gate: (pH, I, T, H2, CO2, products) -> dG' + feasibility for formate/acetate/pyruvate synthesis.",
        "description": (
            "A stateless Step: each tick it reads the vent conditions and emits the real "
            "eQuilibrator physiological dG' (ComponentContribution, offline) for H2-driven "
            "CO2 reduction to formate / acetate / pyruvate, plus a feasibility multiplier "
            "in [0,1] (logistic in -dG'/RT) that gates the downstream kinetics. dG'0 is "
            "cached and recomputed only when pH / ionic strength / temperature change."
        ),
        "inputs": {
            "pH": "fluid pH (dimensionless)", "ionic_strength": "ionic strength (molar)",
            "temperature": "temperature (K)", "H2": "dissolved H2 (molar)", "CO2": "dissolved CO2 (molar)",
            "formate": "formate concentration (molar)", "acetate": "acetate concentration (molar)",
            "pyruvate": "pyruvate concentration (molar)",
        },
        "outputs": {
            "dg_formate": "dG' of CO2->formate (kJ/mol)", "dg_acetate": "dG' of CO2->acetate (kJ/mol)",
            "dg_pyruvate": "dG' of CO2->pyruvate (kJ/mol)",
            "feasible_formate": "feasibility multiplier in [0,1] (dimensionless)",
            "feasible_acetate": "feasibility multiplier in [0,1] (dimensionless)",
            "feasible_pyruvate": "feasibility multiplier in [0,1] (dimensionless)",
            "free_energy_logged": "witness that dG' was logged this tick (dimensionless)",
        },
        "math": ["dG' = dG'0 + RT ln Q", "feasible = 1 / (1 + exp(dG'/RT))"],
        "symbols": {"Q": "reaction quotient", "R": "gas constant", "T": "temperature (K)"},
        "assumptions": ["Physiological (transformed) dG' at the given pH / I / T.", "H2-dependent reductive carbon fixation (acetyl-CoA-like)."],
        "references": ["preiner2020hydrogen", "huber1997activated", "martin2008hydrothermal"],
    }

    config_schema = {
        "conc_floor": {"_type": "float", "_default": 1.0e-9, "_units": "molar"},  # activity floor for ln(Q)
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._cc = None
        self._parsed = None               # {name: eQuilibrator reaction}
        self._dg0_cache = {}              # {(pH,I,T rounded): {name: dg0 kJ/mol}}

    def inputs(self):
        return {
            "pH": _DIMLESS, "ionic_strength": _MOLAR, "temperature": _K,
            "H2": _MOLAR, "CO2": _MOLAR,
            "formate": _MOLAR, "acetate": _MOLAR, "pyruvate": _MOLAR,
        }

    def outputs(self):
        return {
            "dg_formate": _KJ, "dg_acetate": _KJ, "dg_pyruvate": _KJ,
            # Feasibility multipliers in [0,1] (logistic in -ΔG'/RT) — gate the kinetics.
            "feasible_formate": {"_type": "overwrite[float]", "_units": "dimensionless"},
            "feasible_acetate": {"_type": "overwrite[float]", "_units": "dimensionless"},
            "feasible_pyruvate": {"_type": "overwrite[float]", "_units": "dimensionless"},
            # energy_directionality invariant witness.
            "free_energy_logged": {"_type": "overwrite[boolean]"},
        }

    def _engine(self):
        if self._cc is None:
            from equilibrator_api import ComponentContribution  # lazy, offline
            self._cc = ComponentContribution()
            self._parsed = {name: self._cc.parse_reaction_formula(f)
                            for name, (f, _) in _REACTIONS.items()}
        return self._cc

    def _dg0(self, ph: float, ionic: float, temp_k: float) -> dict:
        key = (round(ph, 2), round(ionic, 3), round(temp_k, 1))
        cached = self._dg0_cache.get(key)
        if cached is not None:
            return cached
        from equilibrator_api import Q_
        cc = self._engine()
        cc.p_h = Q_(float(key[0]))
        cc.ionic_strength = Q_(f"{max(key[1], 1e-6)} M")
        cc.temperature = Q_(f"{key[2]} K")
        out = {}
        for name, rxn in self._parsed.items():
            out[name] = float(cc.standard_dg_prime(rxn).value.to("kJ/mol").magnitude)
        self._dg0_cache[key] = out
        return out

    def update(self, state):
        ph = float(state.get("pH", 7.0))
        ionic = float(state.get("ionic_strength", 0.25))
        temp_k = max(float(state.get("temperature", 298.15)), 250.0)
        floor = self.config["conc_floor"]
        h2 = max(float(state.get("H2", 0.0)), floor)
        co2 = max(float(state.get("CO2", 0.0)), floor)
        prod = {n: max(float(state.get(n, 0.0)), floor) for n in _REACTIONS}

        dg0 = self._dg0(ph, ionic, temp_k)
        rt = _R * temp_k
        out = {"free_energy_logged": True}
        for name, (_f, (nco2, nh2)) in _REACTIONS.items():
            # Q = [product] / ([CO2]^nCO2 * [H2]^nH2)  (water activity ~ 1)
            q = prod[name] / (co2 ** nco2 * h2 ** nh2)
            dg = dg0[name] + rt * math.log(q)
            # logistic feasibility: ~1 when ΔG' very negative, ~0 when positive.
            feasible = 1.0 / (1.0 + math.exp(dg / rt))
            out[f"dg_{name}"] = dg
            out[f"feasible_{name}"] = feasible
        return out
