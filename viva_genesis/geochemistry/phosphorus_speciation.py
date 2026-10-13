"""Module I (phosphorus) — P speciation via the REAL libRoadRunner engine.

**This is a genuine bridge to libRoadRunner / Tellurium** (the SBML ODE engine).
It integrates a closed phosphorus-speciation network for the phosphorus
bottleneck (campaign enrichment plan §6): dissolved orthophosphate, condensed
polyphosphate, reactive (activated) phosphorus, and a mineral-bound P sink, with
an explicit **precipitation / adsorption LOSS** term that competes with reactive-P
formation. The thermal-gradient pore (coupled from og-03) concentrates the
dissolved pool, and that enrichment drives condensation + activation; a no-trap
open pore (``pore_enrichment = 1``) leaves precipitation to win.

Why P is a harder bottleneck than carbon: dissolved phosphate precipitates /
adsorbs onto mineral surfaces readily (Ca/Fe phosphates), so the question is
whether reactive P is *produced faster than it is lost to the mineral sink* — and
whether the same pore regime that concentrates carbon can co-concentrate P before
it precipitates.

Reaction network (P-atom units, so total P is exactly conserved):

    Rcond : phosphate -> polyP        k_cond * Tfac * enr^2 * phosphate   (thermal/enrichment condensation)
    Rphyd : polyP     -> phosphate    k_phyd * polyP                      (polyphosphate hydrolysis)
    Ract  : polyP     -> reactiveP    k_act  * Tfac * enr   * polyP       (activation to reactive P)
    Rhyd  : reactiveP -> phosphate    k_hyd  * reactiveP                  (reactive-P relaxation if unused)
    Rprec : phosphate -> mineralP     k_prec * phosphate                  (precipitation / adsorption LOSS)
    Rdes  : mineralP  -> phosphate    k_des  * mineralP                   (slow desorption — finite sink)

``enr`` (pore enrichment) enters condensation as ``enr^2`` (condensation is
steeply concentration-dependent — two phosphates meet) and activation as ``enr``,
while precipitation is first-order in phosphate with no enrichment boost: so a
favorable trap tips the fate of phosphate toward the reactive route, while an
open pore (``enr = 1``) lets precipitation dominate.

Emergent observables (not assumptions):
- ``reactive_P`` — the standing available reactive-P pool (molar).
- ``reactive_P_production`` vs ``phosphate_loss`` — the mechanism-view competition
  (reactive-P formation flux vs the precipitation/adsorption loss flux, mole/s).
- ``net_reactive_P`` = production - precipitation loss; > 0 means reactive P is
  produced faster than it precipitates (a local availability window).
- ``precipitated_fraction`` — mineral-bound P / total P (how much was lost).
- ``p_mass_residual`` — |total P - supplied| / supplied (conservation witness, ~0).
"""
from __future__ import annotations

from process_bigraph import Process

_MOLAR = {"_type": "float", "_units": "molar"}
_K = {"_type": "float", "_units": "kelvin"}
_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_OW_MOLAR = {"_type": "overwrite[float]", "_units": "molar"}
_OW_MOLS = {"_type": "overwrite[float]", "_units": "mole/second"}
_OW_DIMLESS = {"_type": "overwrite[float]", "_units": "dimensionless"}

# Antimony P-speciation network (closed; P-atom units -> total P conserved).
# phosphate_supply seeds the dissolved pool; enr/Tfac are driven each tick.
_MODEL = """
  species phosphate, polyP, reactiveP, mineralP;
  Rcond: phosphate => polyP;      k_cond*Tfac*enr*enr*phosphate;
  Rphyd: polyP => phosphate;      k_phyd*polyP;
  Ract:  polyP => reactiveP;      k_act*Tfac*enr*polyP;
  Rhyd:  reactiveP => phosphate;  k_hyd*reactiveP;
  Rprec: phosphate => mineralP;   k_prec*phosphate;
  Rdes:  mineralP => phosphate;   k_des*mineralP;
  phosphate=1e-4; polyP=0; reactiveP=0; mineralP=0;
  enr=30; Tfac=1;
  k_cond=0.004; k_phyd=0.01; k_act=0.5; k_hyd=0.02; k_prec=0.08; k_des=0.002;
"""


class PhosphorusSpeciationProcess(Process):
    """Real libRoadRunner P-speciation network (phosphate <-> polyphosphate <->
    reactive-P with a precipitation/adsorption mineral sink). Reads the dissolved
    phosphate supply, the thermal-gradient pore enrichment and the pore
    temperature; advances the genuine SBML ODE network each tick; and emits the
    P-species pools (overwrite — roadrunner is the authority) plus the emergent
    reactive-P production / precipitation-loss competition and a P-mass
    conservation residual."""

    contract = {
        "summary": "Real libRoadRunner phosphorus-speciation network: is reactive P produced faster than it precipitates/adsorbs, and does a thermal pore co-concentrate P?",
        "description": (
            "A closed Antimony/SBML phosphorus network — condensation of dissolved "
            "phosphate to polyphosphate, activation to reactive P, relaxation/"
            "hydrolysis, and a reversible precipitation/adsorption mineral sink — "
            "integrated every step by the genuine libRoadRunner ODE engine. The "
            "thermal-gradient pore enrichment (coupled from og-03) drives the "
            "condensation (enr^2) and activation (enr) routes while precipitation is "
            "first-order in phosphate, so the enrichment decides whether phosphate "
            "becomes reactive (useful) or precipitates (lost). Emits the P pools, the "
            "reactive-P production vs precipitation-loss fluxes, the net availability, "
            "the precipitated fraction and a P-mass residual, all as overwrite sensors."
        ),
        "inputs": {
            "phosphate_supply": "dissolved orthophosphate supply / initial pool (molar)",
            "pore_enrichment": "thermal-gradient pore enrichment factor from the og-03 trap (dimensionless, >=1; 1 = open pore / no gradient)",
            "temperature": "mean pore temperature (kelvin) — Arrhenius factor on condensation + activation",
        },
        "outputs": {
            "phosphate": "dissolved orthophosphate (molar)",
            "polyphosphate": "condensed polyphosphate, P-atom units (molar)",
            "reactive_P": "reactive / activated phosphorus (molar)",
            "mineral_P": "mineral-bound (precipitated/adsorbed) phosphorus (molar)",
            "reactive_P_production": "reactive-P formation flux (mole/second)",
            "phosphate_loss": "precipitation + adsorption loss flux (mole/second)",
            "net_reactive_P": "reactive-P production - precipitation loss (mole/second); >0 = reactive P wins the race",
            "precipitated_fraction": "mineral_P / total P (dimensionless, 0-1)",
            "p_mass_residual": "|total P - supplied| / supplied (dimensionless, ~machine eps)",
        },
        "assumptions": [
            "Closed P-atom-conserving network (total P fixed by the supply), integrated as an ODE CSTR-less batch.",
            "Condensation is steeply concentration-dependent (enr^2) — the thermal pore makes two phosphates meet; activation scales with enr.",
            "Precipitation/adsorption is first-order in dissolved phosphate with slow desorption (a finite, reversible mineral sink).",
        ],
        "math": [
            "Rcond = k_cond*Tfac*enr^2*phosphate ; Ract = k_act*Tfac*enr*polyP",
            "Rprec = k_prec*phosphate (loss_rate) ; Rdes = k_des*mineralP",
            "net_reactive_P = Ract - Rprec ; precipitated_fraction = mineralP / total_P",
        ],
        "symbols": {
            "enr": "pore enrichment (dimensionless)", "Tfac": "Arrhenius temperature factor",
            "k_cond": "condensation rate", "k_act": "activation rate",
            "k_prec": "precipitation/adsorption loss rate (loss_rate)", "k_des": "desorption rate",
        },
        "references": ["pasek2017schreibersite", "baaske2007extreme", "mast2010thermal"],
    }

    config_schema = {
        "k_cond": {"_type": "float", "_default": 0.004, "_units": "1/second"},  # enrichment-gated condensation
        "k_phyd": {"_type": "float", "_default": 0.01, "_units": "1/second"},
        "k_act": {"_type": "float", "_default": 0.5, "_units": "1/second"},
        "k_hyd": {"_type": "float", "_default": 0.02, "_units": "1/second"},
        "k_prec": {"_type": "float", "_default": 0.08, "_units": "1/second"},  # precipitation LOSS (loss_rate)
        "k_des": {"_type": "float", "_default": 0.002, "_units": "1/second"},   # desorption (finite sink)
        "t_ref": {"_type": "float", "_default": 333.15, "_units": "kelvin"},
        "t_scale": {"_type": "float", "_default": 40.0, "_units": "kelvin"},
        "reactor_volume_scale": {"_type": "float", "_default": 1.0, "_units": "liter"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._rr = None
        self._t = 0.0
        self._total_p0 = None
        self._fluxes = {}

    def inputs(self):
        return {"phosphate_supply": _MOLAR, "pore_enrichment": _DIMLESS, "temperature": _K}

    def outputs(self):
        return {
            "phosphate": _OW_MOLAR, "polyphosphate": _OW_MOLAR,
            "reactive_P": _OW_MOLAR, "mineral_P": _OW_MOLAR,
            "reactive_P_production": _OW_MOLS, "phosphate_loss": _OW_MOLS,
            "net_reactive_P": _OW_MOLS,
            "precipitated_fraction": _OW_DIMLESS, "p_mass_residual": _OW_DIMLESS,
        }

    def initial_state(self):
        return {"phosphate_supply": 1.0e-4, "pore_enrichment": 30.0, "temperature": 333.15}

    def _engine(self, supply):
        if self._rr is None:
            import tellurium as te  # lazy — real libRoadRunner/Antimony bridge
            self._rr = te.loada(_MODEL)
            for k in ("k_cond", "k_phyd", "k_act", "k_hyd", "k_prec", "k_des"):
                setattr(self._rr, k, float(self.config[k]))
            self._rr.phosphate = float(supply)
            self._rr.polyP = 0.0
            self._rr.reactiveP = 0.0
            self._rr.mineralP = 0.0
            self._total_p0 = float(supply)
        return self._rr

    def _tfac(self, temperature) -> float:
        import math
        t_ref = float(self.config["t_ref"]); t_scale = max(float(self.config["t_scale"]), 1e-6)
        return float(math.exp((float(temperature) - t_ref) / t_scale))

    def update(self, state, interval):
        supply = max(float(state.get("phosphate_supply", 1.0e-4)), 0.0)
        rr = self._engine(supply)
        rr.enr = max(float(state.get("pore_enrichment", 30.0)), 1.0)
        rr.Tfac = self._tfac(state.get("temperature", 333.15))
        dt = max(float(interval), 1e-6)
        rr.simulate(self._t, self._t + dt, 2)
        self._t += dt

        try:
            self._fluxes = dict(zip(rr.getReactionIds(), (float(r) for r in rr.getReactionRates())))
        except Exception:  # noqa: BLE001
            self._fluxes = {}

        phosphate = float(rr.phosphate); polyp = float(rr.polyP)
        reactivep = float(rr.reactiveP); mineralp = float(rr.mineralP)
        vol = max(float(self.config["reactor_volume_scale"]), 1e-12)
        k_act = float(rr.k_act); k_prec = float(rr.k_prec)
        tfac = float(rr.Tfac); enr = float(rr.enr)
        # Reactive-P formation flux vs the precipitation/adsorption loss flux.
        react_prod = k_act * tfac * enr * polyp * vol
        precip_loss = k_prec * phosphate * vol
        net_reactive = react_prod - precip_loss

        total_p = phosphate + polyp + reactivep + mineralp
        p0 = self._total_p0 if self._total_p0 else max(total_p, 1e-30)
        residual = abs(total_p - p0) / max(p0, 1e-30)
        precipitated = mineralp / max(total_p, 1e-30)

        return {
            "phosphate": phosphate, "polyphosphate": polyp,
            "reactive_P": reactivep, "mineral_P": mineralp,
            "reactive_P_production": react_prod, "phosphate_loss": precip_loss,
            "net_reactive_P": net_reactive,
            "precipitated_fraction": precipitated, "p_mass_residual": residual,
        }


# Species-pool snapshot for the viz — the four P pools + their live fluxes.
_P_SPECIES = ["phosphate", "polyphosphate", "reactive_P", "mineral_P"]


def speciation_state(proc: "PhosphorusSpeciationProcess") -> dict:
    """Live P-pool concentrations (M) + live per-reaction fluxes from the real
    libRoadRunner model. Returns ``{species, conc, fluxes}``; zeros if the model
    has not been built yet."""
    rr = getattr(proc, "_rr", None)
    attr = {"phosphate": "phosphate", "polyphosphate": "polyP",
            "reactive_P": "reactiveP", "mineral_P": "mineralP"}
    conc = []
    for s in _P_SPECIES:
        try:
            conc.append(float(getattr(rr, attr[s])) if rr is not None else 0.0)
        except Exception:
            conc.append(0.0)
    return {"species": list(_P_SPECIES), "conc": conc,
            "fluxes": dict(getattr(proc, "_fluxes", {}) or {})}
