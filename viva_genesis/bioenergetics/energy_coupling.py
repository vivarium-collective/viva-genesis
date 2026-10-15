"""Energy coupling inside a protocell — the five classes on the ``energy_coupling`` face (Phase 6).

Model Upgrade plan, Phase 6 (*proto-energetics*): the energy question is moved
INSIDE the individual. A protocell sitting in the vent wall has two free-energy
sources — the external ion gradient (the natural pmf, tapped only through the
membrane's leak: Sojo 2014, Lane & Martin 2010) and the chemical drive (H2/CO2
redox, Fe(II) disproportionation) delivered by substrate turnover that does NOT
need the leak — and may build an internal STORE it later spends. Every class
here publishes one per-individual POWER BUDGET (watt per cell) so that

    autonomy = internal_power / (internal_power + external_power)

is one readout across classes, and a :class:`~viva_genesis.ledger.FreeEnergyLedgerProcess`
can audit each the same way (``free_energy_in >= work + dissipated`` with the
store, exact to rounding every tick).

The classes differ STRUCTURALLY (what the store is, how it is charged and how it
leaks), which is what makes the model class an experimental factor rather than
a parameter:

* ``passive_gradient`` — the external tap only (no store, no machinery). The
  baseline every "internalization pays" comparison is made against.
* ``h_na_gradient_leaky_membrane`` — a pumped Na+/H+ ion-gradient store
  (capacitor-like potential ``n F pmf_max q``) charged by the chemical drive
  through a pump and leaking THROUGH THE MEMBRANE at ``P_Na = ratio x P_H`` —
  the Sojo tradeoff: the same leak that feeds the external tap drains the store.
* ``thioester_acyl_phosphate`` / ``polyphosphate`` — og-energy's chemical
  carriers as the internal store (phosphorylation-potential-like
  ``mu(q) = bond + RT ln(q/(1-q))``), charged by the chemical drive gated by the
  store potential, leaking by hydrolysis plus slow carrier permeation.
* ``fe_redox`` — a reduced-metal (Fe/Ni centre) store charged by the
  Fe(II)-disproportionation drive, leaking by re-oxidation plus Fe2+ permeation.

The threshold physics is thermodynamic, not fitted: a store can only deliver
the load's work (``load_free_energy``, e.g. a 30 kJ/mol synthesis step) once its
potential ``mu(q)`` clears it, so a weak or leaky coupling charges the store
below the load potential and pays maintenance for nothing — that is the
``internalization-pays`` threshold the Phase-6 study sweeps.

Units: everything is per individual in SI (W, J, mol, s); free energies in
kJ/mol on the ports (the campaign convention); concentrations molar. Every
config parameter declares its vg-data provenance class; the numbers live in
``viva_genesis/data/vg_data/energy_currencies.yaml``.
"""
from __future__ import annotations

import math

from process_bigraph import Process

F_KJ = 96.485          # kJ/mol per volt (Faraday)
F_C = 96485.33212      # C/mol
R_KJ = 8.314462618e-3  # kJ/mol/K

_V = {"_type": "float", "_units": "volt"}
_KJMOL = {"_type": "float", "_units": "kilojoule/mole"}
_MPS = {"_type": "float", "_units": "meter/second"}
_M2 = {"_type": "float", "_units": "meter**2"}
_LITER = {"_type": "float", "_units": "liter"}
_K = {"_type": "float", "_units": "kelvin"}
_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_MOLAR = {"_type": "float", "_units": "molar"}
_OW = {"_type": "overwrite[float]", "_units": "watt"}
_OJ = {"_type": "overwrite[float]", "_units": "joule"}
_OD = {"_type": "overwrite[float]", "_units": "dimensionless"}
_OKJ = {"_type": "overwrite[float]", "_units": "kilojoule/mole"}


def _cfg(default, units, provenance, **extra):
    return {"_type": "float", "_default": default, "_units": units, "_provenance": provenance, **extra}


# Shared config: the per-individual power budget's knobs. Zero-able knobs default
# to 0.0 (process-bigraph drops a 0.0 override and refills the default, so a
# knob a study may set to 0 must default to 0; see og-07).
_BASE_CONFIG = {
    # external ion gradient tap (needs leak)
    "proton_gradient_conc": _cfg(1.0e-6, "molar", "inferred"),          # delta[H+] across the membrane
    "external_capture_efficiency": _cfg(0.3, "dimensionless", "hypothetical"),
    # the chemical drive (does not need leak)
    "drive_turnover": _cfg(1.0e-21, "mole/second", "hypothetical"),     # substrate turnover per cell at full activity
    "coupling_activity": _cfg(0.0, "dimensionless", "hypothetical"),    # 0 = passive .. 1 = fully active (swept)
    "slip_fraction": _cfg(0.3, "dimensionless", "hypothetical"),        # uncoupled turnover (fully dissipated)
    # the internal store and its load
    "pool_conc": _cfg(1.0e-3, "molar", "hypothetical"),                 # store capacity per volume
    "bond_free_energy": _cfg(0.0, "kilojoule/mole", "inferred"),        # chemical carriers (class override)
    "load_free_energy": _cfg(30.0, "kilojoule/mole", "hypothetical"),   # the endergonic step the store must clear
    "draw_rate": _cfg(1.0e-3, "1/second", "hypothetical"),              # demand: store turnover per second
    "gate_width": _cfg(2.0, "kilojoule/mole", "inferred"),              # soft gate ~ RT
    # leak laws (class override)
    "hydrolysis_rate": _cfg(0.0, "1/second", "extrapolated"),           # chemical store decay
    "carrier_permeability_ratio": _cfg(0.0, "dimensionless", "hypothetical"),  # P_store / P_H
    "n_ions_per_transfer": _cfg(3.0, "dimensionless", "inferred"),      # ion store: ions per load transfer
    "pmf_max": _cfg(0.2, "volt", "inferred"),                           # ion store: potential at full charge
    "pump_efficiency": _cfg(0.6, "dimensionless", "inferred"),          # ion store: drive -> gradient
    # maintenance
    "maintenance_base": _cfg(1.0e-19, "watt", "hypothetical"),
    "maintenance_active": _cfg(5.0e-18, "watt", "hypothetical"),        # machinery upkeep at full activity
    "temperature": _cfg(322.15, "kelvin", "calibrated"),                # Phase-1 posterior example point
    "charge0": _cfg(0.0, "dimensionless", "hypothetical"),              # initial store charge fraction
    "seconds_per_tick": _cfg(1.0, "second", "inferred"),                # physical seconds per composite tick
}


class _EnergyCouplingBase(Process):
    """The shared per-individual power-budget engine; subclasses fix the store.

    Per tick (operator-split, with EXACT store free-energy differences so the
    ledger closes to rounding):

    1. external tap: ``G_flux = F P_H A dc pmf``; captured ``eta_ext`` of it as
       external work, the rest dissipated in the leak;
    2. charging: the chemical drive turns over ``a D`` mol/s; the coupled part
       ``(1-q) g_charge`` raises the store charge fraction q while the drive
       clears the store potential (``mu(q) <= dG_drive``, capped exactly), the
       slipped part is dissipated; ``in_chem = (coupled + slipped) dG_drive``;
    3. draw: ``k_draw q N g_draw`` mol/s leave the store; work per mole is
       ``min(mu, dG_load)`` (the load's step), the excess potential dissipated;
    4. leak: ``lambda q`` (class law) leaves the store, its free energy dissipated.
    """

    STORE = "none"   # "chemical" | "ionic" | "none"
    config_schema = dict(_BASE_CONFIG)

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        q0 = float(self.config["charge0"])
        # An uncoupled store rests at its equilibrium charge (E = 0 there), so the
        # ledger's zero initial store is exact.
        self._q = min(max(q0, 0.0), 1.0) if q0 > 0.0 else self._q_rest(float(self.config["temperature"]))

    # ---- ports ------------------------------------------------------------
    def inputs(self):
        return {"electric_potential": _V, "drive_free_energy": _KJMOL, "permeability": _MPS,
                "membrane_area": _M2, "compartment_volume": _LITER,
                "temperature": _K, "catalyst_activity": _DIMLESS}

    def outputs(self):
        out = {"free_energy_in": _OW, "external_power": _OW, "internal_power": _OW,
               "maintenance_power": _OW, "work": _OW, "dissipated": _OW, "leak_power": _OW,
               "net_power": _OW, "energy_stored": _OJ, "autonomy": _OD,
               "energy_charge_fraction": _OD, "store_potential": _OKJ}
        if self.STORE == "ionic":
            out["pmf"] = {"_type": "overwrite[float]", "_units": "volt"}
        return out

    def initial_state(self):
        # Do not seed the wired inputs (the composite's env / boundary stores own them).
        return {}

    # ---- store thermodynamics (class hooks) ---------------------------------
    def _rt(self, T):
        return R_KJ * T

    def _q_rest(self, T):
        """The store's equilibrium charge fraction (its free-energy minimum)."""
        return 0.0

    def _store_G(self, q, N, T):
        """Free energy of the store (J) above its equilibrium (resting) state — never negative."""
        return 0.0

    def _store_mu(self, q, T):
        """Store potential (kJ/mol) at charge fraction q."""
        return 0.0

    def _q_at_potential(self, mu, T):
        """Charge fraction whose potential equals ``mu`` (the exact charging cap)."""
        return 1.0

    def _leak_rate(self, P_H, A, V):
        """First-order leak of the store charge (1/s) — the class's leak law."""
        return 0.0

    def _charge_scale(self):
        """Drive free energy per unit of store charge: 1 for a chemical carrier
        (one turnover charges one carrier), ``pump_efficiency`` for an ion
        gradient (the pump converts drive to gradient at that efficiency)."""
        return 1.0

    # ---- update -------------------------------------------------------------
    @staticmethod
    def _gate(margin, width):
        g = margin / max(width, 1e-12) + 0.5
        return 0.0 if g < 0.0 else (1.0 if g > 1.0 else g)

    def update(self, state, interval):
        c = self.config
        dt = float(interval) * float(c["seconds_per_tick"])
        pmf = max(float(state.get("electric_potential", 0.0)), 0.0)
        dG_drive = max(float(state.get("drive_free_energy", 0.0)), 0.0)
        P_H = max(float(state.get("permeability", 0.0)), 0.0)
        A = max(float(state.get("membrane_area", 0.0)), 0.0)
        V_l = max(float(state.get("compartment_volume", 0.0)), 1e-30)
        V = V_l * 1.0e-3                                   # m^3
        T = float(state.get("temperature", c["temperature"]) or c["temperature"])
        cat = max(float(state.get("catalyst_activity", 1.0)), 0.0)
        a = min(max(float(c["coupling_activity"]), 0.0), 1.0)
        if self.STORE == "none":
            a = 0.0

        # 1. external tap through the leak (W)
        dc = float(c["proton_gradient_conc"]) * 1.0e3        # mol/m^3
        G_flux = F_C * P_H * A * dc * pmf
        eta_ext = min(max(float(c["external_capture_efficiency"]) * cat, 0.0), 1.0)
        external = eta_ext * G_flux
        diss_ext = G_flux - external
        in_ext = G_flux

        N = float(c["pool_conc"]) * V_l                      # mol of store capacity
        in_chem = work_int = diss_charge = diss_draw = diss_leak = 0.0
        q = self._q
        if self.STORE != "none" and N > 0.0:
            D = float(c["drive_turnover"]) * a * cat
            slip = min(max(float(c["slip_fraction"]), 0.0), 1.0)
            gw = float(c["gate_width"])
            # 2. charging, gated by the drive clearing the store potential
            mu0 = self._store_mu(q, T)
            g_c = self._gate(dG_drive - mu0, gw)
            j_c = D * (1.0 - slip) * (1.0 - q) * g_c * self._charge_scale()
            dq = min(j_c * dt / N, 1.0 - q)
            q_cap = self._q_at_potential(dG_drive, T)         # exact: mu(q1) <= dG_drive
            if q + dq > q_cap:
                dq = max(q_cap - q, 0.0)
            q1 = q + dq
            drive_consumed = (dq * N / max(self._charge_scale(), 1e-30)) + D * slip * dt
            in_chem = drive_consumed * dG_drive * 1.0e3       # J (kJ/mol -> J/mol)
            stored_gain = self._store_G(q1, N, T) - self._store_G(q, N, T)
            diss_charge = max(in_chem - stored_gain, 0.0)
            in_chem = stored_gain + diss_charge               # closes exactly
            # 3. draw to the load
            mu1 = self._store_mu(q1, T)
            g_d = self._gate(mu1 - float(c["load_free_energy"]), gw)
            dq_d = min(float(c["draw_rate"]) * q1 * g_d * dt, q1)
            q2 = q1 - dq_d
            released = self._store_G(q1, N, T) - self._store_G(q2, N, T)
            work_int = min(released, dq_d * N * float(c["load_free_energy"]) * 1.0e3)
            diss_draw = released - work_int
            # 4. leak (class law): first-order relaxation TOWARD the resting charge
            # (hydrolysis / re-oxidation / ion leak are reversible at equilibrium),
            # so the leak always lowers the store free energy.
            lam = self._leak_rate(P_H, A, V)
            q_rest = self._q_rest(T)
            dq_l = min(lam * max(q2 - q_rest, 0.0) * dt, max(q2 - q_rest, 0.0))
            q3 = q2 - dq_l
            diss_leak = self._store_G(q2, N, T) - self._store_G(q3, N, T)
            q = q3
        self._q = q
        E = self._store_G(q, N, T) if self.STORE != "none" else 0.0

        maintenance = float(c["maintenance_base"]) + (float(c["maintenance_active"]) * a if self.STORE != "none" else 0.0)
        internal = work_int / dt
        work = external + internal
        dissipated = diss_ext + (diss_charge + diss_draw + diss_leak) / dt
        free_energy_in = in_ext + in_chem / dt
        leak_power = diss_ext + diss_leak / dt
        tot = internal + external
        out = {
            "free_energy_in": free_energy_in,
            "external_power": external,
            "internal_power": internal,
            "maintenance_power": maintenance,
            "work": work,
            "dissipated": dissipated,
            "leak_power": leak_power,
            "net_power": work - maintenance,
            "energy_stored": E,
            "autonomy": (internal / tot) if tot > 0.0 else 0.0,
            "energy_charge_fraction": q,
            "store_potential": self._store_mu(q, T) if self.STORE != "none" else 0.0,
        }
        if self.STORE == "ionic":
            out["pmf"] = float(c["pmf_max"]) * q
        return out


# --------------------------------------------------------------------------- #
# store laws
# --------------------------------------------------------------------------- #
class _ChemicalStore(_EnergyCouplingBase):
    STORE = "chemical"

    def _q_rest(self, T):
        # mu(q_eq) = 0: bond + RT ln(q/(1-q)) = 0
        x = float(self.config["bond_free_energy"]) / self._rt(T)
        return 1.0 / (1.0 + math.exp(x)) if x < 60.0 else 0.0

    def _G_raw(self, q, N, T):
        q = min(max(q, 0.0), 1.0)
        ent = 0.0
        if 0.0 < q < 1.0:
            ent = q * math.log(q) + (1.0 - q) * math.log(1.0 - q)
        return N * (q * float(self.config["bond_free_energy"]) + self._rt(T) * ent) * 1.0e3

    def _store_G(self, q, N, T):
        # ideal-mixing free energy of the charged / uncharged pool, relative to its minimum
        return max(self._G_raw(q, N, T) - self._G_raw(self._q_rest(T), N, T), 0.0)

    def _store_mu(self, q, T):
        q = min(max(q, 1e-12), 1.0 - 1e-12)
        return float(self.config["bond_free_energy"]) + self._rt(T) * math.log(q / (1.0 - q))

    def _q_at_potential(self, mu, T):
        x = (mu - float(self.config["bond_free_energy"])) / self._rt(T)
        if x > 60.0:
            return 1.0
        if x < -60.0:
            return 0.0
        return 1.0 / (1.0 + math.exp(-x))

    def _leak_rate(self, P_H, A, V):
        return float(self.config["hydrolysis_rate"]) + float(self.config["carrier_permeability_ratio"]) * P_H * A / max(V, 1e-30)


class _IonicStore(_EnergyCouplingBase):
    STORE = "ionic"

    def _cap(self):
        return float(self.config["n_ions_per_transfer"]) * F_KJ * float(self.config["pmf_max"])  # kJ/mol at q = 1

    def _store_G(self, q, N, T):
        q = min(max(q, 0.0), 1.0)
        return N * self._cap() * 0.5 * q * q * 1.0e3

    def _store_mu(self, q, T):
        return self._cap() * min(max(q, 0.0), 1.0)

    def _q_at_potential(self, mu, T):
        cap = self._cap()
        return min(max(mu / cap, 0.0), 1.0) if cap > 0 else 0.0

    def _leak_rate(self, P_H, A, V):
        return float(self.config["carrier_permeability_ratio"]) * P_H * A / max(V, 1e-30)

    def _charge_scale(self):
        return float(self.config["pump_efficiency"])


# --------------------------------------------------------------------------- #
# the five classes
# --------------------------------------------------------------------------- #
_REFS = ["sojo2014bioenergetic", "lane2010chemiosmotic", "buckel2013energy"]


def _contract(summary, description, extra_assumptions=(), refs=_REFS):
    return {
        "summary": summary,
        "description": description,
        "inputs": {
            "electric_potential": "external ion gradient (natural pmf) across the membrane (volt)",
            "drive_free_energy": "chemical drive free energy per turnover (kJ/mol)",
            "permeability": "membrane H+ permeability (meter/second) — the leak",
            "membrane_area": "individual's membrane area (meter**2)",
            "compartment_volume": "individual's internal volume (liter)",
            "temperature": "temperature (kelvin)",
            "catalyst_activity": "catalyst availability scaling both the external capture and the drive turnover (0-1)",
        },
        "outputs": {
            "free_energy_in": "gross free energy drawn from the environment this tick (watt)",
            "external_power": "useful work from the passive external tap (watt)",
            "internal_power": "useful work drawn from the internal store (watt)",
            "maintenance_power": "upkeep: base + machinery x activity (watt)",
            "work": "external + internal useful work (watt)",
            "dissipated": "free energy dissipated this tick: uncaptured leak + charging drop + draw excess + store leak (watt)",
            "leak_power": "membrane-leak losses: uncaptured ion flux + store leak (watt)",
            "net_power": "work - maintenance (watt); the surplus the individual keeps",
            "energy_stored": "free energy held in the internal store (joule)",
            "autonomy": "internal / (internal + external) power (0-1) — per individual",
            "energy_charge_fraction": "store charge fraction q",
            "store_potential": "store potential mu(q) (kJ/mol)",
        },
        "assumptions": [
            "Per-individual SI power budget; coarse-grained deterministic kinetics (reproducible), not a wrapped engine.",
            "The external tap needs membrane leak (G_flux = F P_H A dc pmf); the chemical drive needs none.",
            "Work is delivered only when the store potential mu(q) clears the load free energy (soft gate ~RT).",
            *extra_assumptions,
        ],
        "math": [
            "G_flux = F P_H A dc pmf;  external = eta_ext G_flux",
            "charge: dq = a D (1-slip)(1-q) g(dG_drive - mu(q)) dt / N, capped at mu(q1) = dG_drive",
            "draw: dq_d = k_draw q g(mu(q) - dG_load) dt;  work = min(G(q1)-G(q2), N dq_d dG_load)",
            "leak: dq_l = lambda(P_H) q dt;  in = work + dissipated + dE (exact)",
            "autonomy = internal / (internal + external)",
        ],
        "references": list(refs),
    }


class PassiveGradientCouplingProcess(_EnergyCouplingBase):
    """``passive_gradient``: the natural external gradient tapped through the
    leak, no internal store and no machinery — the baseline every
    internalization comparison is made against (autonomy = 0 by construction)."""

    STORE = "none"
    contract = _contract(
        "Passive gradient coupling: the external pmf tapped through the membrane leak; no store, no machinery.",
        "The individual captures external_capture_efficiency of the ion-flux free energy F P_H A dc pmf "
        "as work and dissipates the rest; it builds no internal store and pays only base maintenance. "
        "coupling_activity is ignored (autonomy 0). The baseline for 'internalization pays'.",
        ["No internal store: internal_power = 0, autonomy = 0."],
    )


class IonGradientCouplingProcess(_IonicStore):
    """``h_na_gradient_leaky_membrane``: a pumped Na+/H+ gradient as the store.

    The chemical drive powers a pump (``pump_efficiency``) that builds an ion
    gradient whose potential is capacitor-like, ``n F pmf_max q`` (``n`` ions per
    load transfer, as a c-ring couples several ions per synthesis step). The
    store leaks THROUGH THE MEMBRANE at ``P_Na = carrier_permeability_ratio x P_H``
    (Sojo 2014: fatty-acid membranes are far less permeable to Na+ than H+), so
    the same leak that feeds the external tap drains the store — the Sojo tradeoff
    made per-individual.
    """

    config_schema = {**_BASE_CONFIG,
                     "carrier_permeability_ratio": _cfg(1.0e-3, "dimensionless", "inferred")}
    contract = _contract(
        "Ion-gradient coupling (Sojo leaky membrane): a pumped Na+/H+ gradient store that leaks with the membrane.",
        "The chemical drive powers a pump building an ion-gradient store with capacitor-like potential "
        "n F pmf_max q; work is drawn once that potential clears the load; the store leaks through the "
        "membrane at P_Na = ratio x P_H, so a leaky membrane feeds the external tap and drains the store at once.",
        ["Ion store potential is linear in charge (capacitor); leak is first-order through the membrane at ratio x P_H."],
    )


class ThioesterCouplingProcess(_ChemicalStore):
    """``thioester_acyl_phosphate``: og-energy's thioester / acyl-phosphate
    carrier as the internal store (bond 35 kJ/mol), leaking by hydrolysis and
    slow carrier permeation — the existing currency, now inside the individual."""

    config_schema = {**_BASE_CONFIG,
                     "bond_free_energy": _cfg(35.0, "kilojoule/mole", "inferred"),
                     "hydrolysis_rate": _cfg(1.0e-4, "1/second", "extrapolated"),
                     "carrier_permeability_ratio": _cfg(1.0e-4, "dimensionless", "hypothetical")}
    contract = _contract(
        "Thioester / acyl-phosphate coupling: the og-energy chemical carrier as the individual's internal store.",
        "The chemical drive charges a thioester-class carrier pool (bond 35 kJ/mol; potential bond + RT ln(q/(1-q))) "
        "while the drive clears the store potential; work is drawn once the potential clears the load; the store "
        "leaks by hydrolysis and by carrier permeation (ratio x P_H).",
    )


class PolyphosphateCouplingProcess(_ChemicalStore):
    """``polyphosphate``: a low-bond (20 kJ/mol) but kinetically stable
    phosphoanhydride store — it must be charged very high to clear a 30 kJ/mol
    load, but it hardly hydrolyses."""

    config_schema = {**_BASE_CONFIG,
                     "bond_free_energy": _cfg(20.0, "kilojoule/mole", "inferred"),
                     "hydrolysis_rate": _cfg(1.0e-6, "1/second", "extrapolated"),
                     "carrier_permeability_ratio": _cfg(1.0e-4, "dimensionless", "hypothetical")}
    contract = _contract(
        "Polyphosphate coupling: a low-bond, kinetically stable phosphoanhydride store.",
        "As the thioester class with bond 20 kJ/mol and a 100x slower hydrolysis: the store must sit near full "
        "charge (RT ln(q/(1-q)) >= 10 kJ/mol) before it can clear a 30 kJ/mol load, so it pays only where the "
        "membrane keeps it.",
        refs=["buckel2013energy", "natcomm2025phosphateactivation", "pasek2017schreibersite"],
    )


class FeRedoxCouplingProcess(_ChemicalStore):
    """``fe_redox``: reduced Fe/Ni centres as the store, charged by the
    Fe(II)-disproportionation drive (the composite wires this class to that
    drive), leaking by re-oxidation and Fe2+ permeation."""

    config_schema = {**_BASE_CONFIG,
                     "bond_free_energy": _cfg(28.0, "kilojoule/mole", "hypothetical"),
                     "hydrolysis_rate": _cfg(1.0e-4, "1/second", "hypothetical"),
                     "carrier_permeability_ratio": _cfg(1.0e-5, "dimensionless", "hypothetical")}
    contract = _contract(
        "Fe-redox coupling: reduced-metal centres charged by Fe(II) disproportionation.",
        "A reduced Fe/Ni-centre pool (effective transfer 28 kJ/mol) is charged by the mineral-mediated "
        "Fe(II)-disproportionation drive and drawn to the load; it loses charge by re-oxidation and by Fe2+ "
        "permeation (divalent, tighter than Na+).",
        refs=["natcomm2025fedisproportionation", "buckel2013energy"],
    )


ENERGY_COUPLING_CLASSES = {
    "passive_gradient": PassiveGradientCouplingProcess,
    "h_na_gradient_leaky_membrane": IonGradientCouplingProcess,
    "thioester_acyl_phosphate": ThioesterCouplingProcess,
    "polyphosphate": PolyphosphateCouplingProcess,
    "fe_redox": FeRedoxCouplingProcess,
}

__all__ = ["PassiveGradientCouplingProcess", "IonGradientCouplingProcess", "ThioesterCouplingProcess",
           "PolyphosphateCouplingProcess", "FeRedoxCouplingProcess", "ENERGY_COUPLING_CLASSES",
           "F_KJ", "F_C", "R_KJ"]
