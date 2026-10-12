"""Module A — serpentinization geochemistry via the REAL PHREEQC engine.

**This is a genuine bridge to USGS PHREEQC** (the IPhreeqc shared library, driven
through ``phreeqpython``), not a parameterized stand-in. Each step it runs a real
aqueous-speciation + mineral-equilibrium calculation on the vent fluid:

1. Build the ancient vent/ocean fluid at the current interface temperature.
2. Dissolve olivine — forsterite ``Mg2SiO4`` + fayalite ``Fe2SiO4`` — at a
   flow- and temperature-dependent reaction rate (the kinetic driver on top of
   the equilibrium chemistry; standard partial-equilibrium reactive-transport
   practice).
3. Equilibrate with the serpentinite assemblage — chrysotile + brucite +
   magnetite — so Mg/Fe partition into real minerals and the fluid goes
   alkaline and strongly reducing.
4. Read the genuine speciation outputs: pH, pe, **dissolved H2** (``species['H2']``
   — the reducing power that is the whole origins-of-life point), carbonate +
   hydroxide alkalinity, and the PHREEQC charge balance.

The redox + mineral set live in the vendored ``data/llnl.dat`` (LLNL thermo via
the USGS PHREEQC v3 distribution — see ``data/PROVENANCE.md``); the databases
shipped in the ``phreeqpython`` wheel lack the Fe-redox / H2 machinery.

This replaces the earlier :class:`~viva_genesis.geochemistry.serpentinization.SerpentinizationReproductionProcess`
(a tuned Gaussian source) as Module A of the og-00 Campaign-0 reactor. PHREEQC
conserves elements and charge by construction, which is what lets the composite
satisfy the ``mass_balance`` and ``charge_neutrality`` contract invariants.
"""
from __future__ import annotations

import math
from pathlib import Path

from process_bigraph import Process

_K = {"_type": "float", "_units": "kelvin"}
_MPS = {"_type": "float", "_units": "meter/second"}
_MOLS = {"_type": "float", "_units": "mole/second"}
_W = {"_type": "float", "_units": "watt"}
_MOLAR = {"_type": "float", "_units": "molar"}
_DIMLESS = {"_type": "float", "_units": "dimensionless"}

# Reaction enthalpy of serpentinization (exothermic) — ~ -300 kJ per mol of
# olivine reacted (order-of-magnitude literature value; drives the heat source).
_SERP_ENTHALPY_J_PER_MOL = 3.0e5


def _db_dir() -> Path:
    """Directory holding the vendored llnl.dat (inside this package)."""
    return Path(__file__).resolve().parent.parent / "data"


class PhreeqcSerpentinizationProcess(Process):
    """Real PHREEQC serpentinization source: ``(T, flow, DIC) -> H2 / alkalinity / heat``.

    Drives the genuine IPhreeqc engine every step. Emits the serpentinization
    *source* into the vent fluid as composable ``float`` deltas (H2, alkalinity,
    heat accumulate; a sibling transport process removes them by advection, so
    the vent fluid settles at source = sink), plus ``overwrite[float]`` sensor
    readings (instantaneous fluxes, pe, and the PHREEQC charge imbalance that
    the ``charge_neutrality`` invariant audits).
    """

    contract = {
        "summary": "Real PHREEQC serpentinization source: (T, flow, DIC) -> H2, alkalinity, heat.",
        "description": (
            "Drives the genuine USGS IPhreeqc engine every step over a peridotite "
            "assemblage (forsterite + fayalite + diopside with serpentine / brucite / "
            "magnetite / quartz). Emits the serpentinization source into the vent fluid "
            "as additive float deltas (H2, alkalinity, heat accumulate; a sibling "
            "transport process removes them, so the fluid settles at source = sink), "
            "plus overwrite sensors: instantaneous fluxes, redox pe, the equilibrium pH, "
            "and the PHREEQC charge imbalance the charge_neutrality invariant audits."
        ),
        "inputs": {
            "temperature": "vent fluid temperature (K)",
            "flow_velocity": "boundary flow speed (m/s)",
            "DIC": "dissolved inorganic carbon fed back from the vent fluid (molar)",
        },
        "outputs": {
            "H2": "dissolved H2 source delta (molar) - reducing power",
            "alkalinity": "alkalinity source delta (molar)",
            "heat": "serpentinization heat delta (W)",
            "H2_flux": "instantaneous H2 production rate (mol/s)",
            "alkalinity_flux": "instantaneous alkalinity production rate (mol/s)",
            "heat_flux": "instantaneous heat rate (W)",
            "pe": "redox potential pe (dimensionless)",
            "pH_eq": "PHREEQC equilibrium pH (dimensionless)",
            "charge_imbalance": "PHREEQC charge-balance residual (dimensionless, ~0)",
        },
        "assumptions": [
            "Partial equilibrium: a prescribed olivine dissolution rate feeds full PHREEQC speciation each step.",
            "Peridotite (olivine + diopside), not dunite, so Ca-OH buffering reaches the Lost City high-pH endmember.",
        ],
        "references": ["kelley2005serpentinite", "proskurowski2008abiogenic", "schwander2023serpentinization"],
    }

    config_schema = {
        "database": {"_type": "string", "_default": "llnl.dat"},
        # Olivine dissolution rate (mol olivine per unit flow-saturated reaction
        # progress, per second) at the optimal temperature and reference flow.
        "olivine_rate": {"_type": "float", "_default": 0.15, "_units": "dimensionless"},
        # Fe-olivine (fayalite) fraction of the dissolving olivine — the Fe(II)
        # oxidized into magnetite is what reduces water to H2.
        "fe_fraction": {"_type": "float", "_default": 0.25, "_units": "dimensionless"},
        # Pyroxene (diopside CaMgSi2O6) dissolved per mole of olivine — this makes
        # the reactant PERIDOTITE (olivine + pyroxene), not dunite. The Ca it
        # releases once Mg is consumed into serpentine/brucite is what drives the
        # fluid to the Lost City Ca-OH-rich, pH 9-11 endmember (vs the brucite
        # buffer ~pH 7-8 for olivine alone).
        "pyroxene_fraction": {"_type": "float", "_default": 0.5, "_units": "dimensionless"},
        # Serpentinization kinetic temperature window (K): activity peaks at
        # t_opt and falls off with t_width (reaction is sluggish when cold and
        # the serpentine phases are unstable when very hot).
        "t_opt": {"_type": "float", "_default": 315.0, "_units": "kelvin"},
        "t_width": {"_type": "float", "_default": 80.0, "_units": "kelvin"},
        "flow_ref": {"_type": "float", "_default": 1.0e-3, "_units": "meter/second"},
        # Geometric factor mapping the specific flux (mol/kgw x m/s) to an
        # absolute vent source rate (mol/s) — reactor cross-section / porosity.
        "flux_area": {"_type": "float", "_default": 60.0, "_units": "meter**2"},
        # Fraction of the serpentinization reaction enthalpy retained in the
        # local fluid parcel (the rest conducts into the rock). CALIBRATED to the
        # observed Lost City vent temperature (40-91 C) — the chemistry (H2, pH,
        # pe, charge balance) is emergent from PHREEQC; only this heat-partition
        # knob is tuned to the field thermal boundary condition.
        "heat_to_fluid_fraction": {"_type": "float", "_default": 8.0e-4, "_units": "dimensionless"},
        # Ancient vent-ocean fluid proxy (mol/kgw). Kept separate from modern
        # seawater on purpose (see the study's key_assumptions).
        "fluid_na": {"_type": "float", "_default": 0.5, "_units": "molar"},
        "fluid_cl": {"_type": "float", "_default": 0.556, "_units": "molar"},
        "fluid_mg": {"_type": "float", "_default": 0.052, "_units": "molar"},
        "fluid_ca": {"_type": "float", "_default": 0.01, "_units": "molar"},
        "fluid_fe": {"_type": "float", "_default": 5.0e-4, "_units": "molar"},
        "fluid_dic": {"_type": "float", "_default": 2.0e-3, "_units": "molar"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._pp = None  # lazily-built PhreeqPython instance (reused each step)

    def inputs(self):
        return {
            "temperature": _K,
            "flow_velocity": _MPS,
            # Dissolved inorganic carbon fed back from the vent fluid (coupling
            # port — a sibling could set this; defaults to the config fluid).
            "DIC": _MOLAR,
        }

    def outputs(self):
        return {
            # Accumulating pools (bare float deltas — compose additively).
            "H2": _MOLAR,
            "alkalinity": _MOLAR,
            "heat": _W,
            # Instantaneous sensors (current readings — overwrite semantics).
            "H2_flux": {"_type": "overwrite[float]", "_units": "mole/second"},
            "alkalinity_flux": {"_type": "overwrite[float]", "_units": "mole/second"},
            "heat_flux": {"_type": "overwrite[float]", "_units": "watt"},
            "pe": {"_type": "overwrite[float]", "_units": "dimensionless"},
            # Equilibrium pH of the serpentinized fluid (the Ca-OH buffer sets it)
            # — the transport process relaxes the vent outlet toward this.
            "pH_eq": {"_type": "overwrite[float]", "_units": "dimensionless"},
            # PHREEQC charge imbalance (eq/kgw) — audited by charge_neutrality.
            "charge_imbalance": {"_type": "overwrite[float]", "_units": "dimensionless"},
        }

    def initial_state(self):
        return {"temperature": 300.0, "flow_velocity": 1.0e-3, "DIC": self.config["fluid_dic"]}

    # -- engine ------------------------------------------------------------
    def _engine(self):
        """Build (once) and return the PhreeqPython instance bound to llnl.dat."""
        if self._pp is None:
            from phreeqpython import PhreeqPython  # lazy — real IPhreeqc bridge
            self._pp = PhreeqPython(database=self.config["database"],
                                    database_directory=_db_dir())
        return self._pp

    def _activity(self, temperature: float, flow_velocity: float) -> float:
        """Dimensionless 0..1 reaction driver: a Gaussian temperature window
        times a saturating flow dependence (water–rock-reaction limited)."""
        t_opt = self.config["t_opt"]
        t_width = max(self.config["t_width"], 1.0)
        temp_term = math.exp(-((temperature - t_opt) ** 2) / (2.0 * t_width ** 2))
        flow_ref = max(self.config["flow_ref"], 1e-12)
        flow_term = flow_velocity / (flow_velocity + flow_ref)
        return max(0.0, temp_term * flow_term)

    def _speciate(self, temperature_c: float, moles_olivine: float, dic: float) -> dict:
        """Run ONE real PHREEQC serpentinization calculation; return fluid state."""
        pp = self._engine()
        c = self.config
        sol = pp.add_solution({
            "units": "mol/kgw",
            "temp": max(0.0, min(temperature_c, 350.0)),
            "pH": 6.5,
            "Na": c["fluid_na"], "Cl": c["fluid_cl"], "Mg": c["fluid_mg"],
            "Ca": c["fluid_ca"], "Fe(2)": c["fluid_fe"],
            "C(4)": max(dic, 1e-9),
        })
        try:
            if moles_olivine > 0.0:
                fe = c["fe_fraction"]
                sol.add("Forsterite", moles_olivine * (1.0 - fe), "mol")
                sol.add("Fayalite", moles_olivine * fe, "mol")
                # Pyroxene makes it peridotite -> the Ca-OH high-pH endmember.
                diopside = moles_olivine * c["pyroxene_fraction"]
                if diopside > 0.0:
                    sol.add("Diopside", diopside, "mol")
                # Precipitate the serpentinite assemblage (quartz-undersaturated);
                # tremolite + diopside buffer the Ca-OH fluid to the field pH.
                sol.equalize(["Chrysotile", "Brucite", "Magnetite", "Tremolite", "Diopside"],
                             [0.0, 0.0, 0.0, 0.0, 0.0])
            sp = sol.species
            h2 = float(sp.get("H2", 0.0))                       # dissolved H2, mol/kgw
            oh = float(sp.get("OH-", 0.0))
            hco3 = float(sp.get("HCO3-", 0.0))
            co3 = float(sp.get("CO3-2", 0.0))
            hplus = float(sp.get("H+", 0.0))
            alk = max(0.0, oh + hco3 + 2.0 * co3 - hplus)       # eq/kgw (OH + carbonate)
            out = {
                "pH": float(sol.pH), "pe": float(sol.pe), "H2": h2, "alkalinity": alk,
                "charge": float(sol.total("charge")),
            }
        finally:
            sol.forget()  # release the PHREEQC solution slot (avoid leak over a long run)
        return out

    def update(self, state, interval):
        temperature_k = float(state["temperature"])
        flow = float(state["flow_velocity"])
        dic = float(state.get("DIC", self.config["fluid_dic"]))

        act = self._activity(temperature_k, flow)
        moles_olivine = self.config["olivine_rate"] * act * interval

        fluid = self._speciate(temperature_k - 273.15, moles_olivine, dic)

        # Specific flux (mol/kgw x m/s) -> absolute source rate (mol/s) via the
        # reactor geometric factor. H2/alkalinity are the reacted-fluid values.
        area = self.config["flux_area"]
        h2_flux = fluid["H2"] * flow * area
        alk_flux = fluid["alkalinity"] * flow * area
        # Exothermic reaction heat: (moles reacted / s) x enthalpy x the fraction
        # retained in the fluid parcel (calibrated to the field vent temperature).
        heat_flux = ((moles_olivine / max(interval, 1e-12))
                     * _SERP_ENTHALPY_J_PER_MOL * self.config["heat_to_fluid_fraction"])

        return {
            # Integrated source into the vent fluid (removed by transport).
            "H2": h2_flux * interval,
            "alkalinity": alk_flux * interval,
            "heat": heat_flux * interval,
            # Sensors.
            "H2_flux": h2_flux,
            "alkalinity_flux": alk_flux,
            "heat_flux": heat_flux,
            "pe": fluid["pe"],
            "pH_eq": fluid["pH"],
            "charge_imbalance": fluid["charge"],
        }
