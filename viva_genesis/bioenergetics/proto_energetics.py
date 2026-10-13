"""Proto-energetics — an energy currency before modern pumping.

A central missing transition between a favourable geochemical gradient and a
living cell is the coupling of EXERGONIC to ENDERGONIC chemistry through a
transferable chemical **currency** — pre-ATP carriers such as thioesters, acyl
phosphates, polyphosphates or reduced metal centres (Buckel & Thauer 2013; de
Duve's thioester world). This stage sits BEFORE modern-style ion pumping (og-05):
it asks whether a primitive system can *capture environmental free energy into a
store it can spend later*, not merely run reactions in a favourable direction.

The model is explicit ENERGETIC BOOKKEEPING, not a favourable-direction fudge. A
carrier pool is **charged** by an exergonic geochemical drive at a coupling
efficiency, **discharged** to do endergonic work under a load, and bleeds energy
to spontaneous **hydrolysis / loss**. Every kilojoule is tracked in a FREE-ENERGY
LEDGER — input free energy = useful work delivered + currently stored in the pool
+ dissipated — so conservation of free energy is a contract invariant (the ledger
residual stays at machine precision), and the stage reports *what fraction of the
geochemical free energy becomes stored usable work* rather than assuming it does.

Two coupled processes (mirroring the campaign's other composites):

  - :class:`GeochemicalDriveProcess` — the sustained environmental free-energy
    supply (the vent's redox/geochemical disequilibrium), a drive ΔG in kJ/mol.
  - :class:`ProtoEnergyCurrencyProcess` — the currency bookkeeping: charge /
    discharge / hydrolysis of the carrier pool with the full free-energy ledger.

Deterministic and reproducible (no RNG); coarse-grained reduced kinetics, not a
wrapped MD/quantum-chemistry engine, and labelled as such.
"""
from __future__ import annotations

from process_bigraph import Process

_KJMOL = {"_type": "float", "_units": "kilojoule/mole"}
_KJL = {"_type": "float", "_units": "kilojoule/liter"}
_MOLAR = {"_type": "float", "_units": "molar"}
_DIMLESS = {"_type": "float", "_units": "dimensionless"}

# Representative high-energy bond free energies (|ΔG°'| of hydrolysis, kJ/mol) of
# the candidate primitive carriers — the "which coupling chemistry" axis. Thioester
# (acetyl-CoA-like) is the default carrier; acyl phosphate is higher-energy,
# polyphosphate lower. Values are textbook order-of-magnitude anchors.
CARRIER_BOND_KJMOL = {
    "thioester": 35.0,       # acetyl-CoA-like thioester (~31-43 kJ/mol)
    "acyl_phosphate": 43.0,  # e.g. acetyl phosphate / 1,3-BPG class
    "polyphosphate": 20.0,   # phosphoanhydride, lower per-bond
    "reduced_metal": 28.0,   # reduced Fe/Ni centre, effective transfer
}


class GeochemicalDriveProcess(Process):
    """The sustained environmental free-energy supply — the vent's geochemical /
    redox disequilibrium that an early system could tap. Writes a (optionally
    declining) exergonic drive free energy ΔG (kJ/mol) that the currency process
    couples to. Steady by default; a decline models the gradient waning so the
    store must carry the system through."""

    contract = {
        "summary": "Sustained environmental (geochemical) free-energy supply — an exergonic drive ΔG the proto-energy currency couples to.",
        "description": (
            "Writes drive_free_energy = max(g_floor, g_drive - decline_rate * t), the "
            "per-transfer free energy (kJ/mol) available from the vent's redox / geochemical "
            "disequilibrium (e.g. FeS-mediated redox, H2/CO2). The currency process can only "
            "charge a carrier whose bond this drive can clear — so the drive ΔG sets which "
            "carriers are chargeable, not just how fast."
        ),
        "inputs": {},
        "outputs": {"drive_free_energy": "exergonic environmental drive ΔG available this tick (kJ/mol)"},
        "assumptions": ["A controlled environmental supply (not a scripted upgrade of the system)."],
        "references": ["lane2010chemiosmotic", "buckel2013energy"],
    }

    config_schema = {
        "g_drive": {"_type": "float", "_default": 50.0, "_units": "kilojoule/mole"},
        "g_floor": {"_type": "float", "_default": 0.0, "_units": "kilojoule/mole"},
        "decline_rate": {"_type": "float", "_default": 0.0, "_units": "kilojoule/mole"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._g = float(self.config["g_drive"])

    def inputs(self):
        return {}

    def outputs(self):
        return {"drive_free_energy": {"_type": "overwrite[float]", "_units": "kilojoule/mole"}}

    def update(self, state, interval):
        self._g = max(float(self.config["g_floor"]),
                      self._g - float(self.config["decline_rate"]) * interval)
        return {"drive_free_energy": self._g}


class ProtoEnergyCurrencyProcess(Process):
    """A pre-ATP energy currency as explicit free-energy bookkeeping.

    A carrier pool (``carrier_pool`` molar, charged fraction tracked internally) is
    **charged** by the exergonic drive at ``coupling_efficiency`` — but only if the
    drive ΔG can clear the carrier's high-energy bond (a thermodynamic gate, so the
    drive axis has a real threshold, not just a rate) — **discharged** to do
    endergonic work at a rate set by ``load``, and bled by first-order
    **hydrolysis** (``loss_rate``). All flows feed a FREE-ENERGY LEDGER so that

        input free energy = useful work delivered + stored in the pool + dissipated

    holds to machine precision every tick (the free-energy-accounting invariant).
    Emits the carrier charge/discharge/loss fluxes (World view), the ledger shares
    (Mechanism view), and the derived scalars the stage grades on:
    ``energy_charge_fraction`` (is the currency maintained under load?) and
    ``energy_stored_work_fraction`` (what fraction of geochemical free energy became
    transferable usable work?). Deterministic reduced kinetics; not a wrapped engine."""

    contract = {
        "summary": "Energy-currency bookkeeping: an exergonic drive charges a transferable carrier that is discharged for endergonic work and lost to hydrolysis, under a conserved free-energy ledger.",
        "description": (
            "Coarse-grained, deterministic reduced kinetics (not a wrapped MD/quantum engine). "
            "A carrier pool is charged by the environmental drive at coupling_efficiency when the "
            "drive ΔG clears the carrier bond (soft thermodynamic gate), discharged to endergonic "
            "work under a load at discharge_efficiency, and bled by first-order hydrolysis. Input "
            "free energy drawn = charged mol x bond/coupling_efficiency; the uncoupled remainder, "
            "the discharge inefficiency and the hydrolysed bonds are dissipated; the rest is useful "
            "work or still stored. The ledger residual input-(work+stored+dissipated) is held at "
            "machine precision — free-energy accounting is the stage's conservation invariant."
        ),
        "inputs": {
            "drive_free_energy": "exergonic environmental drive ΔG available to tap (kJ/mol)",
            "coupling_efficiency": "fraction of tapped drive free energy coupled into the carrier bond (dimensionless 0-1)",
            "load": "endergonic work demand as a fraction of the carrier pool per tick (dimensionless)",
        },
        "outputs": {
            "energy_charge": "charged-carrier concentration (molar)",
            "energy_charge_fraction": "charged fraction of the carrier pool (dimensionless 0-1)",
            "energy_charge_flux": "carrier charging flux this tick (molar/tick)",
            "energy_discharge_flux": "carrier discharge-to-work flux this tick (molar/tick)",
            "energy_loss_flux": "carrier hydrolysis/loss flux this tick (molar/tick)",
            "energy_input": "cumulative input free energy drawn from the drive (kJ/liter)",
            "energy_work": "cumulative useful endergonic work delivered (kJ/liter)",
            "energy_stored": "free energy currently held in the charged pool (kJ/liter)",
            "energy_dissipated": "cumulative dissipated free energy (kJ/liter)",
            "energy_stored_work_fraction": "fraction of input free energy captured as transferable usable work ((work+stored)/input)",
            "energy_ledger_residual": "input-(work+stored+dissipated); the conservation witness (~0)",
        },
        "assumptions": [
            "Coarse-grained deterministic reduced kinetics (reproducible); not a wrapped engine.",
            "A carrier bond of fixed free energy (bond_free_energy); charging needs the drive ΔG to clear it (thermodynamic gate).",
            "Capturing free energy into a transferable store is the transition — not merely a favourable reaction direction.",
        ],
        "math": [
            "gate = clip((drive - bond)/gate_width + 0.5, 0, 1)",
            "J_charge = min(k_charge*free*gate*dt, free);  dG_in = J_charge*bond/eta;  dG_store = J_charge*bond",
            "J_discharge = min(charge, load*pool*dt);  dG_work = J_discharge*bond*deff",
            "J_loss = loss_rate*charge*dt (capped);  dG_loss = J_loss*bond",
            "input = work + stored + dissipated   (free-energy ledger invariant)",
        ],
        "symbols": {
            "bond": "carrier high-energy bond free energy (kJ/mol)", "eta": "coupling efficiency",
            "deff": "discharge efficiency", "free": "uncharged carrier (molar)", "pool": "carrier_pool",
        },
        "references": ["buckel2013energy", "lane2010chemiosmotic"],
    }

    config_schema = {
        "carrier": {"_type": "string", "_default": "thioester"},                        # which primitive carrier
        "bond_free_energy": {"_type": "float", "_default": 0.0, "_units": "kilojoule/mole"},  # 0 -> look up from carrier
        "carrier_pool": {"_type": "float", "_default": 1.0e-3, "_units": "molar"},       # total carrier (charged+free)
        "coupling_efficiency": {"_type": "float", "_default": 0.6, "_units": "dimensionless"},
        "loss_rate": {"_type": "float", "_default": 0.05, "_units": "dimensionless"},    # first-order hydrolysis / tick
        "load": {"_type": "float", "_default": 0.20, "_units": "dimensionless"},         # endergonic demand (frac pool / tick)
        "k_charge": {"_type": "float", "_default": 0.6, "_units": "dimensionless"},      # charging rate constant / tick
        "discharge_efficiency": {"_type": "float", "_default": 0.85, "_units": "dimensionless"},
        "gate_width": {"_type": "float", "_default": 10.0, "_units": "kilojoule/mole"},  # soft thermodynamic-gate width
        "charge0": {"_type": "float", "_default": 0.0, "_units": "molar"},               # initial charged carrier
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        bond = float(self.config["bond_free_energy"])
        if bond <= 0.0:
            bond = CARRIER_BOND_KJMOL.get(str(self.config["carrier"]), 35.0)
        self._bond = bond
        self._pool = float(self.config["carrier_pool"])
        self._charge = min(max(float(self.config["charge0"]), 0.0), self._pool)
        # Cumulative free-energy ledger (kJ/liter).
        self._in = 0.0
        self._work = 0.0
        self._diss = 0.0

    def inputs(self):
        return {"drive_free_energy": _KJMOL, "coupling_efficiency": _DIMLESS, "load": _DIMLESS}

    def outputs(self):
        return {
            "energy_charge": {"_type": "overwrite[float]", "_units": "molar"},
            "energy_charge_fraction": {"_type": "overwrite[float]", "_units": "dimensionless"},
            "energy_charge_flux": {"_type": "overwrite[float]", "_units": "molar"},
            "energy_discharge_flux": {"_type": "overwrite[float]", "_units": "molar"},
            "energy_loss_flux": {"_type": "overwrite[float]", "_units": "molar"},
            "energy_input": {"_type": "overwrite[float]", "_units": "kilojoule/liter"},
            "energy_work": {"_type": "overwrite[float]", "_units": "kilojoule/liter"},
            "energy_stored": {"_type": "overwrite[float]", "_units": "kilojoule/liter"},
            "energy_dissipated": {"_type": "overwrite[float]", "_units": "kilojoule/liter"},
            "energy_stored_work_fraction": {"_type": "overwrite[float]", "_units": "dimensionless"},
            "energy_ledger_residual": {"_type": "overwrite[float]", "_units": "kilojoule/liter"},
        }

    def initial_state(self):
        # Deliberately do NOT seed the input-port stores (drive_free_energy,
        # coupling_efficiency, load): the composite's env store provides them, and
        # seeding here would clobber a wired 0.0 (process-bigraph drops a falsy
        # config override — see og-07), masking the no-coupling ablation.
        return {}

    def update(self, state, interval):
        dt = float(interval)
        drive = max(float(state.get("drive_free_energy", 0.0)), 0.0)
        eta = min(max(float(state.get("coupling_efficiency", self.config["coupling_efficiency"])), 0.0), 1.0)
        load = max(float(state.get("load", self.config["load"])), 0.0)

        bond = self._bond
        pool = self._pool
        charge = self._charge
        free = max(pool - charge, 0.0)

        # Thermodynamic gate: the drive ΔG must clear the carrier bond to charge it
        # (a weak drive cannot charge a high-energy carrier). Soft ramp of width
        # gate_width centred on the bond energy.
        gw = max(float(self.config["gate_width"]), 1e-9)
        gate = (drive - bond) / gw + 0.5
        gate = 0.0 if gate < 0.0 else (1.0 if gate > 1.0 else gate)

        # Charging: first-order in free carrier, gated by drive feasibility and the
        # coupling efficiency (an inefficient coupling charges more slowly).
        kc = max(float(self.config["k_charge"]), 0.0)
        j_charge = kc * free * gate * eta * dt
        if j_charge > free:
            j_charge = free
        if j_charge < 0.0:
            j_charge = 0.0

        # Discharge to endergonic work: bounded by the endergonic demand and the
        # charged pool actually present.
        demand = load * pool * dt
        j_discharge = demand if demand < charge else charge
        if j_discharge < 0.0:
            j_discharge = 0.0

        # First-order hydrolysis of what remains after discharge.
        rem = charge - j_discharge
        j_loss = float(self.config["loss_rate"]) * charge * dt
        if j_loss > rem:
            j_loss = rem
        if j_loss < 0.0:
            j_loss = 0.0

        # --- free-energy ledger (kJ/liter) ---------------------------------
        # Charging draws bond/eta of input free energy per charged mole (eta stored,
        # the uncoupled remainder dissipated).
        dG_in = j_charge * bond / eta if eta > 1e-9 else 0.0
        if eta <= 1e-9:
            j_charge = 0.0  # no coupling -> nothing captured
        dG_store = j_charge * bond
        dG_charge_waste = dG_in - dG_store
        deff = min(max(float(self.config["discharge_efficiency"]), 0.0), 1.0)
        dG_work = j_discharge * bond * deff
        dG_discharge_waste = j_discharge * bond * (1.0 - deff)
        dG_loss = j_loss * bond

        self._charge = charge + j_charge - j_discharge - j_loss
        if self._charge < 0.0:
            self._charge = 0.0
        elif self._charge > pool:
            self._charge = pool
        self._in += dG_in
        self._work += dG_work
        self._diss += dG_charge_waste + dG_discharge_waste + dG_loss

        stored = self._charge * bond
        charge_frac = self._charge / pool if pool > 0 else 0.0
        stored_work_frac = (self._work + stored) / self._in if self._in > 1e-30 else 0.0
        residual = self._in - (self._work + stored + self._diss)

        return {
            "energy_charge": self._charge,
            "energy_charge_fraction": charge_frac,
            "energy_charge_flux": j_charge,
            "energy_discharge_flux": j_discharge,
            "energy_loss_flux": j_loss,
            "energy_input": self._in,
            "energy_work": self._work,
            "energy_stored": stored,
            "energy_dissipated": self._diss,
            "energy_stored_work_fraction": stored_work_frac,
            "energy_ledger_residual": residual,
        }


def currency_state(proc: "ProtoEnergyCurrencyProcess") -> dict:
    """Snapshot of the currency bookkeeping for the viz — every value a real ledger
    state. Returns ``{charge, pool, bond, input, work, stored, dissipated}``."""
    if getattr(proc, "_pool", None) is None:
        return {}
    return {"charge": proc._charge, "pool": proc._pool, "bond": proc._bond,
            "input": proc._in, "work": proc._work,
            "stored": proc._charge * proc._bond, "dissipated": proc._diss}
