#!/usr/bin/env python3
"""Canonical run for og-growth-alt — physical reproduction.

Runs the founder lineage as the canonical run: a founder individual grows to the
division threshold and divides by a _divide structural rewrite (matter + volume
halved); the daughters grow and divide in turn, building a multi-generation
lineage in the agents map. Writes a committed JSON report
(``artifacts/physical_reproduction_report.json``) holding the run series + a
headline block, persists an isolated sqlite store, and auto-grades the two
derived gates — ``peak_generation`` (the deepest generation REACHED, not the
time-mean) and ``partition_residual_peak`` (worst split residual) — which read
the committed artifact (not the gitignored run.db), so every number verifies
from the tree.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = STUDY_DIR.parents[2]

SPEC_ID = "viva_genesis.composites.physical_reproduction.physical_reproduction"
STUDY_SLUG = "og-growth-alt-physical-reproduction"
INVESTIGATION_SLUG = "origins-of-life-vent"
N_STEPS = 30
ARTIFACT_REL = "artifacts/physical_reproduction_report.json"
_PARAMS = {"growth_per_step": 0.4, "founder_volume": 8.0e-12,
           "founder_formate": 8.0, "founder_acetate": 4.0}


def _run(core, **params):
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.composites.physical_reproduction import physical_reproduction
    sim = Composite({"state": physical_reproduction(core, **params)}, core=core)
    sim.run(float(N_STEPS))
    return gather_emitter_results(sim)[("emitter",)]


def _series(rows, key):
    return [float(r.get(key, 0.0)) for r in rows]


def _write_artifact(rows) -> dict:
    art = STUDY_DIR / ARTIFACT_REL
    art.parent.mkdir(parents=True, exist_ok=True)
    gen = _series(rows, "max_generation")
    vol = _series(rows, "total_volume")
    presid = _series(rows, "partition_residual_max")
    rewrite = _series(rows, "rewrite_ok")
    founder_v = float(_PARAMS["founder_volume"])
    report = {
        "study": STUDY_SLUG,
        "spec_id": SPEC_ID,
        "n_steps": N_STEPS,
        "params": _PARAMS,
        "series": {k: _series(rows, k) for k in
                   ("n_agents", "max_generation", "total_volume", "partition_residual_max")},
        "headline": {
            # the deepest generation the lineage REACHES (peak), not the time-mean
            "peak_generation": float(max(gen)) if gen else 0.0,
            "final_n_agents": float(rows[-1]["n_agents"]),
            "founder_volume": founder_v,
            "final_total_volume": float(vol[-1]) if vol else 0.0,
            "volume_conserved": bool(vol and abs(vol[-1] - founder_v) <= 1e-15),
            # worst split residual over the whole lineage (0 => every _divide conserved)
            "partition_residual_peak": float(max(presid)) if presid else 0.0,
            "rewrite_conservation_ok": float(min(rewrite)) if rewrite else 0.0,
        },
    }
    art.write_text(json.dumps(report, indent=1))
    return report["headline"]


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
    from viva_genesis.core import build_core
    from vivarium_workbench.lib.auto_evaluate import evaluate_on_run_completion

    run_id = f"{SPEC_ID}__{int(time.time())}__{uuid.uuid4().hex[:6]}"
    store_rel = f"canonical-runs/{run_id}/run.db"
    study_yaml = STUDY_DIR / "study.yaml"

    core = build_core()
    rows = _run(core, **_PARAMS)
    headline = _write_artifact(rows)
    print("artifact headline:", json.dumps(headline))

    _write_store(STUDY_DIR / store_rel, rows, run_id)
    _upsert_run_entry(study_yaml, run_id, store_rel)
    summary = evaluate_on_run_completion(STUDY_DIR, run_id, ws_root=WORKSPACE_ROOT,
                                         overwrite_authored=True)
    print("gate grading:", summary)
    try:
        from viva_genesis.viz import render_declared_viz_json
        print("viz.json panels:", render_declared_viz_json(STUDY_DIR, run_id, WORKSPACE_ROOT))
    except Exception as _viz_exc:  # noqa: BLE001
        print("viz render skipped:", _viz_exc)
    print(f"canonical run complete: {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
