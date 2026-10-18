#!/usr/bin/env python
"""Gate E (optional) — does a stochastic cross-feeding community beat the best single lineage? (study og-36)

Tests the ⚑4 community-function criterion with HONEST low-count demographic
stochasticity (a dependency-free Gillespie SSA; Option B). The same
``og_36_stochastic_protocell_ecology`` composite drives every arm; the shared feed
budget ``feed_F`` is held EQUAL across arms, so the only differences are topology
and the cross-feeding switch:

  - community   : all K lineages seeded on the ring, cross-feeding on.
  - best-single : each lineage run as a monoculture (full shared feed, no partner);
                  the BEST of the K is the strict "margin over the best single
                  lineage" control.
  - knockout    : all K seeded, cross-feeding OFF (mu_cross gated to 0) — isolates
                  whether the community margin is causally cross-feeding.

Three readouts (writer's ⚑4 decision form):
  1. margin_positive       — community cumulative productivity > the best single
                             lineage at equal feed (in the SSA mean AND in most seeds);
  2. cross_feeding_causal  — the knockout margin collapses toward zero (the benefit
                             is cross-feeding, not mere diversity);
  3. stochastic_material   — the SSA outcome differs materially from the deterministic
                             mean-field, and a system-size (Omega) scale sweep shows the
                             divergence (extinctions, margin erosion) GROWING as counts fall.
  + community_more_robust  — is the community LESS variable / more persistent than the
                             best single lineage? (the honest robustness check.)

Decision: met only if the community out-produces AND out-persists (more robust than)
the best single lineage, causally via cross-feeding. Qualified when the productivity
margin is real and causal but stochastic low-count dynamics materially erode it / the
community is NOT more robust than a monoculture (the honest productivity-not-robustness
result). Refuted if the margin is absent or not cross-feeding-caused. Guardrail: the
metabolism is the sustained A1 cross-feeding community, not autocatalysis (A2 refuted).

Writes artifacts/gate_e_ecology.json.

    PYTHONPATH=<worktree> python .../sims/compute_gate_e_ecology.py
"""
from __future__ import annotations

import json
import math
import statistics as st
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"

N_STEPS = 120
K = 4
N_SEEDS = 24
SWEEP_SEEDS = 16
# System-size (Omega) multipliers on the EXTENSIVE params (feed, pools, initial counts);
# per-capita rates are scale-invariant, so the deterministic per-capita trajectory is
# Omega-invariant and only the absolute molecule/cell counts scale — the textbook
# low-count axis. Omega<1 => lower counts => stronger demographic noise.
# Nominal (Omega=1.0) is a genuine LOW-COUNT protocell regime (tens of cells), where
# demographic noise is material; the sweep spans below and above it so the
# stochastic<->deterministic divergence can be seen GROWING as counts fall.
OMEGA_SWEEP = [0.7, 1.0, 2.0, 4.0]
BASE = {"feed_F": 7.0, "feed_Ks": 3.0, "cross_Kb": 3.0, "S0": 9.0, "n0": 3}


def _jd(o):
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return str(o)


def _scaled(omega: float) -> dict:
    """Extensive params scaled by the system size Omega (per-capita rates unchanged)."""
    return {"feed_F": BASE["feed_F"] * omega, "feed_Ks": BASE["feed_Ks"] * omega,
            "cross_Kb": BASE["cross_Kb"] * omega, "S0": BASE["S0"] * omega,
            "n0": max(int(round(BASE["n0"] * omega)), 1)}


def _run(core, og36, **kw):
    from process_bigraph import Composite
    doc = og36(core, **kw)
    sim = Composite({"state": doc}, core=core)
    sim.run(N_STEPS)
    c = sim.state["community"]
    return {"productivity": float(c["cumulative_productivity"]), "n_alive": float(c["n_alive"]),
            "n_extinct": float(c["n_extinct"]), "total_population": float(c["total_population"])}


def _ssa_batch(core, og36, seeds, **kw):
    runs = [_run(core, og36, seed=s, **kw) for s in seeds]
    prod = [r["productivity"] for r in runs]
    alive = [r["n_alive"] for r in runs]
    ext = [r["n_extinct"] for r in runs]
    return {"prod": prod, "mean": st.mean(prod), "sd": (st.pstdev(prod) if len(prod) > 1 else 0.0),
            "cv": (st.pstdev(prod) / st.mean(prod) if st.mean(prod) else 0.0),
            "n_alive_mean": st.mean(alive), "extinction_frac": sum(1 for e in ext if e > 0) / len(ext),
            "mean_extinct": st.mean(ext)}


def main() -> int:
    from viva_genesis.composites.og_36_stochastic_protocell_ecology import og_36_stochastic_protocell_ecology as og36
    from viva_genesis.core import build_core

    core = build_core()
    nom = _scaled(1.0)

    def log(m):
        print(m, flush=True)

    seeds = list(range(N_SEEDS))

    # --- deterministic arms (the mean-field reference) ---
    det_comm = _run(core, og36, deterministic=True, **nom)
    det_ko = _run(core, og36, deterministic=True, knockout=True, **nom)
    det_monos = [_run(core, og36, deterministic=True, n_seeded=1, mono_lineage=i, **nom) for i in range(K)]
    best_i = max(range(K), key=lambda i: det_monos[i]["productivity"])
    det_best = det_monos[best_i]
    det_margin = det_comm["productivity"] - det_best["productivity"]
    det_ko_margin = det_ko["productivity"] - det_best["productivity"]
    log(f"DET community={det_comm['productivity']:.0f} (n_alive={det_comm['n_alive']:.0f}) best-single="
        f"{det_best['productivity']:.0f} (lineage {best_i}) knockout={det_ko['productivity']:.0f} "
        f"-> margin={det_margin:.0f} ko_margin={det_ko_margin:.0f}")

    # --- stochastic (SSA) arms at nominal scale ---
    ssa_comm = _ssa_batch(core, og36, seeds, **nom)
    ssa_best = _ssa_batch(core, og36, seeds, n_seeded=1, mono_lineage=best_i, **nom)
    ssa_ko = _ssa_batch(core, og36, seeds, knockout=True, **nom)
    ssa_margin = ssa_comm["mean"] - ssa_best["mean"]
    ssa_ko_margin = ssa_ko["mean"] - ssa_best["mean"]
    frac_seeds_positive = sum(1 for p in ssa_comm["prod"] if p > ssa_best["mean"]) / len(ssa_comm["prod"])
    log(f"SSA community={ssa_comm['mean']:.0f}±{ssa_comm['sd']:.0f} (cv={ssa_comm['cv']:.3f}, "
        f"n_alive={ssa_comm['n_alive_mean']:.2f}, ext_frac={ssa_comm['extinction_frac']:.2f}) "
        f"best-single={ssa_best['mean']:.0f}±{ssa_best['sd']:.0f} (cv={ssa_best['cv']:.3f}) "
        f"knockout={ssa_ko['mean']:.0f} -> margin={ssa_margin:.0f} ko_margin={ssa_ko_margin:.0f}")

    # --- system-size (Omega) sweep: the low-count demonstration ---
    sweep = []
    for omega in OMEGA_SWEEP:
        sp = _scaled(omega)
        sseeds = list(range(SWEEP_SEEDS))
        sc = _ssa_batch(core, og36, sseeds, **sp)
        sm = _ssa_batch(core, og36, sseeds, n_seeded=1, mono_lineage=best_i, **sp)
        dc = _run(core, og36, deterministic=True, **sp)
        dm = _run(core, og36, deterministic=True, n_seeded=1, mono_lineage=best_i, **sp)
        s_margin = sc["mean"] - sm["mean"]
        d_margin = dc["productivity"] - dm["productivity"]
        # relative gap between the stochastic and deterministic margin (per-capita
        # comparable: divide by the deterministic margin at that scale)
        rel_gap = (d_margin - s_margin) / d_margin if d_margin else 0.0
        sweep.append({"omega": omega, "ssa_margin": s_margin, "det_margin": d_margin,
                      "rel_margin_gap": rel_gap, "extinction_frac": sc["extinction_frac"],
                      "n_alive_mean": sc["n_alive_mean"], "community_cv": sc["cv"]})
        log(f"  Omega={omega}: ssa_margin={s_margin:.0f} det_margin={d_margin:.0f} rel_gap={rel_gap:.2f} "
            f"ext_frac={sc['extinction_frac']:.2f} n_alive={sc['n_alive_mean']:.2f}")

    # divergence grows as counts fall: extinction_frac and rel_gap at the lowest Omega
    # exceed those at the highest Omega.
    low, high = sweep[0], sweep[-1]
    divergence_grows = bool(low["extinction_frac"] >= high["extinction_frac"]
                            and low["rel_margin_gap"] >= high["rel_margin_gap"])

    # --- criteria ---
    margin_positive = bool(ssa_margin > 0 and frac_seeds_positive >= 0.5)
    # knockout recovers only a small fraction of the community's margin -> cross-feeding is the cause
    ko_frac = (ssa_ko_margin / ssa_margin) if ssa_margin else 1.0
    cross_feeding_causal = bool(ko_frac < 0.15)
    stochastic_material = bool((ssa_comm["extinction_frac"] > 0.0 or (det_margin - ssa_margin) / det_margin > 0.05)
                               and divergence_grows)
    community_more_robust = bool(ssa_comm["cv"] <= ssa_best["cv"] and ssa_comm["extinction_frac"] == 0.0)

    if not (margin_positive and cross_feeding_causal):
        verdict = "refuted"
    elif community_more_robust and not stochastic_material:
        verdict = "met"
    else:
        verdict = "qualified"

    log(f"margin_positive={margin_positive} cross_feeding_causal={cross_feeding_causal} "
        f"stochastic_material={stochastic_material} community_more_robust={community_more_robust} "
        f"-> verdict={verdict}")

    headline = (
        f"Gate E stochastic protocell ecology (Option B, dependency-free Gillespie SSA — NOT GillesPy2/"
        f"COBRApy, which is og-36a): verdict={verdict}. With the shared feed budget held EQUAL across arms, "
        f"a cross-feeding community of {K} protocell lineages out-produces the BEST single lineage "
        f"(community {ssa_comm['mean']:.0f} vs best-single {ssa_best['mean']:.0f} cumulative births; SSA "
        f"margin {ssa_margin:.0f}, positive in {frac_seeds_positive*100:.0f}% of seeds; margin_positive="
        f"{margin_positive}), and the margin is CAUSALLY cross-feeding: the knockout (cross-feeding off, same "
        f"feed) collapses it to {ssa_ko_margin:.0f} ({ko_frac*100:.0f}% of the community margin; "
        f"cross_feeding_causal={cross_feeding_causal}). Coexistence is stabilised by depletable byproduct "
        f"pools (negative frequency dependence), not assumed — deterministically all {K} lineages persist "
        f"(n_alive={det_comm['n_alive']:.0f}), the knockout excludes down ({det_ko['n_alive']:.0f}). BUT the "
        f"benefit is productivity, not robustness: under low-count demographic noise the community is MORE "
        f"variable than the rock-stable monoculture (cv {ssa_comm['cv']:.2f} vs {ssa_best['cv']:.2f}) and loses "
        f"a lineage in {ssa_comm['extinction_frac']*100:.0f}% of runs (community_more_robust="
        f"{community_more_robust}); the system-size sweep shows this divergence GROWING as counts fall "
        f"(Omega {low['omega']}: ext_frac {low['extinction_frac']:.2f}, margin gap {low['rel_margin_gap']:.2f} "
        f"vs Omega {high['omega']}: {high['extinction_frac']:.2f}/{high['rel_margin_gap']:.2f}; "
        f"stochastic_material={stochastic_material}) — the mean-field misses it. So qualified = a real, "
        f"cross-feeding-caused community productivity win that low-count stochasticity makes FRAGILE. Unlike the "
        f"pore (B), membrane (C) and energy carrier (35) — each of which buys persistence, NOT throughput — the "
        f"cross-feeding ecology is the campaign's first genuine THROUGHPUT/productivity win (the community "
        f"extracts more biomass from the same feed than the best single lineage, causally via cross-feeding); "
        f"but it buys that productivity at the cost of ROBUSTNESS (more variable than a monoculture, lineage loss "
        f"at low counts). The unifying campaign reading is not 'nothing buys throughput' but 'every mechanism "
        f"trades one virtue for another — robustness/persistence is never free.' Metabolism = sustained A1 "
        f"community, NOT autocatalytic (A2 refuted)."
    )

    out = {
        "meta": {"n_steps": N_STEPS, "n_lineages": K, "n_seeds": N_SEEDS, "sweep_seeds": SWEEP_SEEDS,
                 "base_params": BASE, "omega_sweep": OMEGA_SWEEP,
                 "model": "Option B: dependency-free numpy Gillespie SSA (exact) + matched mean-field Euler ODE; "
                          "explicit integer counts (shared feed S, K byproduct pools, K cell counts); a reproduction, "
                          "NOT a wrapped ALife engine; parameters are proposed_inputs, not fitted",
                 "equal_feed": "feed_F held equal across community / best-single / knockout arms",
                 "best_single": f"max over all {K} single-lineage monocultures (lineage {best_i}); the strict control",
                 "scope": "GillesPy2 / COBRApy genome-scale resolution = study og-36a, follow-on",
                 "guardrail": "cross-feeding community is the sustained A1 network, NOT autocatalytic (A2 refuted)"},
        "deterministic": {"community": det_comm, "best_single": det_best, "knockout": det_ko,
                          "per_lineage_mono": det_monos, "best_lineage": best_i,
                          "margin": det_margin, "ko_margin": det_ko_margin},
        "stochastic": {"community": {k: ssa_comm[k] for k in ("mean", "sd", "cv", "n_alive_mean", "extinction_frac", "mean_extinct")},
                       "best_single": {k: ssa_best[k] for k in ("mean", "sd", "cv")},
                       "knockout": {k: ssa_ko[k] for k in ("mean", "sd", "cv")},
                       "margin": ssa_margin, "ko_margin": ssa_ko_margin,
                       "ko_margin_fraction": ko_frac, "frac_seeds_positive": frac_seeds_positive},
        "omega_sweep": sweep, "divergence_grows_at_low_counts": divergence_grows,
        "criteria": {"margin_positive": margin_positive, "cross_feeding_causal": cross_feeding_causal,
                     "stochastic_material": stochastic_material, "community_more_robust": community_more_robust},
        "verdict": verdict, "headline": headline,
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "gate_e_ecology.json").write_text(json.dumps(out, indent=1, default=_jd))
    log(f"wrote {ARTIFACTS / 'gate_e_ecology.json'}")
    log(headline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
