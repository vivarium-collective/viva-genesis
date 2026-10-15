#!/usr/bin/env python3
"""Canonical run for og-energy-alt-internalization-threshold — one protocell, thioester class, half activity.

Runs ``protocell_energetics`` with ``model_energy_coupling = thioester_acyl_phosphate``
at ``coupling_activity = 0.5`` on the nominal vg-data membrane and gradient
(P_H 1e-6 m/s, external pmf 0.216 V, 300 ticks of 10 s) with the
FreeEnergyLedgerProcess beside it, persists an isolated per-run sqlite store the
behavior-test evaluator can open, grades the ledger / autonomy gates into
``runs[].outcomes`` and appends the run to ``.pbg/runs.jsonl``. The cross-class
gates (internalization-pays, thresholds per class, structure agreement) read the
committed artifact written by ``compute_internalization_threshold.py``.

Run it with the workspace venv:  ``python workspace/studies/og-energy-alt-internalization-threshold/sims/run.py``
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = STUDY_DIR.parents[2]

SPEC_ID = "viva_genesis.composites.protocell_energetics.protocell_energetics"
STUDY_SLUG = "og-energy-alt-internalization-threshold"
INVESTIGATION_SLUG = "origins-of-life-vent"
N_STEPS = 300
PARAMS = {"model_energy_coupling": "thioester_acyl_phosphate", "coupling_activity": 0.5}


def _write_sqlite_store(db_path: Path, rows: list[dict], sim_id: str) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(str(db_path))
    con.execute("CREATE TABLE history (simulation_id TEXT, step INTEGER, global_time REAL, state TEXT)")
    for i, r in enumerate(rows):
        con.execute("INSERT INTO history VALUES (?,?,?,?)",
                    (sim_id, i, float(r.get("global_time", i)), json.dumps(r)))
    con.commit()
    con.close()


def _upsert_run_entry(study_yaml: Path, run_id: str, store_rel: str, params: dict) -> None:
    import ruamel.yaml
    ryaml = ruamel.yaml.YAML()
    ryaml.preserve_quotes = True
    ryaml.width = 4096
    with open(study_yaml, encoding="utf-8") as fh:
        doc = ryaml.load(fh)
    runs = doc.get("runs")
    if not isinstance(runs, list):
        runs = ryaml.load("[]")
        doc["runs"] = runs
    entry = ryaml.load("{}")
    entry["name"] = run_id
    entry["status"] = "completed"
    entry["timestamp"] = time.time()
    entry["canonical"] = True
    em = ryaml.load("{}")
    em["kind"] = "sqlite"
    em["store"] = store_rel
    entry["emitter"] = em
    entry["store_path"] = store_rel
    entry["params"] = json.dumps(params)
    runs[:] = [r for r in runs if r.get("canonical") is not True]
    runs.append(entry)
    tmp = study_yaml.with_suffix(".yaml.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        ryaml.dump(doc, fh)
    tmp.replace(study_yaml)


def main() -> int:
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.core import build_core
    from viva_genesis.composites.protocell_energetics import protocell_energetics

    run_id = f"{SPEC_ID}__{int(time.time())}__{uuid.uuid4().hex[:6]}"
    store_rel = f"canonical-runs/{run_id}/run.db"
    store_abs = STUDY_DIR / store_rel
    try:
        from vivarium_workbench.lib.run_log import append_run_event
        append_run_event(WORKSPACE_ROOT, {
            "run_id": run_id, "event": "started", "spec_id": SPEC_ID,
            "label": "Protocell energetics (Phase 6, thioester, activity 0.5)", "started_at": time.time(),
            "status": "running", "n_steps": N_STEPS, "emitter": "sqlite",
            "origin": "canonical_run", "study_slug": STUDY_SLUG,
            "investigation_slug": INVESTIGATION_SLUG, "params": PARAMS,
        })
    except Exception:
        append_run_event = None  # type: ignore

    core = build_core()
    sim = Composite({"state": protocell_energetics(core, **PARAMS)}, core=core)
    sim.run(float(N_STEPS))
    rows = gather_emitter_results(sim)[("emitter",)]
    _write_sqlite_store(store_abs, rows, run_id)
    _upsert_run_entry(STUDY_DIR / "study.yaml", run_id, store_rel, PARAMS)

    from vivarium_workbench.lib.auto_evaluate import evaluate_on_run_completion
    summary = evaluate_on_run_completion(STUDY_DIR, run_id, ws_root=WORKSPACE_ROOT, overwrite_authored=True)
    print("evaluate_on_run_completion:", summary)
    try:
        from viva_genesis.viz import render_declared_viz_json
        print("viz.json panels:", render_declared_viz_json(STUDY_DIR, run_id, WORKSPACE_ROOT))
    except Exception as exc:  # noqa: BLE001
        print("viz render skipped:", exc)
    if append_run_event is not None:
        append_run_event(WORKSPACE_ROOT, {"run_id": run_id, "event": "completed",
                                          "completed_at": time.time(), "n_steps": N_STEPS,
                                          "status": "completed"})
    last = rows[-1]
    print(f"canonical run complete: {run_id}\n  store: {store_rel}\n  final: "
          + json.dumps({k: last[k] for k in ("net_power", "internal_power", "external_power", "autonomy",
                                                "store_potential", "energy_charge_fraction",
                                                "free_energy_residual_max", "second_law_margin_min",
                                                "capture_efficiency", "free_energy_ledger_ok")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
