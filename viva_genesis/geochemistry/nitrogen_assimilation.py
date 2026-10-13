"""Module I (kinetics) — FeS-mediated reduced-nitrogen production + assimilation.

Carbon fixation is not the only requirement for a protocell: every amino acid,
nucleobase and cofactor needs REDUCED nitrogen (NH3/NH4+), and the early ocean's
accessible nitrogen was oxidised (NO3-/NO2-) or inert (N2). This process reduces
the available inorganic nitrogen to ammonium on an Fe/Ni-S catalyst, then draws
that ammonium into amino-acid precursors by reductive amination at a rate set by
the carbon-fixation demand — so the stage tracks whether reduced N is produced
fast enough to keep pace with reduced carbon (the C:N supply ratio).

Mechanism (all rates gated by the four things that actually control abiotic
nitrogen reduction at a vent, so the controls kill it honestly)::

    avail(H2)  = H2 / (H2 + km_h2)                  # reductant dependence
    T-window   = exp(-(T - t_opt)^2 / 2 t_width^2)  # ~70-90 C FeS optimum
    catalyst   = fes_activity in [0,1]              # 0 = no-mineral control

  dissimilatory nitrate -> nitrite -> ammonium on FeS (Est-2024-style):
    r_nar = k_nar * catalyst * avail * T-window * [NO3-]     # NO3- -> NO2-
    r_nir = k_nir * catalyst * avail * T-window * [NO2-]     # NO2- -> NH4+
  abiotic N2 fixation on fresh FeS (Doerr-2003; LOW yield, a minor source):
    r_n2  = k_n2fix * catalyst * avail * T-window * [N2]     # N2 -> 2 NH4+
  reductive amination toward amino-acid precursors, demanded by carbon fixation:
    v_want = c_demand / (volume * cn_target)                 # N uptake carbon wants (M/s)
    r_amin = v_want * [NH4+]/([NH4+] + km_amin)              # NH4+ -> precursor (saturating)

``no3_supply`` replenishes the nitrate pool (open-flow feed) and ``loss_rate``
washes ammonium / precursor out, so each pool reaches a CONDITION-DEPENDENT steady
state and ``nh4_production_rate`` settles to a genuine sustained throughput rather
than collapsing at substrate exhaustion. The C:N supply ratio
``c_demand / nh4_production_rate`` is the decision observable: below ~Redfield the
reduced-N supply keeps pace with carbon; far above it nitrogen is limiting.

Nitrogen mass is conserved by construction (every internal reaction conserves N
atoms; the only sources/sinks are the nitrate feed and the washout), and
``n_mass_residual`` emits the per-step accounting error — ~0 to machine precision,
the matter-accounting witness the campaign requires.
"""
from __future__ import annotations

import math

from process_bigraph import Process

_MOLAR = {"_type": "float", "_units": "molar"}
_K = {"_type": "float", "_units": "kelvin"}
_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_MOLS = {"_type": "float", "_units": "mole/second"}


class ReducedNitrogenProductionProcess(Process):
    """FeS-mediated reduction of NO3-/NO2- (and minor N2 fixation) to NH4+, with
    reductive amination toward amino-acid precursors at a carbon-demanded rate.

    Emits pool concentration increments (additive float deltas — pools accumulate)
    plus overwrite sensors for the ammonium-production rate, the C:N supply ratio,
    the reduced-N mass and the per-step nitrogen-mass residual."""

    contract = {
        "summary": "FeS-mediated NO3-/NO2- -> NH4+ (+ minor N2 fixation) with carbon-demanded reductive amination; tracks the C:N supply ratio and conserves nitrogen mass.",
        "description": (
            "Emits pool concentration increments (additive float deltas - pools accumulate) "
            "for H2-driven, FeS-catalysed reduction of nitrate through nitrite to ammonium, a "
            "minor abiotic N2-fixation source on fresh FeS, and reductive amination of ammonium "
            "into amino-acid precursors at a rate set by the carbon-fixation demand. Each rate is "
            "gated by reductant availability (H2), an FeS temperature window and catalyst activity "
            "(0 = no-mineral control). An open-flow nitrate feed and ammonium washout give a "
            "condition-dependent steady state, so the ammonium-production rate and the C:N supply "
            "ratio (carbon demand / reduced-N production) are sustained-throughput sensors. "
            "Nitrogen mass is conserved by construction; n_mass_residual is the accounting witness."
        ),
        "inputs": {
            "NO3": "dissolved nitrate (molar)", "NO2": "dissolved nitrite (molar)",
            "NH4": "ammonium pool (molar)", "amino_precursor": "reductively-aminated precursor pool (molar)",
            "N2": "dissolved dinitrogen (molar)", "H2": "dissolved H2 reductant (molar)",
            "temperature": "temperature (K)",
            "fes_activity": "active Fe/Ni/S catalyst in [0,1] (dimensionless; 0 = no-mineral control)",
            "c_demand": "carbon-fixation demand pulling reduced N into precursors (mole/second)",
        },
        "outputs": {
            "NO3": "nitrate delta (molar)", "NO2": "nitrite delta (molar)",
            "NH4": "ammonium delta (molar)", "amino_precursor": "precursor delta (molar)",
            "N2": "dinitrogen delta (molar)",
            "nh4_production_rate": "reduced-nitrogen (ammonium) production rate (mole/second)",
            "n_supply_rate": "reduced-N made available to amination (mole/second)",
            "cn_supply_ratio": "carbon demand / reduced-N production (dimensionless)",
            "reduced_n": "useful reduced N = NH4+ + amino-precursor (molar)",
            "total_n": "total nitrogen atoms across all pools (molar, matter accounting)",
            "n_mass_residual": "per-step nitrogen-mass accounting error (molar; ~0 by construction)",
        },
        "assumptions": [
            "Nitrate reduction NO3- -> NO2- -> NH4+ on FeS (Est-2024-style dissimilatory route).",
            "N2 fixation on FeS is a LOW-yield minor source (Doerr-2003 ~0.1% relative yield).",
            "rate = k * fes_activity * avail(H2) * T-window * [substrate]; amination scales with c_demand.",
            "Nitrogen atoms conserved internally; only the nitrate feed and ammonium washout are sources/sinks.",
        ],
        "references": ["dorr2003prebiotic", "huber1997activated", "varma2018native"],
    }

    config_schema = {
        "k_nar": {"_type": "float", "_default": 0.08, "_units": "1/second"},      # NO3- -> NO2-
        "k_nir": {"_type": "float", "_default": 0.12, "_units": "1/second"},      # NO2- -> NH4+
        "k_n2fix": {"_type": "float", "_default": 1.0e-4, "_units": "1/second"},  # N2 -> 2 NH4+ (low)
        "km_h2": {"_type": "float", "_default": 1.0e-4, "_units": "molar"},
        "km_amin": {"_type": "float", "_default": 1.0e-3, "_units": "molar"},     # amination half-saturation on NH4+
        "cn_target": {"_type": "float", "_default": 5.0, "_units": "dimensionless"},  # Redfield-like C:N the cell wants
        "t_opt": {"_type": "float", "_default": 353.15, "_units": "kelvin"},       # ~80 C FeS optimum
        "t_width": {"_type": "float", "_default": 45.0, "_units": "kelvin"},
        "reactor_volume_scale": {"_type": "float", "_default": 1.0, "_units": "liter"},
        # Open-flow nitrate feed (M/s) and washout (1/s). no3_supply replenishes the
        # nitrate pool; loss_rate flushes ammonium + precursor so a fast producer
        # reaches a condition-dependent steady state (not just substrate exhaustion).
        "no3_supply": {"_type": "float", "_default": 2.0e-5, "_units": "molar/second"},
        "loss_rate": {"_type": "float", "_default": 0.0, "_units": "1/second"},
    }

    def inputs(self):
        return {
            "NO3": _MOLAR, "NO2": _MOLAR, "NH4": _MOLAR, "amino_precursor": _MOLAR,
            "N2": _MOLAR, "H2": _MOLAR, "temperature": _K,
            # fes_activity is a STORE input (not config) so an explicit 0.0 control
            # is honored rather than swallowed by the is_empty(Float, 0.0) config fill.
            "fes_activity": _DIMLESS,
            "c_demand": _MOLS,
        }

    def outputs(self):
        return {
            "NO3": _MOLAR, "NO2": _MOLAR, "NH4": _MOLAR, "amino_precursor": _MOLAR, "N2": _MOLAR,
            "nh4_production_rate": {"_type": "overwrite[float]", "_units": "mole/second"},
            "n_supply_rate": {"_type": "overwrite[float]", "_units": "mole/second"},
            "cn_supply_ratio": {"_type": "overwrite[float]", "_units": "dimensionless"},
            "reduced_n": {"_type": "overwrite[float]", "_units": "molar"},
            "total_n": {"_type": "overwrite[float]", "_units": "molar"},
            "n_mass_residual": {"_type": "overwrite[float]", "_units": "molar"},
        }

    def initial_state(self):
        return {"NO3": 1.0e-3, "NO2": 0.0, "NH4": 0.0, "amino_precursor": 0.0,
                "N2": 5.0e-4, "H2": 5.0e-3, "temperature": 353.15,
                "fes_activity": 1.0, "c_demand": 1.0e-4}

    def update(self, state, interval):
        no3 = max(float(state.get("NO3", 0.0)), 0.0)
        no2 = max(float(state.get("NO2", 0.0)), 0.0)
        nh4 = max(float(state.get("NH4", 0.0)), 0.0)
        amino = max(float(state.get("amino_precursor", 0.0)), 0.0)
        n2 = max(float(state.get("N2", 0.0)), 0.0)
        h2 = max(float(state.get("H2", 0.0)), 0.0)
        temp_k = float(state.get("temperature", 353.15))
        cat = max(0.0, min(1.0, float(state.get("fes_activity", 0.0))))
        c_demand = max(float(state.get("c_demand", 0.0)), 0.0)

        km_h2 = self.config["km_h2"]
        avail = h2 / (h2 + km_h2)
        t_opt, t_w = self.config["t_opt"], max(self.config["t_width"], 1.0)
        t_window = math.exp(-((temp_k - t_opt) ** 2) / (2.0 * t_w ** 2))
        gate = cat * avail * t_window
        vol = max(self.config["reactor_volume_scale"], 1e-12)
        supply = max(float(self.config.get("no3_supply", 0.0)), 0.0)    # M/s nitrate feed
        loss = max(float(self.config.get("loss_rate", 0.0)), 0.0)        # 1/s washout

        # Reduction chain NO3- -> NO2- -> NH4+ and minor N2 fixation (M/s).
        r_nar = self.config["k_nar"] * gate * no3
        r_nir = self.config["k_nir"] * gate * no2
        r_n2 = self.config["k_n2fix"] * gate * n2
        # Reductive amination NH4+ -> precursor, demanded by carbon fixation (M/s).
        # The carbon flux WANTS N at c_demand/cn_target; uptake saturates on the
        # standing ammonium pool, so NH4+ keeps a physical steady-state pool and the
        # draw is bounded + non-negative even when demand outruns supply.
        cn_target = max(self.config["cn_target"], 1e-6)
        v_want = c_demand / (vol * cn_target)
        r_amin = v_want * nh4 / (nh4 + self.config["km_amin"])

        # Open-flow washout on the mobile reduced-N pools (exponential, stable at any rate).
        wash_nh4 = nh4 * (1.0 - math.exp(-loss * interval))
        wash_amino = amino * (1.0 - math.exp(-loss * interval))

        d_no3 = (supply - r_nar) * interval
        d_no2 = (r_nar - r_nir) * interval
        d_nh4 = (r_nir + 2.0 * r_n2 - r_amin) * interval - wash_nh4
        d_amino = r_amin * interval - wash_amino
        d_n2 = -r_n2 * interval

        # Reduced-N (ammonium) production rate and the C:N supply ratio (mol/s).
        nh4_rate = (r_nir + 2.0 * r_n2) * vol
        cn_ratio = c_demand / nh4_rate if nh4_rate > 1e-18 else float("inf")
        cn_ratio = min(cn_ratio, 1.0e6)  # cap the "N absent" singularity for plotting

        # Matter accounting: Delta(total N atoms) must equal feed - washout exactly
        # (every internal reaction conserves N; N2 carries 2 atoms).
        d_total_n = d_no3 + d_no2 + d_nh4 + d_amino + 2.0 * d_n2
        expected = supply * interval - (wash_nh4 + wash_amino)
        residual = d_total_n - expected
        total_n = no3 + no2 + nh4 + amino + 2.0 * n2

        return {
            "NO3": d_no3, "NO2": d_no2, "NH4": d_nh4, "amino_precursor": d_amino, "N2": d_n2,
            "nh4_production_rate": nh4_rate,
            "n_supply_rate": (r_nir + 2.0 * r_n2) * vol,
            "cn_supply_ratio": cn_ratio,
            "reduced_n": nh4 + amino,
            "total_n": total_n,
            "n_mass_residual": residual,
        }
