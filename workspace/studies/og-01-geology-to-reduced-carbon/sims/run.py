#!/usr/bin/env python3
"""Canonical run for og-01 — geology to reduced carbon (real eQuilibrator + FiPy).

Runs the FAVORABLE arm as the canonical run (persists an isolated sqlite store,
auto-grades the six single-run behavior tests via the workspace derived-scalar
evaluator), then runs the three controls (no gradient / no H2 / no catalyst) and
the Tutolo-2026 arm to grade the two CROSS-RUN tests
(``ph-gradient-drives-formate`` and ``in-situ-ph-correction``), writing their
verdicts into the canonical run's ``outcomes``.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = STUDY_DIR.parents[2]

SPEC_ID = "viva_genesis.composites.campaign1.og_01_geology_to_reduced_carbon"
STUDY_SLUG = "og-01-geology-to-reduced-carbon"
INVESTIGATION_SLUG = "origins-of-life-vent"
N_STEPS = 120
EPS = 1.0e-6  # avoid the is_empty(Float, 0.0) param gotcha for "zero" controls


def _run(core, **params):
    """Run one condition in memory; return the last emitted row + peaks."""
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.composites.campaign1 import og_01_geology_to_reduced_carbon
    sim = Composite({"state": og_01_geology_to_reduced_carbon(core, **params)}, core=core)
    sim.run(float(N_STEPS))
    rows = gather_emitter_results(sim)[("emitter",)]
    return rows


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
    """Write the two cross-run test verdicts into the canonical run's outcomes."""
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
    from process_bigraph import gather_emitter_results  # noqa: F401
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
            "label": "Geology to reduced carbon (favorable)", "started_at": time.time(),
            "status": "running", "n_steps": N_STEPS, "emitter": "sqlite",
            "origin": "canonical_run", "study_slug": STUDY_SLUG,
            "investigation_slug": INVESTIGATION_SLUG, "params": {},
        })

    core = build_core()
    # Favorable canonical run -> store + auto-grade the six single-run tests.
    fav = _run(core, gradient_efficiency=1.0)
    _write_store(STUDY_DIR / store_rel, fav, run_id)
    _upsert_run_entry(study_yaml, run_id, store_rel)
    summary = evaluate_on_run_completion(STUDY_DIR, run_id, ws_root=WORKSPACE_ROOT,
                                         overwrite_authored=True)
    print("single-run grading:", summary)
    # Render declared visualizations to .pbg/runs/<run_id>/viz.json so the
    # workbench native viz gallery shows this run's figures.
    try:
        from viva_genesis.viz import render_declared_viz_json
        panels = render_declared_viz_json(STUDY_DIR, run_id, WORKSPACE_ROOT)
        print("viz.json panels:", panels)
    except Exception as _viz_exc:  # noqa: BLE001
        print("viz render skipped:", _viz_exc)


    # Cross-run arms/controls.
    def last_formate_mM(rows):
        return rows[-1]["formate"] * 1000.0

    def peak_pmf_mV(rows):
        return max(r["pmf"] for r in rows) * 1000.0

    fav_formate = last_formate_mM(fav)
    fav_pmf = peak_pmf_mV(fav)
    controls = {
        "no-gradient": last_formate_mM(_run(core, gradient_efficiency=EPS)),
        "no-H2": last_formate_mM(_run(core, h2=1.0e-12)),
        "no-catalyst": last_formate_mM(_run(core, catalyst_active=EPS)),
    }
    tutolo_rows = _run(core, gradient_efficiency=0.1)
    tutolo_pmf = peak_pmf_mV(tutolo_rows)

    present = fav_formate >= 10.0
    absent = all(v < 1.0 for v in controls.values())
    gradient_verdict = {
        "result": "PASS" if (present and absent) else "FAIL",
        "measured_value": round(fav_formate, 3),
        "detail": (f"favorable formate={fav_formate:.1f} mM; controls "
                   + ", ".join(f"{k}={v:.3f}" for k, v in controls.items())
                   + " mM (all <1 => gradient drives formate)"),
    }
    collapse = tutolo_pmf < 0.3 * fav_pmf
    insitu_verdict = {
        "result": "PASS" if collapse else "FAIL",
        "measured_value": round(tutolo_pmf, 1),
        "detail": (f"favorable pmf={fav_pmf:.0f} mV vs Tutolo-2026 pmf={tutolo_pmf:.0f} mV "
                   f"=> usable gradient {'COLLAPSES' if collapse else 'persists'} at in-situ T/P"),
    }
    _write_cross_run_outcomes(study_yaml, run_id, {
        "ph-gradient-drives-formate": gradient_verdict,
        "in-situ-ph-correction": insitu_verdict,
    })
    print("cross-run: gradient", gradient_verdict["result"], "| in-situ", insitu_verdict["result"])

    if append_run_event:
        append_run_event(WORKSPACE_ROOT, {
            "run_id": run_id, "event": "completed", "completed_at": time.time(),
            "n_steps": N_STEPS, "status": "completed",
        })
    print(f"canonical run complete: {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
