"""Module G — mixed-amphiphile protocell self-assembly (coarse-grained kinetics).

Campaign-IV transition: when do organic boundaries (fatty-acid / mixed single-chain
amphiphile vesicles) enhance an individual's persistence WITHOUT cutting it off
from the external geochemical gradient? The "individuality vs access" tradeoff: a
membrane must retain internal chemistry (low leakage) yet stay permeable enough to
import the vent's resources.

This is a **coarse-grained physico-chemical model** — the study's proposed primary
method (full membrane MD via OpenMM/LAMMPS is impractical in-environment). It is a
clean-room reproduction of the Jordan-2019 vesicle-stability physical chemistry,
NOT a wrapped MD engine, and is named + documented as such. It reproduces, from
established relations:

- **the stability window** — fatty-acid vesicles form in a pH band around the
  bilayer-shifted apparent pKa, and tolerate only limited ionic strength / divalent
  cations; a co-surfactant fraction (mixed amphiphiles) BROADENS the window in pH,
  salt and divalent tolerance (Jordan et al. 2019, Nat. Ecol. Evol.);
- **permeability** — a solubility-diffusion Arrhenius law in temperature and
  composition;
- **retention vs access** — retention = exp(−permeability·A/V·τ) (chemistry held),
  access = permeability·A·(external gradient) (resources imported); their product is
  the individuality-without-isolation metric, non-empty only in an intermediate
  window.

The favorable arm (mixed amphiphiles, alkaline vent pH, seawater salt) forms viable
compartments with retention AND access > 0; a single-fatty-acid control fails on
salt tolerance; extreme-salt / extreme-pH controls form no vesicles.
"""
from __future__ import annotations

import math

from process_bigraph import Process

_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_MOLAR = {"_type": "float", "_units": "molar"}
_K = {"_type": "float", "_units": "kelvin"}
_M2 = {"_type": "float", "_units": "meter**2"}
_MPS = {"_type": "float", "_units": "meter/second"}
_LITER = {"_type": "float", "_units": "liter"}
_COUNT = {"_type": "integer", "_units": "dimensionless"}

_R = 8.314462618     # J/mol/K


class ProtocellAssemblyProcess(Process):
    """Coarse-grained physico-chemical model of mixed single-chain amphiphile
    vesicle self-assembly + permeability, calibrated to Jordan 2019. Reads the
    environment (pH, ionic strength, temperature); decides vesicle viability from
    the pH window + salt/divalent tolerance (broadened by the co-surfactant
    fraction); and emits the membrane area, permeability, compartment volume,
    viable-compartment count, and the retention / access / individuality-access
    tradeoff. A reproduction, not a wrapped MD engine — labeled as such."""

    contract = {
        "summary": "Coarse-grained mixed-amphiphile vesicle self-assembly + permeability, calibrated to Jordan 2019: the individuality-vs-access tradeoff (retain chemistry while staying permeable to the gradient).",
        "description": (
            "Clean-room reproduction of the Jordan-2019 vesicle-stability physical "
            "chemistry (NOT a wrapped MD engine; the proposed primary method is "
            "coarse-grained membrane kinetics). Vesicles are viable when pH lies in a "
            "band around the bilayer apparent pKa AND ionic strength / divalent cations "
            "stay below a tolerance that the co-surfactant fraction broadens; "
            "permeability follows a solubility-diffusion Arrhenius law; retention = "
            "exp(-P*A/V*tau) and access = P*A*gradient trade off, their product non-empty "
            "only in an intermediate window. Favorable (mixed amphiphiles, alkaline, "
            "seawater salt) forms viable compartments with retention AND access; a "
            "single-fatty-acid control fails on salt tolerance."
        ),
        "inputs": {
            "pH": "environment pH (dimensionless)",
            "ionic_strength": "ionic strength (molar)",
            "temperature": "temperature (K)",
        },
        "outputs": {
            "membrane_area": "total vesicle membrane area (meter**2)",
            "permeability": "membrane solute permeability coefficient (meter/second)",
            "compartment_volume": "total enclosed compartment volume (liter)",
            "viable_compartments": "number of viable vesicles (integer)",
            "retention": "fraction of internal chemistry retained (dimensionless, 0-1)",
            "access": "external-gradient access / resource import (dimensionless, 0-1)",
            "individuality_access": "retention x access — individuality without isolation (dimensionless)",
        },
        "assumptions": [
            "Coarse-grained reproduction calibrated to Jordan 2019; full membrane MD is out of environment.",
            "Vesicle viability: pH in [pKa_eff +/- window] AND ionic_strength < I_max AND divalent < Mg_max AND T in range.",
            "Co-surfactant fraction broadens the pH / salt / divalent tolerance (the Jordan mixed-amphiphile result).",
            "Permeability: solubility-diffusion Arrhenius in T + composition; retention/access from P*A/V.",
        ],
        "math": [
            "viable = (|pH - pKa_eff| < window_eff) and (I < I_max_eff) and (Mg < Mg_max_eff) and (T in range)",
            "P = P0 * exp(-Ea/(R*T)) * (1 + k_P * mix_fraction)",
            "retention = exp(-P*A/V*tau);  access = tanh(P*A*gradient_scale);  individuality_access = retention*access",
        ],
        "symbols": {
            "pKa_eff": "bilayer apparent pKa (shifted up from solution)", "window_eff": "pH half-window (broadened by mix)",
            "I_max_eff": "ionic-strength tolerance (broadened by mix)", "mix_fraction": "co-surfactant fraction (0 = single fatty acid)",
        },
        "references": ["jordan2019promotion", "sutherland2017opinion"],
    }

    config_schema = {
        "mix_fraction": {"_type": "float", "_default": 0.4, "_units": "dimensionless"},        # co-surfactant fraction (0 = single FA)
        "amphiphile_conc": {"_type": "float", "_default": 5.0e-3, "_units": "molar"},          # total amphiphile (M)
        "cac": {"_type": "float", "_default": 1.0e-3, "_units": "molar"},                      # critical aggregation conc (M)
        "pka_bilayer": {"_type": "float", "_default": 8.3, "_units": "dimensionless"},         # apparent pKa in bilayer
        "ph_window": {"_type": "float", "_default": 0.9, "_units": "dimensionless"},           # base pH half-window
        "i_tolerance": {"_type": "float", "_default": 0.18, "_units": "molar"},                # base ionic-strength tolerance (M)
        "divalent": {"_type": "float", "_default": 0.01, "_units": "molar"},                   # Mg2+/Ca2+ present (M)
        "divalent_tolerance": {"_type": "float", "_default": 0.012, "_units": "molar"},        # base divalent tolerance (M)
        "vesicle_radius": {"_type": "float", "_default": 2.0e-7, "_units": "meter"},           # 200 nm
        "perm_prefactor": {"_type": "float", "_default": 5.0e-4, "_units": "meter/second"},    # P0
        "perm_activation": {"_type": "float", "_default": 3.0e4, "_units": "joule/mole"},      # Ea
        "residence_time": {"_type": "float", "_default": 30.0, "_units": "second"},            # internal retention timescale
        # Selective permeability: the membrane is far less permeable to the large/
        # charged INTERNAL metabolites (retain) than to the small external resources
        # (access) — individuality WITHOUT isolation.
        "retain_factor": {"_type": "float", "_default": 0.03, "_units": "dimensionless"},
        "access_factor": {"_type": "float", "_default": 1.0, "_units": "dimensionless"},
    }

    def inputs(self):
        return {"pH": _DIMLESS, "ionic_strength": _MOLAR, "temperature": _K}

    def outputs(self):
        return {
            "membrane_area": {"_type": "overwrite[float]", "_units": "meter**2"},
            "permeability": {"_type": "overwrite[float]", "_units": "meter/second"},
            "compartment_volume": {"_type": "overwrite[float]", "_units": "liter"},
            "viable_compartments": {"_type": "overwrite[integer]", "_units": "dimensionless"},
            "retention": {"_type": "overwrite[float]", "_units": "dimensionless"},
            "access": {"_type": "overwrite[float]", "_units": "dimensionless"},
            "individuality_access": {"_type": "overwrite[float]", "_units": "dimensionless"},
        }

    def initial_state(self):
        return {"pH": 9.0, "ionic_strength": 0.35, "temperature": 318.15}

    def update(self, state, interval):
        pH = float(state.get("pH", 9.0))
        ionic = max(float(state.get("ionic_strength", 0.0)), 0.0)
        temp_k = max(float(state.get("temperature", 318.15)), 250.0)

        mix = min(max(float(self.config["mix_fraction"]), 0.0), 1.0)
        # Co-surfactant broadens the pH window, salt tolerance and divalent
        # tolerance (the Jordan-2019 mixed-amphiphile result).
        window_eff = float(self.config["ph_window"]) * (1.0 + 1.6 * mix)
        i_max_eff = float(self.config["i_tolerance"]) * (1.0 + 2.5 * mix)
        mg_max_eff = float(self.config["divalent_tolerance"]) * (1.0 + 3.0 * mix)

        in_ph = abs(pH - float(self.config["pka_bilayer"])) < window_eff
        in_salt = ionic < i_max_eff
        in_mg = float(self.config["divalent"]) < mg_max_eff
        in_temp = 278.0 < temp_k < 348.0
        above_cac = float(self.config["amphiphile_conc"]) > float(self.config["cac"])
        viable = in_ph and in_salt and in_mg and in_temp and above_cac

        radius = float(self.config["vesicle_radius"])
        # Vesicle count scales with amphiphile excess over the CAC (coarse).
        excess = max(float(self.config["amphiphile_conc"]) - float(self.config["cac"]), 0.0)
        n_ves = int(max(0, round(excess / 5.0e-4 * 1000.0))) if viable else 0
        area_one = 4.0 * math.pi * radius ** 2                         # m^2 per vesicle
        vol_one_L = (4.0 / 3.0) * math.pi * radius ** 3 * 1.0e3        # m^3 -> L
        membrane_area = area_one * n_ves
        compartment_volume = vol_one_L * n_ves

        # Permeability: solubility-diffusion Arrhenius + composition (mixed slightly
        # more permeable). m/s.
        perm = (float(self.config["perm_prefactor"])
                * math.exp(-float(self.config["perm_activation"]) / (_R * temp_k))
                * (1.0 + 0.6 * mix))

        # Retention vs access tradeoff (per single vesicle geometry, viable only).
        # The membrane retains the large/charged internal metabolites (low effective
        # permeability, retain_factor << 1) while admitting small external resources
        # (access_factor ~ 1) — individuality WITHOUT isolation.
        if viable:
            a_over_v = 3.0 / radius                                   # 1/m
            tau = float(self.config["residence_time"])
            leak = perm * a_over_v * tau                              # dimensionless leak number
            retention = math.exp(-float(self.config["retain_factor"]) * leak)   # held
            access = math.tanh(float(self.config["access_factor"]) * leak)      # imported
            individuality_access = retention * access
        else:
            retention = access = individuality_access = 0.0

        return {
            "membrane_area": membrane_area,
            "permeability": perm,
            "compartment_volume": compartment_volume,
            "viable_compartments": n_ves,
            "retention": retention,
            "access": access,
            "individuality_access": individuality_access,
        }
