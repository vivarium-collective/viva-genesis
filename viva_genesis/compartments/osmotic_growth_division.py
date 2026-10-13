"""Module H+ — osmotic growth and division (og-growth-division).

Campaign stage **metabolism → growth & division**: a protocell should not merely
*persist* — its chemistry should change its physical fate. This process couples an
internal autocatalytic/metabolic source (a reduced rTCA-style turn, Muchowska 2019)
to compartment physics: the product it makes is an osmolyte, its accumulation
generates **osmotic pressure** (van 't Hoff), that pressure drives **solvent
influx** across a semi-permeable membrane, the compartment **expands**, and at a
size threshold it **divides** (halving volume and contents). Division is a *physical*
selection mechanism — no abstract fitness score.

The membrane **permeability** is the control knob that decides the fate. It lets
solutes (the osmolyte product) and solvent (water) cross:

- **too permeable** — the product leaks out as fast as it is made, the internal
  concentration (and osmotic pressure) never build, no water is drawn in, the
  compartment never grows → **starvation**;
- **too impermeable** — the product is trapped, concentration and osmotic pressure
  spike faster than slow solvent influx + division can relieve them, and the
  pressure exceeds the membrane's burst tension → **lysis**;
- **matched** — the product is retained enough to pull water in and grow to the
  division threshold, yet the pressure stays bounded → sustained **growth → division**.

This is a **coarse-grained, units-typed, mass-conserving** reproduction (the stage's
proposed primary method is custom membrane kinetics; full membrane MD is out of the
environment). Every quantity is a real forward integration of the osmotic coupling:

  c_in       = N / V                                   (internal osmolyte, molar)
  Pi         = R T (c_in - c_out)                      (osmotic pressure, Pa; van 't Hoff)
  dN/dt      = J_prod(1 + g·tanh(N/N_ref)) - P_s·A·(c_in - c_out)   (autocatalytic source − leak)
  dV/dt      = L_p·A·Pi                                 (solvent influx, A = (36π)^{1/3} V^{2/3})
  if V >= V_div:  V,N -> V/2, N/2  (divide; mass conserved)
  if Pi >= Pi_lyse:  lyse

Mass is conserved to machine precision across production, leak and division: the
emitted ``osmolyte_balance_residual`` is ``(N0 + produced) - (N + leaked +
daughter_mass)`` and stays ~0 by construction (the growth/division conservation
witness).
"""
from __future__ import annotations

import math

from process_bigraph import Process

# --- port type helpers (bigraph-schema typed + units) ---------------------
_MOLAR = {"_type": "float", "_units": "molar"}
_O_L = {"_type": "overwrite[float]", "_units": "liter"}
_O_MOLAR = {"_type": "overwrite[float]", "_units": "molar"}
_O_PA = {"_type": "overwrite[float]", "_units": "pascal"}
_O_MOLE = {"_type": "overwrite[float]", "_units": "mole"}
_O_DIMLESS = {"_type": "overwrite[float]", "_units": "dimensionless"}
_O_COUNT = {"_type": "overwrite[integer]", "_units": "dimensionless"}

_R = 8.314462618                     # J/mol/K
_KA = (36.0 * math.pi) ** (1.0 / 3.0)  # sphere area prefactor: A = _KA * V_m3^(2/3)

# outcome codes (physical fate of the compartment)
_STARVE, _GROW, _DIVIDE, _LYSIS = 0, 1, 2, 3


class OsmoticGrowthDivisionProcess(Process):
    """Couples an internal autocatalytic osmolyte source to compartment osmotic
    physics: product accumulation → osmotic pressure → solvent influx → volume
    growth → division at a size threshold (or lysis if the pressure bursts the
    membrane, or starvation if the product leaks away before it can build). A
    coarse-grained, units-typed, mass-conserving reproduction — not wrapped MD.

    Stateful: the compartment's volume ``V`` and internal osmolyte amount ``N``
    are integrated across calls (like a genuine ODE integrator), sub-stepped for
    stability. Each ``update`` advances one ``interval`` and emits the volume,
    internal concentration, osmotic pressure, product amount, division count /
    event, lysis flag, net growth, the mass-balance residual, and an outcome code
    (0 starve · 1 grow-no-division · 2 divide · 3 lysis)."""

    contract = {
        "summary": "Internal autocatalytic osmolyte source coupled to compartment osmotic physics: product → osmotic pressure → solvent influx → volume growth → division (or lysis / starvation set by membrane permeability).",
        "description": (
            "Coarse-grained, units-typed, mass-conserving reproduction of metabolism "
            "changing a protocell's physical fate. An internal autocatalytic/metabolic "
            "source (reduced rTCA-style turn) makes an osmolyte; its accumulation sets "
            "the internal concentration and, by van 't Hoff, the osmotic pressure; that "
            "pressure drives solvent influx across a semi-permeable membrane and the "
            "compartment expands; at a volume threshold it divides (V and N halved, mass "
            "conserved). The membrane permeability lets solutes and solvent cross and "
            "decides the fate: too permeable starves (product leaks, no osmotic build-up), "
            "too impermeable lyses (pressure spikes past the burst tension), matched gives "
            "sustained growth → division. Not a wrapped membrane-MD engine."
        ),
        "inputs": {
            "external_osmolyte": "external osmolyte concentration c_out (molar); the leak/osmosis reference, default 0",
        },
        "outputs": {
            "volume": "compartment volume V (liter)",
            "internal_concentration": "internal osmolyte concentration c_in = N/V (molar)",
            "osmotic_pressure": "van 't Hoff osmotic pressure Pi = R T (c_in - c_out) (pascal)",
            "product_amount": "internal osmolyte amount N in this lineage (mole)",
            "division_count": "cumulative number of divisions (integer)",
            "division_event": "1 on an interval in which a division occurred, else 0 (integer)",
            "lysed": "1 once the osmotic pressure has burst the membrane, else 0 (integer)",
            "net_growth": "V / V0 — net volume growth factor (dimensionless)",
            "osmolyte_balance_residual": "(N0 + produced) - (N + leaked + daughter_mass) — the growth/division mass-conservation witness (~0) (mole)",
            "outcome_code": "physical fate: 0 starve · 1 grow-no-division · 2 divide · 3 lysis (integer)",
        },
        "assumptions": [
            "Coarse-grained reproduction; the proposed primary method is custom membrane kinetics (full membrane MD is out of environment).",
            "van 't Hoff ideal-dilute osmotic pressure Pi = R T (c_in - c_out).",
            "Spherical compartment: A = (36 pi)^(1/3) V^(2/3); solvent influx dV/dt = Lp A Pi.",
            "membrane_permeability is the solute permeability P_s (m/s); solvent hydraulic conductivity Lp is finite and fixed, so osmotic pressure can build (lysis) when influx + division cannot relieve it.",
            "Division halves V and N (mass conserved); lysis when Pi >= lysis_pressure; starvation when the compartment never grows.",
        ],
        "math": [
            "c_in = N/V ; Pi = R T (c_in - c_out)",
            "dN/dt = network_throughput*(1 + autocatalytic_rate*tanh(N/N_ref)) - membrane_permeability*leak_rate*A*(c_in - c_out)",
            "dV/dt = Lp*A*Pi ;  A = (36 pi)^(1/3) (V in m^3)^(2/3)",
            "V >= division_threshold => V,N := V/2, N/2 (divide) ; Pi >= lysis_pressure => lyse",
        ],
        "symbols": {
            "N": "internal osmolyte amount (mol)", "V": "compartment volume (L)",
            "P_s": "membrane solute permeability (m/s)", "Lp": "solvent hydraulic conductivity (m/Pa/s)",
            "N_ref": "autocatalytic half-saturation amount (mol)",
        },
        "references": ["muchowska2019synthesis", "jordan2019promotion"],
    }

    config_schema = {
        # --- the four generator knobs -------------------------------------
        "network_throughput": {"_type": "float", "_default": 1.0e-19, "_units": "mole/second"},   # autocatalytic/metabolic source rate J_prod
        "autocatalytic_rate": {"_type": "float", "_default": 0.5, "_units": "dimensionless"},      # self-amplification gain g
        "membrane_permeability": {"_type": "float", "_default": 1.0e-9, "_units": "meter/second"}, # solute permeability P_s
        "division_threshold": {"_type": "float", "_default": 6.4e-17, "_units": "liter"},          # V_div (= 1.6 x initial volume)
        "leak_rate": {"_type": "float", "_default": 1.0, "_units": "dimensionless"},               # multiplier on P_s for solute leak
        # --- fixed physico-chemical constants -----------------------------
        "initial_volume": {"_type": "float", "_default": 4.0e-17, "_units": "liter"},              # V0 (~200 nm vesicle)
        "initial_osmolyte": {"_type": "float", "_default": 2.0e-20, "_units": "mole"},             # N0 seed
        "autocat_ref": {"_type": "float", "_default": 6.0e-19, "_units": "mole"},                  # N_ref
        "solvent_conductivity": {"_type": "float", "_default": 4.0e-14, "_units": "meter/second/pascal"},  # Lp
        "lysis_pressure": {"_type": "float", "_default": 1.5e5, "_units": "pascal"},               # burst pressure Pi_lyse
        "temperature": {"_type": "float", "_default": 318.15, "_units": "kelvin"},                 # vent T
        "substeps": {"_type": "integer", "_default": 60, "_units": "dimensionless"},               # integration sub-steps per interval
    }

    def __init__(self, config=None, core=None):
        super().__init__(config, core)
        self._init_state()

    def _init_state(self):
        self._V = float(self.config["initial_volume"])        # liter
        self._N = float(self.config["initial_osmolyte"])      # mole
        self._V0 = self._V
        self._divisions = 0
        self._lysed = False
        self._produced = 0.0
        self._leaked = 0.0
        self._daughter_mass = 0.0

    def inputs(self):
        return {"external_osmolyte": _MOLAR}

    def outputs(self):
        return {
            "volume": _O_L,
            "internal_concentration": _O_MOLAR,
            "osmotic_pressure": _O_PA,
            "product_amount": _O_MOLE,
            "division_count": _O_COUNT,
            "division_event": _O_COUNT,
            "lysed": _O_COUNT,
            "net_growth": _O_DIMLESS,
            "osmolyte_balance_residual": _O_MOLE,
            "outcome_code": _O_COUNT,
        }

    def initial_state(self):
        return {"external_osmolyte": 0.0}

    def update(self, state, interval):
        rt = _R * float(self.config["temperature"])                      # J/mol
        c_out_m3 = max(float(state.get("external_osmolyte", 0.0)), 0.0) * 1.0e3   # mol/m^3
        j0 = float(self.config["network_throughput"])                    # mol/s
        g = float(self.config["autocatalytic_rate"])
        p_s = max(float(self.config["membrane_permeability"]), 0.0)      # m/s
        leak = max(float(self.config["leak_rate"]), 0.0)
        lp = float(self.config["solvent_conductivity"])                  # m/Pa/s
        v_div = float(self.config["division_threshold"])                 # L
        n_ref = max(float(self.config["autocat_ref"]), 1e-30)
        pi_lyse = float(self.config["lysis_pressure"])                   # Pa
        n_sub = max(int(self.config["substeps"]), 1)
        h = float(interval) / n_sub

        divisions_this_interval = 0
        for _ in range(n_sub):
            if self._lysed:
                break
            v_m3 = self._V * 1.0e-3
            area = _KA * v_m3 ** (2.0 / 3.0)                             # m^2
            c_in_m3 = (self._N / self._V) * 1.0e3                        # mol/m^3
            pi = rt * (c_in_m3 - c_out_m3)                              # Pa
            if pi >= pi_lyse:
                self._lysed = True
                break
            j_prod = j0 * (1.0 + g * math.tanh(self._N / n_ref))        # mol/s
            j_leak = p_s * leak * area * max(c_in_m3 - c_out_m3, 0.0)   # mol/s (outward)
            d_prod = j_prod * h
            # The outward leak can never remove more osmolyte than is present
            # (floor at 0) — cap it so the mass-balance accounting stays exact.
            d_leak = min(j_leak * h, self._N + d_prod)
            self._produced += d_prod
            self._leaked += d_leak
            self._N = max(self._N + d_prod - d_leak, 0.0)
            dv_m3 = lp * area * max(pi, 0.0) * h                        # m^3 (osmotic influx)
            self._V = max(self._V + dv_m3 * 1.0e3, 1.0e-22)
            if self._V >= v_div:
                self._daughter_mass += 0.5 * self._N
                self._V *= 0.5
                self._N *= 0.5
                self._divisions += 1
                divisions_this_interval += 1

        v_m3 = self._V * 1.0e-3
        c_in_m3 = (self._N / self._V) * 1.0e3
        pi = rt * (c_in_m3 - c_out_m3)
        net_growth = self._V / self._V0
        if self._lysed:
            outcome = _LYSIS
        elif self._divisions >= 1:
            outcome = _DIVIDE
        elif net_growth > 1.15:
            outcome = _GROW
        else:
            outcome = _STARVE
        residual = (float(self.config["initial_osmolyte"]) + self._produced) - (
            self._N + self._leaked + self._daughter_mass)

        return {
            "volume": self._V,
            "internal_concentration": c_in_m3 / 1.0e3,                   # mol/L
            "osmotic_pressure": max(pi, 0.0),
            "product_amount": self._N,
            "division_count": int(self._divisions),
            "division_event": int(divisions_this_interval > 0),
            "lysed": int(self._lysed),
            "net_growth": net_growth,
            "osmolyte_balance_residual": residual,
            "outcome_code": int(outcome),
        }
