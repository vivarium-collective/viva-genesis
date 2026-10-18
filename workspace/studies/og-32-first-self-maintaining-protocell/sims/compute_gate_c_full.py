#!/usr/bin/env python
"""Full Gate C (Option B, MD-INFORMED) — does an MD-coupled endogenous membrane let
the metabolism SELF-MAINTAIN and beat a matched no-membrane ablation at equal feeds?
(study og-32-first-self-maintaining-protocell)

Tests the ⚑1 measurable self-maintenance criterion on the Gate-B pore-concentrated A1
(sustained, NOT autocatalytic) network, with membrane permeability INFORMED BY short
Martini CG-MD of the amphiphile composition (og_32 composite; MD-informed structural
proxy, NOT a PMF-resolved closure — that is Option A / study og-32a):

  (i)  membrane integrity: net amphiphile production >= degradation
         production  = eta_amph * (metabolism productive flux)            [metabolism supply]
         degradation = k_deg * M_req                                      [hydrolytic demand of the
                                                                           membrane needed to enclose]
       maintained iff production >= degradation.
  (ii) benefit over the matched no-endogenous-membrane ablation (permeability OPEN,
       retention 0) at feeds held EQUAL: membrane beats ablation on productive flux OR
       persistence (standing organic-carbon pool).

Self-maintaining (Gate C met) iff (i) AND (ii). Failing either is a reported negative
(not self-maintaining, or a net cost), not tuned. A boundary sweep over the MD
compositions (short vs long chain) + k_deg locates where self-maintenance holds, so the
result is WINDOWED, not a single favorable point.

The eta_amph / k_deg / M_req parameters are declared model parameters (NOT tuned to
pass); the composition->permeability->retention relation constants are a labelled
proposed_input (see the composite). The metabolism is the sustained A1 network, NOT
autocatalytic (A2 refuted under vent conditions).

Writes artifacts/gate_c_full.json. C4 network for speed.

    PYTHONPATH=<worktree> python .../sims/compute_gate_c_full.py
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"

# --- membrane-integrity model parameters (declared; NOT tuned to pass) ------------------- #
ETA_AMPH = 0.10          # fraction of productive carbon flux routed to amphiphile elongation (og-17 chemistry)
K_DEG = 1.0e-4           # amphiphile hydrolytic degradation rate [1/s]
M_REQ = 1.0e-3           # standing membrane pool required to enclose the compartment [molar]
BASE_CO2 = BASE_H2 = 1.0e-3
POROSITY = 0.88
K_WASH = 0.05
N_STEPS = 90
# spans both sides of the integrity boundary (production/M_req) so the window is bracketed
K_DEG_SWEEP = [1.0e-4, 5.0e-4, 1.0e-3, 5.0e-3, 1.0e-2, 5.0e-2, 1.0e-1, 5.0e-1]


def _jd(o):
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return str(o)


def _run(core, og32, *, membrane, composition="long_di-C16"):
    from process_bigraph import Composite
    doc = og32(core, membrane=membrane, composition=composition,
               base_CO2=BASE_CO2, base_H2=BASE_H2, porosity=POROSITY, k_wash=K_WASH, max_carbons=4)
    sim = Composite({"state": doc}, core=core)
    sim.run(N_STEPS)
    st = sim.state
    return {
        "total_organic_carbon": float(st["net"].get("total_organic_carbon", 0.0)),
        "net_carbon_flux": float(st["flux"].get("net_carbon_flux", 0.0)),
        "n_persistent_species": float(st["stats"].get("n_persistent_species", 0.0)),
    }


def _integrity(flux, *, eta_amph=ETA_AMPH, k_deg=K_DEG, m_req=M_REQ):
    """(production, degradation, net, maintained) — supply vs hydrolytic demand."""
    production = eta_amph * abs(flux)
    degradation = k_deg * m_req
    net = production - degradation
    return production, degradation, net, bool(net >= 0.0)


def main() -> int:
    from viva_genesis.composites.og_32_first_self_maintaining_protocell import (
        MD_THICKNESS_NM, composition_retention, og_32_first_self_maintaining_protocell as og32)
    from viva_genesis.core import build_core

    core = build_core()
    t0 = time.time()

    def log(m):
        print(m, flush=True)

    # 1. membrane (long, aggregation-competent composition) vs matched ablation, equal feeds ---- #
    membrane = _run(core, og32, membrane=True, composition="long_di-C16")
    ablation = _run(core, og32, membrane=False)
    d_long, p_long, ret_long = composition_retention("long_di-C16")

    prod_m, deg_m, int_m, maintained = _integrity(membrane["net_carbon_flux"])
    toc_benefit = membrane["total_organic_carbon"] / max(ablation["total_organic_carbon"], 1e-30)
    flux_benefit = membrane["net_carbon_flux"] / max(abs(ablation["net_carbon_flux"]), 1e-30)
    persistence_pays = bool(membrane["total_organic_carbon"] > ablation["total_organic_carbon"])
    throughput_pays = bool(membrane["net_carbon_flux"] > ablation["net_carbon_flux"])
    beats_ablation = bool(persistence_pays or throughput_pays)
    self_maintaining = bool(maintained and beats_ablation)

    log(f"MD-informed (long di-C16, thickness {d_long} nm -> permeability {p_long:.3f} -> retention {ret_long:.3f}):")
    log(f"  MEMBRANE TOC={membrane['total_organic_carbon']:.3e} flux={membrane['net_carbon_flux']:+.3e} | "
        f"ABLATION TOC={ablation['total_organic_carbon']:.3e} flux={ablation['net_carbon_flux']:+.3e}")
    log(f"  integrity: production={prod_m:.3e} >= degradation={deg_m:.3e} ? maintained={maintained} (net={int_m:+.3e})")
    log(f"  benefit: persistence {toc_benefit:.2f}x (pays={persistence_pays}), "
        f"throughput {flux_benefit:.2f}x (pays={throughput_pays}) -> beats_ablation={beats_ablation}")
    log(f"  SELF-MAINTAINING (integrity AND benefit) = {self_maintaining}")

    # 2. boundary: composition (short vs long) + k_deg sweep -> where self-maintenance holds ---- #
    comp_boundary = []
    for comp in ("short_di-C12", "long_di-C16"):
        r = _run(core, og32, membrane=True, composition=comp)
        d, p, ret = composition_retention(comp)
        _pr, _dg, _net, _maint = _integrity(r["net_carbon_flux"])
        pays = bool(r["total_organic_carbon"] > ablation["total_organic_carbon"])
        comp_boundary.append({"composition": comp, "thickness_nm": d, "permeability": p, "retention": ret,
                              "total_organic_carbon": r["total_organic_carbon"],
                              "net_carbon_flux": r["net_carbon_flux"],
                              "persistence_pays": pays, "integrity_maintained": _maint})
        log(f"  comp {comp} (d={d}nm ret={ret:.3f}): TOC={r['total_organic_carbon']:.3e} "
            f"persistence_pays={pays} integrity={_maint}")

    kdeg_boundary = []
    for kd in K_DEG_SWEEP:
        _pr, _dg, _net, _maint = _integrity(membrane["net_carbon_flux"], k_deg=kd)
        kdeg_boundary.append({"k_deg": kd, "degradation": _dg, "net_integrity": _net, "maintained": _maint})
    maint_kdegs = [b["k_deg"] for b in kdeg_boundary if b["maintained"]]
    kdeg_boundary_max = max(maint_kdegs) if maint_kdegs else None   # highest degradation still self-maintained
    log(f"  k_deg boundary: self-maintains up to k_deg <= {kdeg_boundary_max} (1/s)")

    # verdict: met iff self-maintaining on both flux AND persistence; qualified if integrity + one benefit
    # branch (e.g. persistence not throughput, mirroring og-31's feed-limited throughput); refuted otherwise.
    if self_maintaining and persistence_pays and throughput_pays:
        verdict = "met"
    elif self_maintaining:
        verdict = "qualified"
    else:
        verdict = "refuted"

    headline = (
        f"Full Gate C (Option B, MD-INFORMED structural proxy — NOT PMF-resolved): verdict={verdict}. On the "
        f"Gate-B pore-concentrated A1 (sustained, non-autocatalytic) network, membrane permeability is informed "
        f"by short Martini CG-MD of the amphiphile composition (long di-C16 bilayer thickness {d_long} nm vs "
        f"short di-C12 {MD_THICKNESS_NM['short_di-C12']} nm; thicker long-chain core -> lower permeability "
        f"{p_long:.3f} -> retention {ret_long:.3f}). Self-maintenance is the measurable ⚑1 criterion: (i) net "
        f"amphiphile production {prod_m:.2e} {'>=' if maintained else '<'} degradation {deg_m:.2e} "
        f"(maintained={maintained}), AND (ii) the membrane beats the matched no-endogenous-membrane ablation at "
        f"equal feeds on persistence {toc_benefit:.2f}x (pays={persistence_pays}) / throughput {flux_benefit:.2f}x "
        f"(pays={throughput_pays}). Self-maintaining={self_maintaining}. The result is WINDOWED: integrity holds "
        f"up to k_deg <= {kdeg_boundary_max} 1/s, and persistence benefit tracks the MD composition (thicker = "
        f"more retention). NOT strict autopoietic closure; the metabolism is the A1 network, not autocatalytic "
        f"(A2 refuted). PMF-resolved permeability (Option A, study og-32a) is the budgeted gold-standard follow-on."
    )
    out = {
        "meta": {"wall_time_s": time.time() - t0, "network": "C4", "porosity": POROSITY,
                 "base_feed": BASE_CO2, "k_wash": K_WASH,
                 "coupling": "MD-INFORMED (short Martini CG-MD bilayer thickness -> published solubility-diffusion "
                             "relation -> permeability -> retention) — NOT PMF-resolved (Option A = og-32a)",
                 "md_source": "real short Martini 3 CG-MD on the mini (viva-openmm/martini_openmm); "
                              "sims/run_md_bilayer_observables.py; md_bilayer_observables.json",
                 "md_thickness_nm": MD_THICKNESS_NM,
                 "integrity_params": {"eta_amph": ETA_AMPH, "k_deg": K_DEG, "m_req": M_REQ,
                                      "note": "declared model parameters, NOT tuned to pass"},
                 "guardrail": "metabolism = sustained A1 carbon-fixing network, NOT autocatalytic (A2 refuted)",
                 "scope": "Option B MD-informed structural proxy; Option A PMF-resolved permeability = study og-32a (budgeted)"},
        "benefit_demo": {"membrane": membrane, "ablation": ablation, "toc_benefit": toc_benefit,
                         "flux_benefit": flux_benefit, "persistence_pays": persistence_pays,
                         "throughput_pays": throughput_pays, "beats_ablation": beats_ablation},
        "membrane_integrity": {"production": prod_m, "degradation": deg_m, "net_integrity": int_m,
                               "maintained": maintained, "permeability": p_long, "retention": ret_long,
                               "thickness_nm": d_long},
        "self_maintaining": self_maintaining,
        "boundary": {"composition": comp_boundary, "k_deg": kdeg_boundary,
                     "k_deg_boundary_max": kdeg_boundary_max},
        "verdict": verdict, "headline": headline,
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "gate_c_full.json").write_text(json.dumps(out, indent=1, default=_jd))
    log(f"wrote {ARTIFACTS / 'gate_c_full.json'} ({time.time() - t0:.0f}s)")
    log(headline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
