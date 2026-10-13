#!/usr/bin/env python3
"""Canonical run for og-res — nitrogen as a limiting resource (FeS reduced-N).

Runs the FAVOURABLE arm as the canonical run (persists an isolated sqlite store,
auto-grades the four single-run behavior tests via the workspace derived-scalar
evaluator), then runs the two ablation controls (no FeS / no H2) and a nitrogen-
limited arm to grade the two CROSS-RUN tests (``feature-ablation-no-ammonium`` and
``nitrogen-supply-sets-cn``), writing their verdicts into the canonical run's
``outcomes``.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = STUDY_DIR.parents[2]

SPEC_ID = "viva_genesis.composites.nitrogen_assimilation.reduced_nitrogen_reactor"
STUDY_SLUG = "og-res-nitrogen-assimilation"
INVESTIGATION_SLUG = "origins-of-life-vent"
N_STEPS = 120
EPS = 1.0e-6  # avoid the is_empty(Float, 0.0) param gotcha for "zero" controls


def _run(core, **params):
    """Run one condition in memory; return the emitted rows."""
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.composites.nitrogen_assimilation import reduced_nitrogen_reactor
    sim = Composite({"state": reduced_nitrogen_reactor(core, **params)}, core=core)
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
    """Write the cross-run test verdicts into the canonical run's outcomes."""
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
            "label": "Nitrogen as a limiting resource (favourable)", "started_at": time.time(),
            "status": "running", "n_steps": N_STEPS, "emitter": "sqlite",
            "origin": "canonical_run", "study_slug": STUDY_SLUG,
            "investigation_slug": INVESTIGATION_SLUG, "params": {},
        })

    core = build_core()
    # Favourable canonical run -> store + auto-grade the four single-run tests.
    fav = _run(core)
    _write_store(STUDY_DIR / store_rel, fav, run_id)
    _upsert_run_entry(study_yaml, run_id, store_rel)
    summary = evaluate_on_run_completion(STUDY_DIR, run_id, ws_root=WORKSPACE_ROOT,
                                         overwrite_authored=True)
    print("single-run grading:", summary)
    # Render declared visualizations to .pbg/runs/<run_id>/viz.json.
    try:
        from viva_genesis.viz import render_declared_viz_json
        panels = render_declared_viz_json(STUDY_DIR, run_id, WORKSPACE_ROOT)
        print("viz.json panels:", panels)
    except Exception as _viz_exc:  # noqa: BLE001
        print("viz render skipped:", _viz_exc)

    # Cross-run arms / controls.
    def settled_nh4_uM(rows):
        tail = rows[-max(1, len(rows) // 5):]
        return sum(r["NH4"] for r in tail) / len(tail) * 1.0e6

    def settled_cn(rows):
        tail = rows[-max(1, len(rows) // 5):]
        return sum(min(r["cn_supply_ratio"], 1.0e6) for r in tail) / len(tail)

    fav_nh4 = settled_nh4_uM(fav)
    fav_cn = settled_cn(fav)
    controls = {
        "no-FeS": settled_nh4_uM(_run(core, fes_activity=EPS)),
        "no-H2": settled_nh4_uM(_run(core, h2=1.0e-12)),
    }
    limited_cn = settled_cn(_run(core, no3_supply=2.0e-6))

    present = fav_nh4 >= 100.0
    absent = all(v < 1.0 for v in controls.values())
    ablation_verdict = {
        "result": "PASS" if (present and absent) else "FAIL",
        "measured_value": round(fav_nh4, 2),
        "detail": (f"favourable NH4+={fav_nh4:.1f} µM; controls "
                   + ", ".join(f"{k}={v:.3f}" for k, v in controls.items())
                   + " µM (all <1 => FeS + H2 are each necessary for ammonium)"),
    }
    # Reduced N keeps pace at favourable supply; a scarce nitrate feed pushes C:N
    # past the keeps-pace threshold (nitrogen becomes limiting first).
    keeps_pace = fav_cn <= 8.0
    limiting = limited_cn > 8.0
    cn_verdict = {
        "result": "PASS" if (keeps_pace and limiting) else "FAIL",
        "measured_value": round(fav_cn, 2),
        "detail": (f"favourable C:N={fav_cn:.1f} (keeps pace, <=8) vs N-limited feed "
                   f"C:N={limited_cn:.1f} (>8 => nitrogen limiting) => nitrate supply "
                   "sets whether reduced N keeps pace with carbon"),
    }
    _write_cross_run_outcomes(study_yaml, run_id, {
        "feature-ablation-no-ammonium": ablation_verdict,
        "nitrogen-supply-sets-cn": cn_verdict,
    })
    print("cross-run: ablation", ablation_verdict["result"], "| cn-boundary", cn_verdict["result"])

    if append_run_event:
        append_run_event(WORKSPACE_ROOT, {
            "run_id": run_id, "event": "completed", "completed_at": time.time(),
            "n_steps": N_STEPS, "status": "completed",
        })
    print(f"canonical run complete: {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
