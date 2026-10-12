"""Module C (coupling) — stoichiometric proton budget with chemiosmotic back-pressure.

Turns the one-way "gradient drives reduction" gate (``CarbonFixationProcess``'s
``drive(pmf)`` term) into a **conserved proton economy**. The geochemical pH
gradient no longer just *gates* fixation — it is a finite reservoir that fixation
*spends*:

  d(reservoir)/dt = supply  −  protons_per_carbon · carbon_flux  −  leak · reservoir
                    └ geochem  └ chemiosmotic work (H+ translocated per C fixed)  └ passive dissipation

The effective (loaded) proton-motive force sags with the reservoir's state of
charge, exactly like a battery's terminal voltage under load:

  pmf_loaded = pmf_open · charge,   charge = reservoir / capacity ∈ [0, 1]

Because ``CarbonFixationProcess`` reads this loaded pmf, the loop closes: fast
fixation draws the reservoir down → pmf_loaded sags → ``drive(pmf)`` falls →
fixation throttles itself. The system settles at a **loaded steady state** with
``pmf_loaded < pmf_open`` while carbon is being fixed, and the gradient recovers
toward open-circuit once the products saturate and the load falls away. Remove
the geochemical supply and both the reservoir and the fixation collapse.

This is the "the gradient is *spent* doing work" step — the origin of energy
conservation by chemiosmosis, not merely a gradient that happens to correlate
with reduction.

Provenance: ``lane2010chemiosmotic`` + ``lane2012origin`` (natural proton
gradients as LUCA's power source), ``sojo2014bioenergetic`` (leaky-barrier
bioenergetics + back-pressure), ``herschy2014originreactor`` (a bench vent
reactor whose CO2 reduction is *driven by and consumes* the imposed gradient),
``buckel2013energy`` + ``weiss2016physiology`` (the H+-per-carbon translocation
stoichiometry of the ancient Wood–Ljungdahl / Rnf–Ech bioenergetic core).
"""
from __future__ import annotations

from process_bigraph import Process

_V = {"_type": "float", "_units": "volt"}
_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_MOL = {"_type": "float", "_units": "mole"}
_MOLS = {"_type": "float", "_units": "mole/second"}


class ProtonBudgetProcess(Process):
    """Conserved proton reservoir coupling the pH-gradient source to carbon
    fixation with chemiosmotic back-pressure.

    Reads the open-circuit proton-motive force (what the geochemical ΔpH could
    supply) and the carbon-fixation flux (the load), integrates the proton
    reservoir under geochemical supply − stoichiometric draw − leak, and emits
    the **loaded** pmf (sagging with state of charge) plus the budget sensors.
    All outputs are overwrite sensors — the current state of the proton economy,
    not accumulating pools (the reservoir itself is integrated internally)."""

    contract = {
        "summary": "Conserved proton budget: the pH gradient is a finite reservoir that carbon fixation spends, with the loaded pmf sagging under load (chemiosmotic back-pressure).",
        "description": (
            "Integrates a proton reservoir d(R)/dt = supply - protons_per_carbon * "
            "carbon_flux - leak * R (capped at capacity), and outputs the LOADED "
            "proton-motive force pmf_loaded = pmf_open * (R / capacity). Carbon fixation "
            "reads pmf_loaded, so drawing the reservoir down throttles fixation "
            "(respiratory-control back-pressure); the system settles at a loaded steady "
            "state with pmf_loaded < pmf_open while carbon is fixed, and relaxes toward "
            "open-circuit as the load falls. Remove supply and both collapse. All outputs "
            "are overwrite sensors; the reservoir is integrated internally."
        ),
        "inputs": {
            "pmf_open": "open-circuit proton-motive force from the geochemical gradient (volt)",
            "carbon_flux": "net organic-carbon fixation rate — the load (mole/second)",
        },
        "outputs": {
            "pmf": "loaded (back-pressured) proton-motive force fixation actually sees (volt)",
            "charge_state": "reservoir state of charge R/capacity (dimensionless, 0-1)",
            "proton_reservoir": "usable proton imbalance currently stored (mole)",
            "proton_draw": "protons spent by fixation this instant = protons_per_carbon * carbon_flux (mole/second)",
            "proton_supply": "protons delivered by the geochemical gradient (mole/second)",
        },
        "assumptions": [
            "pmf_loaded = pmf_open * state-of-charge (battery terminal-voltage analogy).",
            "protons_per_carbon H+ translocated down the gradient per carbon fixed (Wood-Ljungdahl/Rnf-Ech bioenergetic stoichiometry).",
            "Steady geochemical proton supply from serpentinization; first-order passive leak.",
        ],
        "math": [
            "dR/dt = supply - protons_per_carbon * carbon_flux - leak * R",
            "pmf_loaded = pmf_open * clip(R / capacity, 0, 1)",
        ],
        "symbols": {
            "R": "proton reservoir (mol)", "supply": "geochemical proton supply (mol/s)",
            "leak": "passive dissipation rate (1/s)", "protons_per_carbon": "H+ spent per C fixed",
        },
        "references": [
            "lane2010chemiosmotic", "lane2012origin", "sojo2014bioenergetic",
            "herschy2014originreactor", "buckel2013energy", "weiss2016physiology",
        ],
    }

    config_schema = {
        # H+ translocated down the gradient per carbon fixed — the chemiosmotic
        # work. ~2 brackets the Wood-Ljungdahl / Rnf-Ech bioenergetic cost.
        "protons_per_carbon": {"_type": "float", "_default": 2.0, "_units": "dimensionless"},
        # Geochemical proton delivery (serpentinization-driven alkalinity), mol/s.
        "supply_rate": {"_type": "float", "_default": 0.055, "_units": "mole/second"},
        # Usable proton-imbalance capacity of the barrier region, mol. Buffers the
        # transient draw so fixation loads the gradient (~40% sag) rather than
        # draining it to collapse.
        "reservoir_capacity": {"_type": "float", "_default": 0.30, "_units": "mole"},
        # Passive first-order dissipation of the stored gradient, 1/s.
        "leak_rate": {"_type": "float", "_default": 0.12, "_units": "1/second"},
        # Fraction of capacity the reservoir starts charged to (1.0 = open-circuit).
        "initial_charge": {"_type": "float", "_default": 1.0, "_units": "dimensionless"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        cap = float(self.config["reservoir_capacity"])
        self._reservoir = max(0.0, min(1.0, float(self.config["initial_charge"]))) * cap

    def inputs(self):
        return {"pmf_open": _V, "carbon_flux": _MOLS}

    def outputs(self):
        return {
            "pmf": {"_type": "overwrite[float]", "_units": "volt"},
            "charge_state": {"_type": "overwrite[float]", "_units": "dimensionless"},
            "proton_reservoir": {"_type": "overwrite[float]", "_units": "mole"},
            "proton_draw": {"_type": "overwrite[float]", "_units": "mole/second"},
            "proton_supply": {"_type": "overwrite[float]", "_units": "mole/second"},
        }

    def initial_state(self):
        return {"pmf_open": 0.0, "carbon_flux": 0.0}

    def update(self, state, interval):
        pmf_open = max(float(state.get("pmf_open", 0.0)), 0.0)
        carbon_flux = max(float(state.get("carbon_flux", 0.0)), 0.0)

        cap = max(float(self.config["reservoir_capacity"]), 1e-12)
        n_h = max(float(self.config["protons_per_carbon"]), 0.0)
        supply = max(float(self.config["supply_rate"]), 0.0)
        leak = max(float(self.config["leak_rate"]), 0.0)

        draw = n_h * carbon_flux                                   # mol H+/s spent fixing C
        d_res = (supply - draw - leak * self._reservoir) * interval
        self._reservoir = min(cap, max(0.0, self._reservoir + d_res))

        charge = self._reservoir / cap                            # state of charge 0..1
        pmf_loaded = pmf_open * charge                            # terminal voltage sag

        return {
            "pmf": pmf_loaded,
            "charge_state": charge,
            "proton_reservoir": self._reservoir,
            "proton_draw": draw,
            "proton_supply": supply,
        }
