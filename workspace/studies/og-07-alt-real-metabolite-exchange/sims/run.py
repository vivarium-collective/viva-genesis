#!/usr/bin/env python3
"""Canonical run for og-07-alt-real-metabolite-exchange — the two-lineage community.

Runs ``metabolite_exchange_community`` with ``lineages = fixer:4,reducer:4``
(the carboxylating and the hydrogenating lineage interleaved along the pore)
at the canonical operating point (diacid permeability 1e-8 m/s, residence
100 s), the Phase-3 universe inside every agent, the exchange rules firing
on the Phase-4-shaped field and the cross-system C/N/P ledger beside them,
for 250 ticks; persists an isolated per-run sqlite store the behavior-test
evaluator can open, grades the run-level gates (element ledger closed,
exchange rules fired, cross-lineage flux, no cell complete, og-07's
robustness readouts) into ``runs[].outcomes`` and appends the run to
``.pbg/runs.jsonl``. The cross-arm gates (community-function-precedes-cell-
completeness, the private / generalist / null controls, the emergence
boundary) read the committed artifact written by
``compute_community_function_map.py``.

Run it with the workspace venv:  ``python workspace/studies/og-07-alt-real-metabolite-exchange/sims/run.py``
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = STUDY_DIR.parents[2]

SPEC_ID = "viva_genesis.composites.metabolite_exchange_community.metabolite_exchange_community"
STUDY_SLUG = "og-07-alt-real-metabolite-exchange"
INVESTIGATION_SLUG = "origins-of-life-vent"
N_STEPS = 250
PARAMS = {"lineages": "fixer:4,reducer:4", "p_diacid": 1.0e-8, "p_monoacid": 1.0e-7, "k_wash": 0.01}


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
    from viva_genesis.composites.metabolite_exchange_community import metabolite_exchange_community

    run_id = f"{SPEC_ID}__{int(time.time())}__{uuid.uuid4().hex[:6]}"
    store_rel = f"canonical-runs/{run_id}/run.db"
    store_abs = STUDY_DIR / store_rel
    try:
        from vivarium_workbench.lib.run_log import append_run_event
        append_run_event(WORKSPACE_ROOT, {
            "run_id": run_id, "event": "started", "spec_id": SPEC_ID,
            "label": "Metabolite-exchange community (Phase 8, fixer + reducer lineages)", "started_at": time.time(),
            "status": "running", "n_steps": N_STEPS, "emitter": "sqlite",
            "origin": "canonical_run", "study_slug": STUDY_SLUG,
            "investigation_slug": INVESTIGATION_SLUG, "params": PARAMS,
        })
    except Exception:
        append_run_event = None  # type: ignore

    core = build_core()
    sim = Composite({"state": metabolite_exchange_community(core, **PARAMS)}, core=core)
    sim.run(float(N_STEPS))
    rows = gather_emitter_results(sim)[("emitter",)]
    # the per-cell field and per-agent rate trees are not needed by the gates; keep the store small
    slim = [{k: v for k, v in r.items() if k not in ("field", "rates")} for r in rows]
    _write_sqlite_store(store_abs, slim, run_id)
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
          + json.dumps({k: last[k] for k in ("metacommunity_robustness", "isolated_robustness", "robustness_gain",
                                                "luca_capability_overlap", "n_functions_union", "max_cell_completeness",
                                                "exchange_firings_total", "cross_lineage_flux_total", "C_residual_max",
                                                "N_residual_max", "P_residual_max", "element_ledger_ok")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
