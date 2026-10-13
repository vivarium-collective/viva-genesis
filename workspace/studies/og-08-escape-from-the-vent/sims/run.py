#!/usr/bin/env python3
"""Canonical run for og-08 — escape from the vent (off-gradient persistence).

Runs the FULL innovation set (internal pump + resource importer + heredity) under
withdrawing geological support as the canonical run (persists an isolated sqlite
store, auto-grades the derived behavior test ``offgradient_survival`` via the
workspace evaluator), then runs the three single-knockout controls (-pump,
-importer, -heredity) to grade the CROSS-RUN ``minimum-innovation-set`` test: each
necessary innovation's removal collapses off-gradient persistence, so the minimum
robust set is {pump, importer, heredity}.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = STUDY_DIR.parents[2]

SPEC_ID = "viva_genesis.composites.off_gradient_persistence.off_gradient_persistence"
STUDY_SLUG = "og-08-escape-from-the-vent"
INVESTIGATION_SLUG = "origins-of-life-vent"
N_STEPS = 60


def _run(core, **params):
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.composites.off_gradient_persistence import off_gradient_persistence
    sim = Composite({"state": off_gradient_persistence(core, **params)}, core=core)
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
            "label": "Escape from the vent (full innovation set)",
            "started_at": time.time(), "status": "running", "n_steps": N_STEPS,
            "emitter": "sqlite", "origin": "canonical_run", "study_slug": STUDY_SLUG,
            "investigation_slug": INVESTIGATION_SLUG, "params": {},
        })

    core = build_core()
    # Canonical run: the FULL innovation set under withdrawing geological support.
    full = _run(core)
    _write_store(STUDY_DIR / store_rel, full, run_id)
    _upsert_run_entry(study_yaml, run_id, store_rel)
    summary = evaluate_on_run_completion(STUDY_DIR, run_id, ws_root=WORKSPACE_ROOT,
                                         overwrite_authored=True)
    print("single-run grading:", summary)
    try:
        from viva_genesis.viz import render_declared_viz_json
        print("viz.json panels:", render_declared_viz_json(STUDY_DIR, run_id, WORKSPACE_ROOT))
    except Exception as _viz_exc:  # noqa: BLE001
        print("viz render skipped:", _viz_exc)

    # Cross-run: the knockout sweep. Each single innovation removed must collapse
    # off-gradient persistence (the set is irreducible), identifying the minimum
    # robust innovation set for autonomy.
    full_s = full[-1]["survivors"]
    ko = {
        "pump": _run(core, has_pump=0)[-1]["survivors"],
        "importer": _run(core, has_importer=0)[-1]["survivors"],
        "heredity": _run(core, has_heredity=0)[-1]["survivors"],
    }
    necessary = [k for k, s in ko.items() if s < 0.1]
    all_collapse = all(s < 0.1 for s in ko.values())
    min_set_verdict = {
        "result": "PASS" if (full_s >= 0.5 and all_collapse) else "FAIL",
        "measured_value": round(max(ko.values()), 3),
        "detail": (f"full set survivors={full_s:.2f} off-gradient; knockouts "
                   f"-pump={ko['pump']:.2f} -importer={ko['importer']:.2f} "
                   f"-heredity={ko['heredity']:.2f} (each necessary => minimum robust set = "
                   f"{{{', '.join(sorted(necessary))}}})"),
    }
    _write_cross_run_outcomes(study_yaml, run_id, {
        "minimum-innovation-set": min_set_verdict,
    })
    print("cross-run: minimum-innovation-set", min_set_verdict["result"],
          "| necessary:", necessary)

    if append_run_event:
        append_run_event(WORKSPACE_ROOT, {
            "run_id": run_id, "event": "completed", "completed_at": time.time(),
            "n_steps": N_STEPS, "status": "completed",
        })
    print(f"canonical run complete: {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
