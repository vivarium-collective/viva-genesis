#!/usr/bin/env python3
"""Canonical run for og-proto-energetics — a transferable energy currency before pumping.

Runs the favourable proto_energetics arm as the canonical run (persists an isolated
sqlite store, auto-grades the derived behavior tests — energy_final_charge_fraction,
energy_stored_work_fraction, energy_ledger_residual — via the workspace evaluator),
then runs the no-coupling and no-drive ablations to grade the CROSS-RUN test
(``ablation-no-coupling-or-drive-collapses``).
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = STUDY_DIR.parents[2]

SPEC_ID = "viva_genesis.composites.proto_energetics.proto_energetics"
STUDY_SLUG = "og-energy-proto-energetics"
INVESTIGATION_SLUG = "origins-of-life-vent"
N_STEPS = 60


def _run(core, **params):
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.composites.proto_energetics import proto_energetics
    sim = Composite({"state": proto_energetics(core, **params)}, core=core)
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
            "label": "Proto-energetics (favourable: strong drive, efficient coupling)",
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

    # Cross-run ablation: no coupling (coupling_efficiency -> 0) or no drive (ΔG below
    # the carrier bond) -> the currency never charges. Both controls must collapse
    # where the favourable arm maintains the store.
    fav_cf = fav[-1]["energy_charge_fraction"]
    no_coupling_cf = _run(core, coupling_efficiency=0.0)[-1]["energy_charge_fraction"]
    no_drive_cf = _run(core, drive_free_energy=10.0)[-1]["energy_charge_fraction"]
    collapsed = max(no_coupling_cf, no_drive_cf)
    ablation_verdict = {
        "result": "PASS" if (fav_cf >= 0.25 and collapsed < 0.05) else "FAIL",
        "measured_value": round(collapsed, 4),
        "detail": (f"favourable charged fraction={fav_cf:.3f} vs no-coupling={no_coupling_cf:.3f} / "
                   f"no-drive={no_drive_cf:.3f} (both ablations collapse => the currency needs BOTH "
                   f"the coupling and a drive that clears the carrier bond)"),
    }
    _write_cross_run_outcomes(study_yaml, run_id, {
        "ablation-no-coupling-or-drive-collapses": ablation_verdict,
    })
    print("cross-run: ablation", ablation_verdict["result"])

    if append_run_event:
        append_run_event(WORKSPACE_ROOT, {
            "run_id": run_id, "event": "completed", "completed_at": time.time(),
            "n_steps": N_STEPS, "status": "completed",
        })
    print(f"canonical run complete: {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
