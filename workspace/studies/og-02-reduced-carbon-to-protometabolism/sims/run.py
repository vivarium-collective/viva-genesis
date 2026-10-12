#!/usr/bin/env python3
"""Canonical run for og-02 — reduced carbon to protometabolism (real libRoadRunner).

Runs the rTCA-fragment CSTR, persists an isolated sqlite store, and auto-grades
the three behavior tests (sustained throughput / autocatalytic gain / network
connectivity) via the workspace derived-scalar evaluator.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = STUDY_DIR.parents[2]

SPEC_ID = "viva_genesis.composites.campaign2.og_02_reduced_carbon_to_protometabolism"
STUDY_SLUG = "og-02-reduced-carbon-to-protometabolism"
INVESTIGATION_SLUG = "origins-of-life-vent"
N_STEPS = 120


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


def main() -> int:
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.core import build_core
    from viva_genesis.composites.campaign2 import og_02_reduced_carbon_to_protometabolism
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
            "label": "Reduced carbon to protometabolism", "started_at": time.time(),
            "status": "running", "n_steps": N_STEPS, "emitter": "sqlite",
            "origin": "canonical_run", "study_slug": STUDY_SLUG,
            "investigation_slug": INVESTIGATION_SLUG, "params": {},
        })

    core = build_core()
    sim = Composite({"state": og_02_reduced_carbon_to_protometabolism(core)}, core=core)
    sim.run(float(N_STEPS))
    rows = gather_emitter_results(sim)[("emitter",)]
    _write_store(STUDY_DIR / store_rel, rows, run_id)
    _upsert_run_entry(study_yaml, run_id, store_rel)
    summary = evaluate_on_run_completion(STUDY_DIR, run_id, ws_root=WORKSPACE_ROOT,
                                         overwrite_authored=True)
    print("grading:", summary)

    if append_run_event:
        append_run_event(WORKSPACE_ROOT, {
            "run_id": run_id, "event": "completed", "completed_at": time.time(),
            "n_steps": N_STEPS, "status": "completed",
        })
    print(f"canonical run complete: {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
