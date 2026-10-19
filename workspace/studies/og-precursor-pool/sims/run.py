#!/usr/bin/env python3
"""Canonical run for og-precursor-pool (NEW A) — geochemical carbon to a
functional precursor pool, on the REAL C1-C3 reaction-universe engine.

Runs the canonical composite (``precursor_pool``) as the canonical run: persists
an isolated sqlite store and auto-grades the single-run derived behavior tests via
the workspace derived-scalar evaluator. Then runs the three ablation controls
(no-H2 / no-catalyst / no-gradient) and grades the cross-run
``controls-collapse-functional-pool`` test. Finally writes the committed
precursor-yield-vector artifact (per-species concentration + carbon-source
attribution + electron budget) and a DIC-window sweep for the viz.

Run from the workspace with the worktree on PYTHONPATH (see the build's bootstrap
sitecustomize) and the canonical venv:
    python workspace/studies/og-precursor-pool/sims/run.py
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = STUDY_DIR.parents[2]

SPEC_ID = "viva_genesis.composites.precursor_pool.precursor_pool"
STUDY_SLUG = "og-precursor-pool"
INVESTIGATION_SLUG = "origins-of-life-vent"
N_STEPS = 240
# Downstream consumption threshold (M): the functional C2+ pool concentration a
# reaction-network / amphiphile study would need to consume. first-principles.
CONSUMABLE_M = 1.0e-6


def _run(core, fn, **params):
    """Run one composite in memory; return the per-tick emitted rows."""
    from process_bigraph import Composite, gather_emitter_results
    sim = Composite({"state": fn(core=core, **params)}, core=core)
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


def _write_yield_vector_artifact(core) -> dict:
    """Drive the engine directly to steady state to capture the full per-species
    yield vectors + carbon-source attribution + electron budget (committed), plus
    a DIC-window (2-20 mM) sweep used by the viz."""
    from viva_genesis.protometabolism.precursor_pool import PrecursorPoolProcess
    from viva_genesis.composites.precursor_pool import _CO2, _H2, _NH4

    def steady(feed_co2):
        p = PrecursorPoolProcess(config={"max_carbons": 3, "thermo_source": "package",
                                          "ammonium_availability": _NH4}, core=core)
        st = p.initial_state(); st["feed_CO2"] = feed_co2; st["feed_H2"] = _H2
        last = {}
        for _ in range(N_STEPS):
            last = p.update(st, 1.0)
        rep = p.precursor_report({"feed_CO2": feed_co2, "feed_H2": _H2})
        return last, rep

    last, rep = steady(_CO2)
    sweep = []
    for co2 in (2.0e-3, 5.0e-3, 1.0e-2, 2.0e-2):
        l, r = steady(co2)
        c2 = sum(v["concentration_M"] for v in r["yield_vectors"].values()
                 if v["n_carbons"] == 2)
        c1 = sum(v["concentration_M"] for v in r["yield_vectors"].values()
                 if v["n_carbons"] == 1)
        sweep.append({"feed_CO2_mM": co2 * 1e3,
                      "functional_pool_carbon_M": l["functional_pool_carbon"],
                      "c1_M": c1, "c2_M": c2,
                      "c2_c1_ratio": (c2 / c1 if c1 > 0 else 0.0)})

    artifact = {
        "study": STUDY_SLUG,
        "feed": {"feed_CO2_M": _CO2, "feed_H2_M": _H2, "ammonium_M": _NH4,
                 "provenance": "og-vent-interface DIC window + og-carbon-fixation H2 + og-nutrient ammonium"},
        "n_steps": N_STEPS,
        "functional_pool_carbon_M": last["functional_pool_carbon"],
        "pool_cofixed_fraction": last["pool_cofixed_fraction"],
        "cn_ratio": last["cn_ratio"],
        "element_residual": last["element_residual"],
        "carbon_residual": last["carbon_residual"],
        "electron_budget": rep["electron_budget"],
        "yield_vectors": rep["yield_vectors"],
        "functional_species": rep["functional_species"],
        "dic_window_sweep": sweep,
        "consumable_threshold_M": CONSUMABLE_M,
    }
    out = STUDY_DIR / "artifacts" / "og-precursor-pool" / "precursor_yield_vectors.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2))
    return artifact


def main() -> int:
    from viva_genesis.core import build_core
    from vivarium_workbench.lib.auto_evaluate import evaluate_on_run_completion
    try:
        from vivarium_workbench.lib.run_log import append_run_event
    except Exception:
        append_run_event = None
    from viva_genesis.composites.precursor_pool import (
        precursor_pool, precursor_pool_no_h2, precursor_pool_no_catalyst,
        precursor_pool_no_gradient,
    )

    run_id = f"{SPEC_ID}__{int(time.time())}__{uuid.uuid4().hex[:6]}"
    store_rel = f"canonical-runs/{run_id}/run.db"
    study_yaml = STUDY_DIR / "study.yaml"

    if append_run_event:
        append_run_event(WORKSPACE_ROOT, {
            "run_id": run_id, "event": "started", "spec_id": SPEC_ID,
            "label": "Functional precursor pool (canonical)", "started_at": time.time(),
            "status": "running", "n_steps": N_STEPS, "emitter": "sqlite",
            "origin": "canonical_run", "study_slug": STUDY_SLUG,
            "investigation_slug": INVESTIGATION_SLUG, "params": {},
        })

    core = build_core()

    # Canonical run -> store + auto-grade the single-run derived tests.
    can = _run(core, precursor_pool)
    _write_store(STUDY_DIR / store_rel, can, run_id)
    _upsert_run_entry(study_yaml, run_id, store_rel)
    summary = evaluate_on_run_completion(STUDY_DIR, run_id, ws_root=WORKSPACE_ROOT,
                                         overwrite_authored=True)
    print("single-run grading:", summary)

    # Cross-run controls: the functional pool must collapse in each ablation.
    def last_func(rows):
        return rows[-1]["functional_pool_carbon"]

    can_func = last_func(can)
    controls = {
        "no-H2": last_func(_run(core, precursor_pool_no_h2)),
        "no-catalyst": last_func(_run(core, precursor_pool_no_catalyst)),
        "no-gradient": last_func(_run(core, precursor_pool_no_gradient)),
    }
    present = can_func >= 1.0e-11
    absent = all(v < 0.01 * can_func for v in controls.values())
    collapse_verdict = {
        "result": "PASS" if (present and absent) else "FAIL",
        "measured_value": float(f"{can_func:.3e}"),
        "detail": (f"canonical functional pool={can_func:.2e} M C; controls "
                   + ", ".join(f"{k}={v:.2e}" for k, v in controls.items())
                   + " M C (all <1% => the vent feed + catalyst + gradient drive the pool)"),
    }
    _write_cross_run_outcomes(study_yaml, run_id, {
        "controls-collapse-functional-pool": collapse_verdict,
    })
    print("cross-run: controls-collapse", collapse_verdict["result"])

    # Committed yield-vector artifact + DIC sweep.
    art = _write_yield_vector_artifact(core)
    print(f"yield vectors: functional_pool={art['functional_pool_carbon_M']:.3e} M C, "
          f"cofixed={art['pool_cofixed_fraction']:.3f}, "
          f"electron_residual={art['electron_budget']['electron_budget_residual']:.1e}")

    if append_run_event:
        append_run_event(WORKSPACE_ROOT, {
            "run_id": run_id, "event": "completed", "completed_at": time.time(),
            "n_steps": N_STEPS, "status": "completed",
        })
    print(f"canonical run complete: {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
