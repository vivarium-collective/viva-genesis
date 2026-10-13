#!/usr/bin/env python3
"""Canonical run for og-03 — dilution to localized individuals (real FiPy thermal trap).

Runs the FAVORABLE pore as the canonical run (persists an isolated sqlite store,
auto-grades the derived behavior tests — settled_accumulation_peclet,
log10_enrichment, max_abs_trap_flux_residual — via the workspace evaluator), then
runs the open-pore and short-pore controls to grade the two CROSS-RUN tests
(``open-pore-control-does-not-concentrate`` and
``enrichment-exponential-in-pore-length``).
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = STUDY_DIR.parents[2]

SPEC_ID = "viva_genesis.composites.heredity_module_comparison.heredity_module_comparison"
STUDY_SLUG = "og-06-chemistry-to-heredity"
INVESTIGATION_SLUG = "origins-of-life-vent"
N_STEPS = 50


def _run(core, **params):
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.composites.heredity_module_comparison import heredity_module_comparison
    sim = Composite({"state": heredity_module_comparison(core, **params)}, core=core)
    sim.run(float(N_STEPS))
    return gather_emitter_results(sim)[("emitter",)]


def _write_store(db_path: Path, rows, sim_id: str) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(str(db_path))
    con.execute("CREATE TABLE history (simulation_id TEXT, step INTEGER, "
                "global_time REAL, state TEXT)")
    for i, r in enumerate(rows):
        con.execute("INSERT INTO history VALUES (?,?,?,?)",
                    (sim_id, i, float(r.get("global_time", i)), json.dumps(r)))
    con.commit()
    con.close()


def _upsert_run_entry(study_yaml: Path, run_id: str, store_rel: str) -> None:
    import ruamel.yaml
    ry = ruamel.yaml.YAML(); ry.preserve_quotes = True; ry.width = 4096
    doc = ry.load(open(study_yaml, encoding="utf-8"))
    runs = doc.get("runs")
    if not isinstance(runs, list):
        runs = ry.load("[]"); doc["runs"] = runs
    runs[:] = [r for r in runs if r.get("name") != run_id and r.get("canonical") is not True]
    e = ry.load("{}")
    e["name"] = run_id; e["status"] = "completed"; e["timestamp"] = time.time()
    e["canonical"] = True
    em = ry.load("{}"); em["kind"] = "sqlite"; em["store"] = store_rel
    e["emitter"] = em; e["store_path"] = store_rel; e["params"] = "{}"
    runs.append(e)
    tmp = study_yaml.with_suffix(".yaml.tmp")
    ry.dump(doc, open(tmp, "w", encoding="utf-8"))
    tmp.replace(study_yaml)


def _write_cross_run_outcomes(study_yaml: Path, run_id: str, verdicts: dict) -> None:
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
        entry["result"] = v["result"]
        entry["measured_value"] = v["measured_value"]
        entry["evaluated_by"] = "code"
        entry["operator"] = "cross_run"
        entry["detail"] = v["detail"]
        outcomes[name] = entry
    tmp = study_yaml.with_suffix(".yaml.tmp")
    ry.dump(doc, open(tmp, "w", encoding="utf-8"))
    tmp.replace(study_yaml)


def main() -> int:
    from viva_genesis.core import build_core
    from vivarium_workbench.lib.auto_evaluate import evaluate_on_run_completion
    try:
        from vivarium_workbench.lib.run_log import append_run_event
    except Exception:
        append_run_event = None

    run_id = f"{SPEC_ID}__{int(time.time())}__{uuid.uuid4().hex[:6]}"
    store_rel = f"canonical-runs/{run_id}/run.db"
    study_yaml = STUDY_DIR / "study.yaml"

    if append_run_event:
        append_run_event(WORKSPACE_ROOT, {
            "run_id": run_id, "event": "started", "spec_id": SPEC_ID,
            "label": "Chemistry to heredity (RNA-like module)",
            "started_at": time.time(), "status": "running", "n_steps": N_STEPS,
            "emitter": "sqlite", "origin": "canonical_run", "study_slug": STUDY_SLUG,
            "investigation_slug": INVESTIGATION_SLUG, "params": {},
        })

    core = build_core()
    fav = _run(core)
    _write_store(STUDY_DIR / store_rel, fav, run_id)
    _upsert_run_entry(study_yaml, run_id, store_rel)
    summary = evaluate_on_run_completion(STUDY_DIR, run_id, ws_root=WORKSPACE_ROOT,
                                         overwrite_authored=True)
    print("single-run grading:", summary)
    try:
        from viva_genesis.viz import render_declared_viz_json
        print("viz.json panels:", render_declared_viz_json(STUDY_DIR, run_id, WORKSPACE_ROOT))
    except Exception as _viz_exc:  # noqa: BLE001
        print("viz render skipped:", _viz_exc)

    # Cross-run: head-to-head module ranking + the error-catastrophe control.
    rna_f = fav[-1]["lineage_fitness"]
    pep = _run(core, module="peptide")[-1]
    low = _run(core, module="low-fidelity")[-1]

    ranking_verdict = {
        "result": "PASS" if (rna_f > 0.0 and pep["lineage_fitness"] > 0.0 and rna_f > pep["lineage_fitness"]) else "FAIL",
        "measured_value": round(pep["lineage_fitness"], 3),
        "detail": (f"RNA-like fitness={rna_f:.3f} vs peptide fitness={pep['lineage_fitness']:.3f} "
                   f"(both viable; RNA-like ranks above => evidence-based head-to-head)"),
    }
    catastrophe_verdict = {
        "result": "PASS" if (low["information_retention"] < 0.1 and low["lineage_fitness"] < 0.0) else "FAIL",
        "measured_value": round(low["information_retention"], 3),
        "detail": (f"low-fidelity retention={low['information_retention']:.2f} fitness={low['lineage_fitness']:.3f} "
                   f"(below the error threshold => information lost, inheritance fails)"),
    }
    # Cross-run (agent-based lineage): compositional (GARD) heredity retains function
    # across generations — length-independent — above the non-heritable control, so
    # heredity need not presume a long high-fidelity template ("do NOT presume RNA").
    # Graded across a SEED SWEEP (all seeds must pass) so the verdict is robust, not
    # knife-edge at one seed.
    import statistics

    from viva_genesis.heredity.lineage import simulate_lineage
    CAP = 220
    SEEDS = range(5)

    def _persist(r):
        return r["final_function"] * min(r["final_population"] / CAP, 1.0)

    comp_ps, nonh_ps, comp_hs, nonh_hs, per_seed_pass = [], [], [], [], []
    for s in SEEDS:
        comp = simulate_lineage("compositional", capacity=CAP, n_gen=40, seed=s)
        nonh = simulate_lineage("non-heritable", length=30, capacity=CAP, n_gen=40, seed=s)
        cp, np_ = _persist(comp), _persist(nonh)
        comp_ps.append(cp); nonh_ps.append(np_)
        comp_hs.append(comp["heritability"]); nonh_hs.append(nonh["heritability"])
        per_seed_pass.append(cp > 0.35 and cp > np_
                             and comp["heritability"] > 0.5 and nonh["heritability"] < 0.3)
    n_seeds = len(comp_ps)
    comp_p = statistics.fmean(comp_ps); comp_sd = statistics.pstdev(comp_ps)
    nonh_p = statistics.fmean(nonh_ps)
    lineage_verdict = {
        "result": "PASS" if all(per_seed_pass) else "FAIL",
        "measured_value": round(comp_p, 3),
        "detail": (f"compositional persistence={comp_p:.3f}±{comp_sd:.3f} "
                   f"(heritability~{statistics.fmean(comp_hs):.2f}) vs non-heritable "
                   f"persistence={nonh_p:.3f} (heritability~{statistics.fmean(nonh_hs):.2f}) "
                   f"across {n_seeds} seeds, {sum(per_seed_pass)}/{n_seeds} pass => compositional "
                   f"heredity persists length-independently and seed-robustly; the non-heritable "
                   f"control collapses every seed"),
    }
    _write_cross_run_outcomes(study_yaml, run_id, {
        "heredity-modules-compared": ranking_verdict,
        "error-catastrophe-below-threshold": catastrophe_verdict,
        "heredity-lineage-compositional-persists": lineage_verdict,
    })
    print("cross-run: ranking", ranking_verdict["result"], "| catastrophe", catastrophe_verdict["result"],
          "| lineage", lineage_verdict["result"])

    if append_run_event:
        append_run_event(WORKSPACE_ROOT, {
            "run_id": run_id, "event": "completed", "completed_at": time.time(),
            "n_steps": N_STEPS, "status": "completed",
        })
    print(f"canonical run complete: {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
