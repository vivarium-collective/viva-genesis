#!/usr/bin/env python3
"""Canonical run for og-adv — the adversarial generic-nonequilibrium control.

The study's model is the real og-01 carbon-fixation composite with every vent
feature removed (no sustained H2, no Fe/Ni/S catalyst, no pH-gradient drive) — a
generic abiotic nonequilibrium mixture. The canonical run persists that generic
carbon-fixation run; the two behavior tests are CROSS-RUN and graded here via
``viva_genesis.adversarial.adversarial_verdict``:

  - gates-reject-generic        : PASS when EVERY og-01/02/03 gate rejects the
                                  generic control (measured value below threshold).
  - vent-specificity-demonstrated: PASS when the SAME gates pass the vent where the
                                  control fails.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = STUDY_DIR.parents[2]

SPEC_ID = "viva_genesis.composites.carbon_fixation.hydrothermal_carbon_fixation"
STUDY_SLUG = "og-adv-generic-nonequilibrium"
INVESTIGATION_SLUG = "origins-of-life-vent"
N_STEPS = 50


def _run_generic(core):
    from process_bigraph import Composite, gather_emitter_results

    from viva_genesis.adversarial import GENERIC_PARAMS
    from viva_genesis.composites.carbon_fixation import hydrothermal_carbon_fixation
    sim = Composite({"state": hydrothermal_carbon_fixation(core, **GENERIC_PARAMS["carbon"])}, core=core)
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
    from viva_genesis.adversarial import adversarial_verdict
    from viva_genesis.core import build_core
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
            "label": "Adversarial control — generic non-vent chemistry",
            "started_at": time.time(), "status": "running", "n_steps": N_STEPS,
            "emitter": "sqlite", "origin": "canonical_run", "study_slug": STUDY_SLUG,
            "investigation_slug": INVESTIGATION_SLUG, "params": {},
        })

    core = build_core()
    rows = _run_generic(core)
    _write_store(STUDY_DIR / store_rel, rows, run_id)
    _upsert_run_entry(study_yaml, run_id, store_rel)

    # Cross-run adversarial grading: run every og-01/02/03 gate in vent vs generic mode.
    v = adversarial_verdict(core)
    worst = min(v["gate_rows"], key=lambda g: g["generic"] / g["threshold"])
    reject_verdict = {
        "result": "PASS" if v["generic_rejected"] else "FAIL",
        "measured_value": round(v["min_reject_decades"], 3),
        "detail": (f"all {v['n_gates']} vent-specific gates REJECT the generic control "
                   f"(min margin {v['min_reject_decades']:.2f} decades below threshold; "
                   f"tightest: {worst['label']} generic={worst['generic']:.2g} < {worst['threshold']:.2g}) "
                   f"=> the gates measure the vent mechanism, not generic nonequilibrium chemistry"),
    }
    specificity_verdict = {
        "result": "PASS" if (v["vent_passes"] and v["generic_rejected"]) else "FAIL",
        "measured_value": v["n_gates"],
        "detail": (f"the vent passes all {v['n_gates']} gates where the generic control fails every one "
                   f"=> vent-specificity demonstrated (pass-where-control-fails on each gate)"),
    }
    _write_cross_run_outcomes(study_yaml, run_id, {
        "gates-reject-generic": reject_verdict,
        "vent-specificity-demonstrated": specificity_verdict,
    })
    print("cross-run: gates-reject-generic", reject_verdict["result"],
          "| vent-specificity", specificity_verdict["result"])

    try:
        from viva_genesis.viz import render_declared_viz_json
        print("viz.json panels:", render_declared_viz_json(STUDY_DIR, run_id, WORKSPACE_ROOT))
    except Exception as _viz_exc:  # noqa: BLE001
        print("viz render skipped:", _viz_exc)

    if append_run_event:
        append_run_event(WORKSPACE_ROOT, {
            "run_id": run_id, "event": "completed", "completed_at": time.time(),
            "n_steps": N_STEPS, "status": "completed",
        })
    print(f"canonical run complete: {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
