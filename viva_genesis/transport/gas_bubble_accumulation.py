"""Concentrate the amphiphile pool at a HEATED GAS-WATER INTERFACE (gas bubble).

An ALTERNATIVE to the thermophoretic (Baaske) pore trap for supplying the
orders-of-magnitude the reciprocal-maintenance refutation (og-self-maintaining-
individual) found missing: the chemistry's amphiphile pool sits 4-7 orders below
its critical aggregation concentration, so no membrane forms endogenously. The
thermophoretic trap closes that gap SPATIALLY but only near its exponential
maximum and on an hours-to-days residence time. Morasch, Liu, Mast, Braun et al.
("Heated gas bubbles enrich, crystallize, dry, phosphorylate and encapsulate
prebiotic molecules", Nature Chemistry 11, 779-788, 2019; arXiv:2104.05537)
report that a gas bubble held across a thermal gradient concentrates solutes at
its warm-side meniscus FASTER (minutes, not hours) via a continuous evaporation-
recondensation cycle of water, and — crucially for a protocell — continuously
ENCAPSULATES the accumulated solutes once lipids (oleic acid / DOPC) are present.

Grounded magnitudes (Morasch 2019, measured, NOT fitted by us):
  * 132-mer ssDNA, 200 nM bulk, delta_T = 20 K (Twarm 30, Tcold 10 degC): the
    chamber-averaged fluorescence at the contact line rose ~12-fold within SIX
    MINUTES; corrected for the thin (~4 um) meniscus accumulation region vs the
    240 um chamber, the inferred LOCAL concentration rose by a factor of ~700
    (200 nM -> ~140 uM).
  * The accumulation grew with delta_T, reaching a ~4000-fold increase at
    delta_T = 40 K. Divalent ions (Mg2+) accumulated ~4-5x at delta_T 20-30 K.
    Smaller (15-mer) DNA accumulated ~3x LESS than the 132-mer (higher diffusion
    coefficient); accumulation is diffusion-coefficient dependent ("several
    orders of magnitude, depending on their diffusion coefficient").
  * With oleic acid or DOPC vesicles present, accumulation at the interface drove
    continuous encapsulation of oligonucleotides into vesicle aggregates with up
    to an 18-fold local concentration enhancement inside the vesicles.
  * Timescale: all six reported processes established within <30 min, in
    continuous contact with bulk water; "the accumulation at the interface
    occurred significantly faster, on the timescale of minutes rather than hours"
    than in a thermophoretic trap, "with which the setting could be combined".

We ground the interface enrichment on the measured delta_T scaling:

    E(delta_T) = E_ref * exp(k * (delta_T - delta_T_ref))
    E_ref = 700 at delta_T_ref = 20 K ;  k = ln(4000/700)/20 = 0.0871 / K
    ->  E(20) = 700, E(30) ~ 1670, E(40) = 4000     (interpolates the two anchors)

This is applied ONCE to the synthesised pool (conservative — not compounded
through the nonlinear synthesis), exactly as the thermophoretic adapter does, so
the two concentrating mechanisms are compared on equal footing. A
``diffusion_derate`` in (0, 1] carries the paper's diffusion-coefficient
dependence: amphiphile MONOMERS (small, fast-diffusing) accumulate less than the
132-mer the anchors were measured on (the 15-mer saw ~0.33), whereas fatty acids
ABOVE their CMC self-assemble into vesicles that — as the paper shows directly —
are themselves strongly accumulated at the interface, so the default 1.0 treats
the aggregation-competent (long-chain, self-associating) pool as a strong
accumulator and the knob lets a reviewer derate it. ``max_enrichment`` defaults
to the measured ceiling (4000); the bubble has a HARD measured ceiling ~O(10^3-4)
unlike the trap's exponential >10^8. ``concentrating=False`` forces the factor to
1.0 — the matched non-concentrating control (the no-built-in-gain witness).

The enrichment builds on a minutes timescale (``tau``, default ~ one 6-min tick,
from the 12-fold-in-6-min observation); ``effective_enrichment`` is the
time-equilibrated factor actually applied, and ``equilibration_fraction`` reports
how far toward steady state the interface has gone — the FAST-vs-slow contrast
with the thermophoretic trap made explicit in the dynamics.
"""
from __future__ import annotations

import math

from process_bigraph import Process

_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_MOLAR = {"_type": "float", "_units": "molar"}
_K = {"_type": "float", "_units": "kelvin"}
_OW_DIMLESS = {"_type": "overwrite[float]", "_units": "dimensionless"}
_OW_MOLAR = {"_type": "overwrite[float]", "_units": "molar"}

# Measured anchors from Morasch 2019 (Nature Chemistry 11, 779-788; arXiv:2104.05537).
_E_REF = 700.0      # local meniscus enrichment at the reference delta_T
_DT_REF = 20.0      # K (Twarm 30, Tcold 10 degC)
_E_HI = 4000.0      # local meniscus enrichment at delta_T = 40 K
_DT_HI = 40.0       # K
_K_DT = math.log(_E_HI / _E_REF) / (_DT_HI - _DT_REF)   # 0.0871 / K


class GasBubbleAccumulationProcess(Process):
    """Apply a heated gas-water interface's evaporation-recondensation enrichment
    to the amphiphile pool -> the meniscus-local aggregation competence (the pool
    re-evaluated at the bubble's warm-side contact line).

    Self-contained: unlike the thermophoretic adapter (which reads an enrichment
    factor solved by a separate FiPy trap), the interface enrichment is derived
    here from the measured Morasch delta_T scaling, then applied to the pool. This
    is the gas-bubble analogue of ``AmphiphileTrapConcentrationProcess`` and is
    deliberately structured the same way so the two mechanisms compare directly.
    """

    config_schema = {
        # The matched non-concentrating control: ignore the interface, pool stays
        # at its well-mixed value (enrichment forced to 1).
        "concentrating": {"_type": "boolean", "_default": True},
        # Measured delta_T -> enrichment anchors (Morasch 2019). Exposed so the
        # grounding is auditable, not hard-wired magic numbers.
        "e_ref": {"_type": "float", "_default": _E_REF, "_units": "dimensionless"},
        "delta_T_ref": {"_type": "float", "_default": _DT_REF, "_units": "kelvin"},
        "k_delta_T": {"_type": "float", "_default": _K_DT, "_units": "1/kelvin"},
        # Diffusion-coefficient dependence (Morasch: 15-mer ~0.33x the 132-mer).
        # 1.0 = aggregation-competent self-associating pool accumulates as strongly
        # as the measured 132-mer / oleic-acid vesicles; < 1 derates fast monomers.
        "diffusion_derate": {"_type": "float", "_default": 1.0, "_units": "dimensionless"},
        # HARD measured ceiling: the bubble reached ~4000-fold at delta_T 40 K;
        # unlike the trap's exponential >10^8 there is no runaway. Kept at the
        # measured max by default; raise only to probe an explicit extrapolation.
        "max_enrichment": {"_type": "float", "_default": _E_HI, "_units": "dimensionless"},
        # Minutes-scale equilibration (12-fold within 6 min). In the composite's
        # 6-min ticks this is ~1 tick; the interface is fast vs the trap's hours.
        "tau": {"_type": "float", "_default": 1.0, "_units": "dimensionless"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._elapsed = 0.0  # ticks since the gradient was switched on

    def inputs(self):
        return {
            "aggregation_competent": _DIMLESS,   # base (well-mixed) long-chain / CAC
            "amphiphile_total": _MOLAR,          # base amphiphile pool
            "delta_T": _K,                       # cross-bubble temperature difference
        }

    def outputs(self):
        return {
            "aggregation_competent_concentrated": _OW_DIMLESS,  # base * E(t)
            "amphiphile_total_concentrated": _OW_MOLAR,
            "effective_enrichment": _OW_DIMLESS,                # the factor actually applied
            "steady_enrichment": _OW_DIMLESS,                   # the delta_T steady target
            "equilibration_fraction": _OW_DIMLESS,              # how far toward steady (0-1)
        }

    def initial_state(self):
        return {"aggregation_competent": 0.0, "amphiphile_total": 0.0, "delta_T": _DT_REF}

    def _steady_enrichment(self, delta_T):
        """Measured meniscus enrichment at this delta_T, derated for diffusion and
        capped at the measured ceiling. >= 1 always."""
        e_ref = float(self.config["e_ref"])
        dt_ref = float(self.config["delta_T_ref"])
        k = float(self.config["k_delta_T"])
        e = e_ref * math.exp(k * (float(delta_T) - dt_ref))
        e *= max(0.0, float(self.config["diffusion_derate"]))
        e = min(max(e, 1.0), float(self.config["max_enrichment"]))
        return e

    def update(self, state, interval):
        base_ac = max(0.0, float(state.get("aggregation_competent", 0.0)))
        base_tot = max(0.0, float(state.get("amphiphile_total", 0.0)))
        delta_T = float(state.get("delta_T", _DT_REF))

        self._elapsed += float(interval)

        if not self.config["concentrating"]:
            steady = 1.0
            frac = 0.0
            e = 1.0
        else:
            steady = self._steady_enrichment(delta_T)
            tau = max(1e-9, float(self.config["tau"]))
            frac = 1.0 - math.exp(-self._elapsed / tau)  # minutes-scale ramp to steady
            e = 1.0 + (steady - 1.0) * frac

        return {
            "aggregation_competent_concentrated": base_ac * e,
            "amphiphile_total_concentrated": base_tot * e,
            "effective_enrichment": e,
            "steady_enrichment": steady,
            "equilibration_fraction": frac,
        }
