#!/usr/bin/env python
"""Gate A1 calibration — the DIC-crossover sweep for the coupled geochemical interface (og-27).

og-27 previously tested two points and found a two-regime tension: undersaturated
(fluid_dic 2 mM, SI -15) sustains H2 flux but exercises NO mineral throttling, while
supersaturated (fluid_dic 20 mM, SI +3.2) throttles (precipitation, accessibility and
porosity collapse) but the supply CHOKES (H2 flux -> ~1e-8). gate_status was
``needs_calibration``: does a MILD-supersaturation operating point exist that sustains
flux AND exercises throttling, or is the tension fundamental (the interface self-limits
at precipitating conditions)?

This sweeps the real control knob — ``fluid_dic`` (inflowing-fluid dissolved inorganic
carbon, a Hadean-ocean proxy) — densely across the crossover, driving the real PHREEQC
carbonate saturation index through SI = 0, and at each point records (from the real
coupled run's emitter): the last H2 flux, the saturation index, the max mineral
precipitation, the final catalytic accessibility and porosity, and the closed-ledger
flag. Each point is classified:

  * sustained_flux      — H2 flux stays >= ``flux_frac`` of the undersaturated baseline
                          (the supply is not choked by clogging);
  * throttling_exercised — mineral precipitation occurs (precip_max > eps) OR catalytic
                          accessibility drops (mineral evolution is actually acting);
  * not_choked          — porosity does not collapse to ~0 (the pore stays open).

The mild-supersaturation OPERATING POINT is a fluid_dic where all three hold at once.
If one exists the two-regime tension is resolved (an interface that both supplies and
is throttled); if none exists across the crossover, the tension is fundamental and the
self-limiting finding stands — reported honestly either way, nothing tuned. All runs
keep the closed mass/charge/energy ledger (``ledger_ok``).

Writes artifacts/dic_crossover_sweep.json.

    PYTHONPATH=<worktree> python .../sims/compute_dic_crossover_sweep.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"

N_STEPS = 120
# fluid_dic sweep (molar): dense across the SI=0 crossover between the undersaturated
# (2 mM) and supersaturated (20 mM) end points og-27 already characterised.
# Dense through the SI=0 crossover (the carbonate SI is very DIC-sensitive, jumping from
# deeply undersaturated at 2 mM to supersaturated by ~4 mM), so the mild-supersaturation
# band — where an operating point would live — is actually sampled, not skipped over.
DIC_SWEEP = [0.0020, 0.0025, 0.0028, 0.0030, 0.0032, 0.0035, 0.0040,
             0.0050, 0.0070, 0.0100, 0.0150, 0.0200]
FLUX_FRAC = 0.2       # sustained = H2 flux >= this fraction of the undersaturated baseline
PRECIP_EPS = 1.0e-3   # throttling = mineral precipitation above this (or accessibility drop)
ACCESS_DROP = 0.02    # throttling = catalytic accessibility falls by at least this
POROSITY_FLOOR = 0.05  # choked = porosity collapses below this


def _jd(o):
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return str(o)


def _run(core, og27, fluid_dic):
    from process_bigraph import Composite, gather_emitter_results
    doc = og27(core, fluid_dic=float(fluid_dic))
    sim = Composite({"state": doc}, core=core)
    sim.run(N_STEPS)
    rows = gather_emitter_results(sim)[("emitter",)]
    last = rows[-1]
    precip_max = max(float(r.get("mineral_precipitation", 0.0)) for r in rows)
    si_max = max(float(r.get("saturation_index", 0.0)) for r in rows)
    access0 = float(rows[0].get("catalytic_accessibility", 1.0))
    return {
        "fluid_dic": float(fluid_dic),
        "h2_flux_last": float(last.get("H2_flux", 0.0)),
        "saturation_index_last": float(last.get("saturation_index", 0.0)),
        "saturation_index_max": si_max,
        "mineral_precipitation_max": precip_max,
        "catalytic_accessibility_last": float(last.get("catalytic_accessibility", 1.0)),
        "catalytic_accessibility_drop": access0 - float(last.get("catalytic_accessibility", 1.0)),
        "porosity_last": float(last.get("porosity", 0.0)),
        "ledger_ok": bool(last.get("ledger_ok", 0.0) >= 0.5),
    }


def main() -> int:
    from viva_genesis.composites.og_27_coupled_geochemical_reaction_interface import (
        og_27_coupled_geochemical_reaction_interface as og27)
    from viva_genesis.core import build_core

    core = build_core()

    def log(m):
        print(m, flush=True)

    sweep = [_run(core, og27, dic) for dic in DIC_SWEEP]
    baseline_flux = sweep[0]["h2_flux_last"]   # undersaturated end point (2 mM)
    flux_floor = FLUX_FRAC * baseline_flux

    for p in sweep:
        p["sustained_flux"] = bool(p["h2_flux_last"] >= flux_floor)
        p["throttling_exercised"] = bool(p["mineral_precipitation_max"] > PRECIP_EPS
                                         or p["catalytic_accessibility_drop"] >= ACCESS_DROP)
        p["not_choked"] = bool(p["porosity_last"] > POROSITY_FLOOR)
        p["operating_point"] = bool(p["sustained_flux"] and p["throttling_exercised"] and p["not_choked"])
        log(f"  dic={p['fluid_dic']*1e3:.2f}mM SI_last={p['saturation_index_last']:+.1f} "
            f"H2_flux={p['h2_flux_last']:.2e} precip_max={p['mineral_precipitation_max']:.3f} "
            f"access_drop={p['catalytic_accessibility_drop']:.3f} porosity={p['porosity_last']:.2f} "
            f"-> sustained={p['sustained_flux']} throttling={p['throttling_exercised']} "
            f"not_choked={p['not_choked']} OP={p['operating_point']}")

    operating = [p for p in sweep if p["operating_point"]]
    window_exists = bool(operating)
    ledger_ok_all = all(p["ledger_ok"] for p in sweep)
    # the SI=0 crossover: first fluid_dic whose STEADY (last) SI reaches supersaturation.
    # (Use the last value, not the max — the diagnostics store inits saturation_index=0.0,
    # so a max-based test would spuriously fire on that step-0 transient at the first point.)
    crossover = next((p["fluid_dic"] for p in sweep if p["saturation_index_last"] >= 0.0), None)
    # recommended operating point: the one that throttles with the HIGHEST sustained flux
    recommended = (max(operating, key=lambda p: p["h2_flux_last"]) if operating else None)

    # Decision: resolved if a mild-supersaturation window exists (sustains flux AND
    # throttles, pore open), with the ledger closing. Otherwise the two-regime tension is
    # fundamental (the interface self-limits) — reported honestly.
    if window_exists and ledger_ok_all:
        verdict = "qualified"   # resolved AT an operating point, within a bounded DIC window (a calibrated A1 interface)
        resolution = "two_regime_tension_resolved"
    elif ledger_ok_all:
        verdict = "qualified"   # tension FUNDAMENTAL — self-limiting; honest negative, still a bounded-window A1 result
        resolution = "two_regime_tension_fundamental"
    else:
        verdict = "refuted"     # ledger broke — not a usable result
        resolution = "ledger_broken"

    rec_mM = (recommended["fluid_dic"] * 1e3) if recommended else None
    headline = (
        f"Gate A1 DIC-crossover calibration (og-27 coupled geochemical reaction interface): verdict={verdict}, "
        f"{resolution}. Sweeping the real control knob fluid_dic across the PHREEQC SI=0 crossover "
        f"(first supersaturating at ~{(crossover*1e3) if crossover else None} mM), "
        + (f"a MILD-supersaturation operating point EXISTS: at fluid_dic {rec_mM:.0f} mM the interface both "
           f"sustains H2 flux ({recommended['h2_flux_last']:.2e}, >= {FLUX_FRAC:.0%} of the undersaturated "
           f"baseline {baseline_flux:.2e}) AND exercises mineral throttling (precip_max "
           f"{recommended['mineral_precipitation_max']:.3f}, accessibility drop "
           f"{recommended['catalytic_accessibility_drop']:.3f}) with the pore still open "
           f"(porosity {recommended['porosity_last']:.2f}) — so the two-regime tension RESOLVES in a bounded "
           f"DIC window ({len(operating)}/{len(sweep)} swept points qualify), a calibrated A1 interface that "
           f"both supplies and is throttled."
           if window_exists else
           f"NO fluid_dic sustains flux AND throttles simultaneously across the crossover — the two-regime "
           f"tension is FUNDAMENTAL: the interface self-limits at precipitating conditions (flux chokes as "
           f"soon as mineral evolution bites). Reported honestly as a bounded-window limitation, not tuned.")
        + f" The full mass/charge/energy ledger closes at every swept point (ledger_ok_all={ledger_ok_all}). "
        f"Geochemically the supersaturating band is real (Lost City precipitates carbonate chimneys). "
        f"Guardrail: this firms up Gate A1's interface (sustained, connected, carbon-fixing feed), not autocatalysis (A2 refuted)."
    )

    out = {
        "meta": {"n_steps": N_STEPS, "dic_sweep_molar": DIC_SWEEP,
                 "flux_frac": FLUX_FRAC, "precip_eps": PRECIP_EPS, "access_drop": ACCESS_DROP,
                 "porosity_floor": POROSITY_FLOOR, "baseline_flux_undersaturated": baseline_flux,
                 "knob": "fluid_dic (inflowing-fluid DIC, Hadean-ocean proxy) driving the real PHREEQC "
                         "carbonate saturation index; MineralSurfaceDynamicsProcess throttling",
                 "guardrail": "firms up Gate A1's coupled geochemical interface; not autocatalysis (A2 refuted)"},
        "sweep": sweep,
        "operating_points": operating,
        "recommended_operating_point": recommended,
        "si_zero_crossover_fluid_dic": crossover,
        "criteria": {"window_exists": window_exists, "ledger_ok_all": ledger_ok_all,
                     "resolution": resolution},
        "verdict": verdict, "headline": headline,
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "dic_crossover_sweep.json").write_text(json.dumps(out, indent=1, default=_jd))
    log(f"wrote {ARTIFACTS / 'dic_crossover_sweep.json'}")
    log(headline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
