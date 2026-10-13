#!/usr/bin/env python3
"""Canonical run for og-growth-division — metabolism → osmotic growth & division.

Runs the FAVORABLE (matched) compartment as the canonical run — the internal
autocatalytic osmolyte source drives osmotic growth to repeated DIVISION (persists an
isolated sqlite store, auto-grades the derived behavior tests ``growth_division_count``
and ``osmotic_balance_residual_max`` via the workspace evaluator). Then it runs the
two regime controls (too-permeable → starvation, too-impermeable → lysis) to grade the
CROSS-RUN ``division-not-lysis-or-starvation`` test (the viable band is bounded), and
the zero-throughput ablation to grade ``ablation-no-throughput-no-growth`` (no source →
no growth).
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = STUDY_DIR.parents[2]

SPEC_ID = "viva_genesis.composites.osmotic_growth_division.osmotic_growth_division"
STUDY_SLUG = "og-growth-division"
INVESTIGATION_SLUG = "origins-of-life-vent"
N_STEPS = 100

# Process-bigraph's config merge ignores a falsy 0.0 override, so the zero-throughput
# ablation uses a negligible (~12 orders below favorable) throughput instead of 0.0.
_ABLATION_THROUGHPUT = 1.0e-30


def _run(core, **params):
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.composites.osmotic_growth_division import osmotic_growth_division
    sim = Composite({"state": osmotic_growth_division(core, **params)}, core=core)
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
            "label": "Metabolism to osmotic growth and division (favorable)",
            "started_at": time.time(), "status": "running", "n_steps": N_STEPS,
            "emitter": "sqlite", "origin": "canonical_run", "study_slug": STUDY_SLUG,
            "investigation_slug": INVESTIGATION_SLUG, "params": {},
        })

    core = build_core()
    # Canonical run: the FAVORABLE (matched) compartment — chemistry drives growth → division.
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

    # Cross-run arms. The viable band is bounded: too permeable starves (product leaks,
    # no osmotic build-up), too impermeable lyses (pressure bursts the membrane); and
    # with no autocatalytic source there is no growth at all.
    fav_div = fav[-1]["division_count"]
    starve = _run(core, membrane_permeability=1.0e-5)[-1]       # too permeable
    lyse = _run(core, network_throughput=1.0e-18, membrane_permeability=1.0e-10)[-1]  # too impermeable
    ablation = _run(core, network_throughput=_ABLATION_THROUGHPUT)[-1]

    bounded = (fav_div >= 1 and starve["division_count"] == 0 and starve["lysed"] == 0
               and lyse["lysed"] == 1)
    band_verdict = {
        "result": "PASS" if bounded else "FAIL",
        "measured_value": int(fav_div),
        "detail": (f"matched → {fav_div} divisions (grow→divide); too-permeable → "
                   f"{starve['division_count']} divisions, net growth {starve['net_growth']:.2f} "
                   f"(starvation, no osmotic build-up); too-impermeable → lysed="
                   f"{lyse['lysed']} at peak pressure {lyse['osmotic_pressure']:.0f} Pa "
                   f"(lysis) — the viable growth→division band is bounded between starvation and lysis"),
    }
    ablation_verdict = {
        "result": "PASS" if (fav_div >= 1 and ablation["division_count"] == 0
                             and ablation["net_growth"] < 1.1) else "FAIL",
        "measured_value": int(ablation["division_count"]),
        "detail": (f"favorable → {fav_div} divisions; zero-throughput ablation → "
                   f"{ablation['division_count']} divisions, net growth "
                   f"{ablation['net_growth']:.3f} (no autocatalytic source ⇒ no osmotic growth)"),
    }
    _write_cross_run_outcomes(study_yaml, run_id, {
        "division-not-lysis-or-starvation": band_verdict,
        "ablation-no-throughput-no-growth": ablation_verdict,
    })
    print("cross-run: bounded-band", band_verdict["result"],
          "| ablation", ablation_verdict["result"])

    if append_run_event:
        append_run_event(WORKSPACE_ROOT, {
            "run_id": run_id, "event": "completed", "completed_at": time.time(),
            "n_steps": N_STEPS, "status": "completed",
        })
    print(f"canonical run complete: {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
