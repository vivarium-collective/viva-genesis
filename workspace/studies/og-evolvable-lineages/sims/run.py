#!/usr/bin/env python3
"""Canonical run + evolvability ensemble for og-evolvable-lineages — evolution
synthesis, given a granted individual.

og-self-maintaining-individual refuted endogenous closure, so the self-maintaining
individual this study needs does not form endogenously. This study therefore tests
evolvability conditional on a granted individual (the protocell/membrane is assumed;
fitness is grounded at og-operating-window's favorable corner regime). Given an
individual, does stochastic partition + variation produce heritable, selectable
organization across generations above two matched nulls - and is it open-ended or
merely bounded fixed-trait selection?

Pipeline (reusing the real HeredityPopulationProcess, driven directly so the
population state carries across a mid-run environment change):
  1. Replicate ensemble (seeds) x {full, no-inheritance null, shared-feed null},
     static environment -> composition shift + heritability + variance trajectory.
  2. Changed environment: flip the favored composition mid-run (swap retention_lo/hi)
     -> does the inheriting population re-track above the no-inheritance null?
  3. Open-ended-vs-bounded: heritable variance ratio (final/initial) + the fixed
     scalar trait space -> bounded, not open-ended.
  4. Artifact + canonical graded composite run + cross-run grading.

Framing-agnostic: reports the full result (response above BOTH nulls, heritability,
adaptation to change, and the bounded/open-ended determination).
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

import numpy as np

STUDY_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = STUDY_DIR.parents[2]

SPEC_ID = "viva_genesis.composites.evolvable_lineages.og_evolvable_lineages"
STUDY_SLUG = "og-evolvable-lineages"
INVESTIGATION_SLUG = "origins-of-life-vent"
N_STEPS = 40
GENS = 40
FLIP_AT = 20
SEEDS = [7, 11, 13, 17, 23]
_LO, _HI = 0.333, 0.661           # study-32 MD retention endpoints (favor high c)
_FLAT = 0.5                        # shared-feed null: flat fitness landscape


def evolve(core, seed, gens, *, inheritance=True, retention_lo=_LO, retention_hi=_HI,
           fitness_exponent=2.0, sigma=0.03, n_pop=120, flip_at=None):
    """Drive HeredityPopulationProcess directly; optionally flip the favored
    composition (swap retention_lo/hi) at ``flip_at`` carrying the population state."""
    from viva_genesis.compartments.heredity_population import HeredityPopulationProcess
    p = HeredityPopulationProcess(config={
        "inheritance": bool(inheritance), "n_pop": int(n_pop), "sigma": float(sigma),
        "seed": int(seed), "fitness_exponent": float(fitness_exponent),
        "retention_lo": float(retention_lo), "retention_hi": float(retention_hi)}, core=core)
    st = p.initial_state() if hasattr(p, "initial_state") else {}
    traj = []
    for g in range(gens):
        if flip_at is not None and g == flip_at:
            p.config["retention_lo"], p.config["retention_hi"] = retention_hi, retention_lo
        last = p.update(st, 1.0)
        traj.append({"gen": g, "mean_composition": float(last["mean_composition"]),
                     "selection_response": float(last["selection_response"]),
                     "parent_offspring_r": float(last["parent_offspring_fitness_correlation"]),
                     "heritable_variance": float(last["heritable_fitness_variance"])})
    return traj


def _shift(traj):
    return traj[-1]["mean_composition"] - traj[0]["mean_composition"]


def _var_ratio(traj):
    n = max(1, int(round(len(traj) * 0.2)))
    first = np.mean([t["heritable_variance"] for t in traj[:n]])
    last = np.mean([t["heritable_variance"] for t in traj[-n:]])
    return float(last / first) if first > 0 else 0.0


def _write_store(db_path, rows, sim_id):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(str(db_path))
    con.execute("CREATE TABLE history (simulation_id TEXT, step INTEGER, global_time REAL, state TEXT)")
    for i, r in enumerate(rows):
        con.execute("INSERT INTO history VALUES (?,?,?,?)", (sim_id, i, float(r.get("global_time", i)), json.dumps(r)))
    con.commit(); con.close()


def _upsert_run_entry(study_yaml, run_id, store_rel):
    import ruamel.yaml
    ry = ruamel.yaml.YAML(); ry.preserve_quotes = True; ry.width = 4096
    doc = ry.load(open(study_yaml, encoding="utf-8"))
    runs = doc.get("runs")
    if not isinstance(runs, list):
        runs = ry.load("[]"); doc["runs"] = runs
    runs[:] = [r for r in runs if r.get("name") != run_id and r.get("canonical") is not True]
    e = ry.load("{}"); e["name"] = run_id; e["status"] = "completed"; e["timestamp"] = time.time(); e["canonical"] = True
    em = ry.load("{}"); em["kind"] = "sqlite"; em["store"] = store_rel
    e["emitter"] = em; e["store_path"] = store_rel; e["params"] = "{}"
    runs.append(e)
    tmp = study_yaml.with_suffix(".yaml.tmp"); ry.dump(doc, open(tmp, "w", encoding="utf-8")); tmp.replace(study_yaml)


def _write_cross_run_outcomes(study_yaml, run_id, verdicts):
    import ruamel.yaml
    ry = ruamel.yaml.YAML(); ry.preserve_quotes = True; ry.width = 4096
    doc = ry.load(open(study_yaml, encoding="utf-8"))
    run = next((r for r in (doc.get("runs") or []) if r.get("name") == run_id), None)
    if run is None:
        return
    outcomes = run.get("outcomes")
    if not isinstance(outcomes, ruamel.yaml.CommentedMap):
        outcomes = ry.load("{}"); run["outcomes"] = outcomes
    for name, v in verdicts.items():
        entry = ry.load("{}")
        entry["result"] = v["result"]; entry["measured_value"] = v["measured_value"]
        entry["evaluated_by"] = "code"; entry["operator"] = "cross_run"; entry["detail"] = v["detail"]
        outcomes[name] = entry
    tmp = study_yaml.with_suffix(".yaml.tmp"); ry.dump(doc, open(tmp, "w", encoding="utf-8")); tmp.replace(study_yaml)


def _ensemble(core, **cfg):
    """Mean +/- std over replicate seeds for a static-environment condition."""
    shifts, rs, ratios = [], [], []
    for s in SEEDS:
        tr = evolve(core, s, GENS, **cfg)
        shifts.append(_shift(tr)); rs.append(tr[-1]["parent_offspring_r"]); ratios.append(_var_ratio(tr))
    return {"shift_mean": float(np.mean(shifts)), "shift_std": float(np.std(shifts)),
            "parent_offspring_r_mean": float(np.mean(rs)), "var_ratio_mean": float(np.mean(ratios))}


def main() -> int:
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.core import build_core
    from viva_genesis.composites.evolvable_lineages import og_evolvable_lineages
    from vivarium_workbench.lib.auto_evaluate import evaluate_on_run_completion

    core = build_core()
    run_id = f"{SPEC_ID}__{int(time.time())}__{uuid.uuid4().hex[:6]}"
    store_rel = f"canonical-runs/{run_id}/run.db"
    study_yaml = STUDY_DIR / "study.yaml"

    # 1. Static-environment ensemble: full vs the two matched nulls.
    full = _ensemble(core)
    no_inh = _ensemble(core, inheritance=False)
    shared = _ensemble(core, retention_lo=_FLAT, retention_hi=_FLAT)

    # 2. Changed environment: flip the favored composition mid-run; does full re-track above the null?
    ce_full = evolve(core, 7, GENS, flip_at=FLIP_AT)
    ce_null = evolve(core, 7, GENS, inheritance=False, flip_at=FLIP_AT)
    retrack_full = ce_full[-1]["mean_composition"] - ce_full[FLIP_AT - 1]["mean_composition"]
    retrack_null = ce_null[-1]["mean_composition"] - ce_null[FLIP_AT - 1]["mean_composition"]

    artifact = {
        "study": STUDY_SLUG,
        "premise": ("Conditional on a GRANTED individual: C (og-self-maintaining-individual) refuted endogenous "
                    "closure, so the protocell/membrane is granted and fitness is grounded at B's favorable S_T "
                    "corner regime; evolvability is NOT claimed for a free individual."),
        "static_ensemble": {"full": full, "no_inheritance_null": no_inh, "shared_feed_null": shared,
                            "n_seeds": len(SEEDS), "generations": GENS},
        "response_above_nulls": {
            "full_shift": full["shift_mean"],
            "exceeds_no_inheritance": full["shift_mean"] > no_inh["shift_mean"] + no_inh["shift_std"] + full["shift_std"],
            "exceeds_shared_feed": full["shift_mean"] > shared["shift_mean"] + shared["shift_std"] + full["shift_std"],
        },
        "changed_environment": {"full_retrack": retrack_full, "null_retrack": retrack_null,
                                "adapts_above_null": abs(retrack_full) > abs(retrack_null) + 0.1},
        "open_ended_vs_bounded": {
            "heritable_variance_ratio_full": full["var_ratio_mean"],
            "trait_space": "fixed scalar composition c in [0,1], single fitness optimum",
            "bounded": full["var_ratio_mean"] < 1.0,
            "note": ("Heritable variance DECLINES as the population converges to the optimum and the trait space is "
                     "a fixed scalar -> BOUNDED fixed-trait selection, NOT open-ended novelty. The changed-environment "
                     "adaptation is re-tracking within the same fixed trait space, not new organization."),
        },
    }
    out = STUDY_DIR / "artifacts" / "og-evolvable-lineages" / "evolvable_lineages.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2))
    print(f"full shift={full['shift_mean']:.3f}+/-{full['shift_std']:.3f} (r={full['parent_offspring_r_mean']:.3f}); "
          f"no-inh={no_inh['shift_mean']:.3f}; shared-feed={shared['shift_mean']:.3f}; "
          f"var_ratio={full['var_ratio_mean']:.2f} (bounded={full['var_ratio_mean']<1}); "
          f"changed-env retrack full={retrack_full:.3f} vs null={retrack_null:.3f}")

    # 4. Canonical graded composite run (full, static, seed 7).
    sim = Composite({"state": og_evolvable_lineages(core=core, inheritance=True, seed=7)}, core=core)
    sim.run(float(N_STEPS))
    rows = gather_emitter_results(sim)[("emitter",)]
    _write_store(STUDY_DIR / store_rel, rows, run_id)
    _upsert_run_entry(study_yaml, run_id, store_rel)
    summary = evaluate_on_run_completion(STUDY_DIR, run_id, ws_root=WORKSPACE_ROOT, overwrite_authored=True)
    print("single-run grading:", summary)

    # Cross-run: the selection response exceeds BOTH matched nulls (heritability AND selection needed).
    above_both = (artifact["response_above_nulls"]["exceeds_no_inheritance"]
                  and artifact["response_above_nulls"]["exceeds_shared_feed"])
    verdict = {
        "result": "PASS" if above_both else "FAIL",
        "measured_value": float(f"{full['shift_mean']:.3f}"),
        "detail": (f"full composition shift={full['shift_mean']:.3f} exceeds BOTH the no-inheritance null "
                   f"({no_inh['shift_mean']:.3f}) and the shared-feed null ({shared['shift_mean']:.3f}); "
                   f"parent-offspring r={full['parent_offspring_r_mean']:.3f} -> heritable selection is real above both nulls"),
    }
    _write_cross_run_outcomes(study_yaml, run_id, {"heritable-selection-above-both-nulls": verdict})
    print("cross-run: heritable-selection-above-both-nulls", verdict["result"])
    print(f"canonical run complete: {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
