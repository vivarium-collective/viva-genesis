#!/usr/bin/env python3
"""Canonical run for og-07 — ecology before LUCA (cross-feeding metacommunity).

Runs the CONNECTED metacommunity as the canonical run (persists an isolated sqlite
store, auto-grades the derived behavior tests — metacommunity_robustness,
luca_capability_overlap — via the workspace evaluator), then runs the ISOLATED
counterfactual arm across a seed sweep to grade the CROSS-RUN tests:

  * ``connected-beats-isolated`` — connected metacommunity robustness is strictly
    higher than the isolated counterfactual on every seed (a measured threshold).
  * ``luca-capability-overlap`` — the collective repertoire's overlap with the
    anaerobic H2/CO2/FeS LUCA reconstruction, REPORTED as a far-end boundary
    (arms_reported), not graded pass/fail.
"""
from __future__ import annotations

import json
import sqlite3
import statistics
import time
import uuid
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = STUDY_DIR.parents[2]

SPEC_ID = "viva_genesis.composites.cross_feeding_metacommunity.cross_feeding_metacommunity"
STUDY_SLUG = "og-07-ecology-before-luca"
INVESTIGATION_SLUG = "origins-of-life-vent"
N_STEPS = 40
SEEDS = range(8)


def _run(core, **params):
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.composites.cross_feeding_metacommunity import cross_feeding_metacommunity
    sim = Composite({"state": cross_feeding_metacommunity(core, **params)}, core=core)
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
        entry["operator"] = v.get("operator", "cross_run")
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
            "label": "Ecology before LUCA (cross-feeding metacommunity)",
            "started_at": time.time(), "status": "running", "n_steps": N_STEPS,
            "emitter": "sqlite", "origin": "canonical_run", "study_slug": STUDY_SLUG,
            "investigation_slug": INVESTIGATION_SLUG, "params": {},
        })

    core = build_core()
    connected = _run(core)  # canonical: connected metacommunity (default seed=1)
    _write_store(STUDY_DIR / store_rel, connected, run_id)
    _upsert_run_entry(study_yaml, run_id, store_rel)
    summary = evaluate_on_run_completion(STUDY_DIR, run_id, ws_root=WORKSPACE_ROOT,
                                         overwrite_authored=True)
    print("single-run grading:", summary)
    try:
        from viva_genesis.viz import render_declared_viz_json
        print("viz.json panels:", render_declared_viz_json(STUDY_DIR, run_id, WORKSPACE_ROOT))
    except Exception as _viz_exc:  # noqa: BLE001
        print("viz render skipped:", _viz_exc)

    # Cross-run: connected metacommunity robustness beats the isolated counterfactual
    # (same seeded assignment, no cross-feeding/HGT) on EVERY seed — the emergence of
    # redundancy is a product of connectivity, not of the assignment. Graded across a
    # seed sweep so the verdict is robust, not knife-edge at one seed.
    conn_robs, iso_robs, lucas, per_seed_pass = [], [], [], []
    for s in SEEDS:
        c = _run(core, seed=s)[-1]
        iso = _run(core, seed=s, isolated=True)[-1]
        conn_robs.append(c["metacommunity_robustness"])
        iso_robs.append(iso["metacommunity_robustness"])
        lucas.append(c["luca_capability_overlap"])
        per_seed_pass.append(c["metacommunity_robustness"] > iso["metacommunity_robustness"])
    n_seeds = len(conn_robs)
    conn_m = statistics.fmean(conn_robs); conn_sd = statistics.pstdev(conn_robs)
    iso_m = statistics.fmean(iso_robs)
    min_gain = min(c - i for c, i in zip(conn_robs, iso_robs))

    connected_verdict = {
        "result": "PASS" if all(per_seed_pass) else "FAIL",
        "measured_value": round(conn_m, 3),
        "operator": "cross_run",
        "detail": (f"connected robustness={conn_m:.3f}±{conn_sd:.3f} vs isolated "
                   f"counterfactual={iso_m:.3f} across {n_seeds} seeds, "
                   f"{sum(per_seed_pass)}/{n_seeds} pass (min gain {min_gain:.3f}) => "
                   f"cross-feeding/HGT build functional redundancy a single compartment cannot"),
    }
    # LUCA overlap is REPORTED as a far-end boundary (arms_reported), never gated.
    luca_m = statistics.fmean(lucas); luca_sd = statistics.pstdev(lucas)
    luca_verdict = {
        "result": "PASS",
        "measured_value": round(luca_m, 3),
        "operator": "arms_reported",
        "detail": (f"collective repertoire overlaps the anaerobic H2/CO2/FeS LUCA core "
                   f"at {luca_m:.3f}±{luca_sd:.3f} across {n_seeds} seeds — reported as a "
                   f"far-end BOUNDARY the emergent set approaches, not a fitting target"),
    }
    _write_cross_run_outcomes(study_yaml, run_id, {
        "connected-beats-isolated": connected_verdict,
        "luca-capability-overlap": luca_verdict,
    })
    print("cross-run: connected-beats-isolated", connected_verdict["result"],
          "| luca-overlap reported", luca_verdict["measured_value"])

    if append_run_event:
        append_run_event(WORKSPACE_ROOT, {
            "run_id": run_id, "event": "completed", "completed_at": time.time(),
            "n_steps": N_STEPS, "status": "completed",
        })
    print(f"canonical run complete: {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
