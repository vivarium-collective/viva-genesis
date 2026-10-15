#!/usr/bin/env python3
"""Canonical run for og-08-alt-robust-innovation-set — the integrated world, full set.

Runs ``integrated_autonomy_world`` at the canonical structure (thioester store,
rna_like heredity, single-chain fatty-acid boundary at the extrapolated
permeability anchor, the multisolute transport surrogate, the constant
maintenance law) with all three innovations on, at the first Phase-1 posterior
draw and the nominal ocean floor, for 300 ticks of 60 s — one hour in the vent,
100 minutes of withdrawal, 140 minutes off-gradient — with the seven ledgers
and the structural-event log beside it; persists an isolated per-run sqlite
store the behavior-test evaluator can open, grades the run-level gates (every
ledger closed, the ablation completed, events logged, the autonomy
decomposition) into ``runs[].outcomes`` and appends the run to
``.pbg/runs.jsonl``. The cross-structure gates (the lattice, the required
intersection, the generic control) read the committed artifact written by
``compute_robust_innovation_set.py``.

Run it with the workspace venv:  ``python workspace/studies/og-08-alt-robust-innovation-set/sims/run.py``
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = STUDY_DIR.parents[2]

SPEC_ID = "viva_genesis.composites.integrated_autonomy.integrated_autonomy_world"
STUDY_SLUG = "og-08-alt-robust-innovation-set"
INVESTIGATION_SLUG = "origins-of-life-vent"
N_TICKS = 300
TICK_SECONDS = 60.0
PARAMS = {"model_energy_coupling": "thioester_acyl_phosphate", "model_heredity": "rna_like", "model_boundary": "single_chain",
          "permeability_anchor": "extrapolated", "model_localization": "multisolute_surrogate", "maintenance_law": "constant",
          "pump": "on", "importer": "on", "heredity": "on", "feed_floor": 1.0e-2}


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
    import roadrunner
    roadrunner.Logger.setLevel(roadrunner.Logger.LOG_ERROR)
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.core import build_core
    from viva_genesis.composites.integrated_autonomy import integrated_autonomy_world
    from viva_genesis.uq.phase1_posterior import posterior_draws

    params = {**PARAMS, **posterior_draws()[0]["endmember"]}
    run_id = f"{SPEC_ID}__{int(time.time())}__{uuid.uuid4().hex[:6]}"
    store_rel = f"canonical-runs/{run_id}/run.db"
    store_abs = STUDY_DIR / store_rel
    try:
        from vivarium_workbench.lib.run_log import append_run_event
        append_run_event(WORKSPACE_ROOT, {
            "run_id": run_id, "event": "started", "spec_id": SPEC_ID,
            "label": "Integrated autonomy world (Phase 9, full innovation set, canonical structure)", "started_at": time.time(),
            "status": "running", "n_steps": N_TICKS, "emitter": "sqlite",
            "origin": "canonical_run", "study_slug": STUDY_SLUG,
            "investigation_slug": INVESTIGATION_SLUG, "params": params,
        })
    except Exception:
        append_run_event = None  # type: ignore

    core = build_core()
    sim = Composite({"state": integrated_autonomy_world(core, **params)}, core=core)
    sim.run(float(N_TICKS) * TICK_SECONDS)
    rows = gather_emitter_results(sim)[("emitter",)]
    # the event tree is cumulative; keep only the final one in the last row so the store stays small
    slim = []
    for i, r in enumerate(rows):
        d = {k: v for k, v in r.items() if k != "events"}
        if i == len(rows) - 1:
            d["events"] = r.get("events", {})
        slim.append(d)
    _write_sqlite_store(store_abs, slim, run_id)
    _upsert_run_entry(STUDY_DIR / "study.yaml", run_id, store_rel, params)

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
                                          "completed_at": time.time(), "n_steps": N_TICKS,
                                          "status": "completed"})
    last = rows[-1]
    print(f"canonical run complete: {run_id}\n  store: {store_rel}\n  final: "
          + json.dumps({k: last[k] for k in ("ablation_phase", "net_power", "material_net", "machinery", "autonomy",
                                                "autonomy_work", "autonomy_material", "autonomy_information", "survivors",
                                                "n_alive", "event_count", "geology_ledger_ok", "charge_ledger_ok",
                                                "network_ledger_ok", "element_ledger_ok", "free_energy_ledger_ok",
                                                "information_ledger_ok", "rewrite_ok")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
