#!/usr/bin/env python3
"""Canonical run for og-04-alt — the endogenous boundary.

Runs the FAVORABLE arm (amphiphile synthesised from acetate+formate) as the
canonical run — the endogenous amphiphile clears cac, a viable boundary forms
and individuals appear in the agents map by an _add structural rewrite (persists
an isolated sqlite store, auto-grades the derived ``rewrite_ok`` conservation
test). Then it runs the synthesis-ABLATED control (k_synth -> 0) to grade the
CROSS-RUN ``boundary-forms-from-chemistry`` test — agents form in the favorable
arm, none in the control.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = STUDY_DIR.parents[2]

SPEC_ID = "viva_genesis.composites.endogenous_boundary.endogenous_boundary"
STUDY_SLUG = "og-04-alt-endogenous-boundary"
INVESTIGATION_SLUG = "origins-of-life-vent"
N_STEPS = 40

# Process-bigraph's config merge ignores a falsy 0.0 override, so the
# synthesis-ablated control uses a negligible (~10 orders below favorable)
# k_synth instead of 0.0.
_ABLATION_K_SYNTH = 1.0e-12


def _run(core, **params):
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.composites.endogenous_boundary import endogenous_boundary
    sim = Composite({"state": endogenous_boundary(core, **params)}, core=core)
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

    run_id = f"{SPEC_ID}__{int(time.time())}__{uuid.uuid4().hex[:6]}"
    store_rel = f"canonical-runs/{run_id}/run.db"
    study_yaml = STUDY_DIR / "study.yaml"

    core = build_core()
    fav = _run(core)  # favorable: endogenous synthesis on
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

    fav_agents = fav[-1]["n_agents"]
    ablation = _run(core, k_synth=_ABLATION_K_SYNTH)[-1]
    forms = (fav_agents >= 1 and ablation["n_agents"] == 0)
    verdict = {
        "result": "PASS" if forms else "FAIL",
        "measured_value": int(fav_agents),
        "detail": (f"favorable (endogenous synthesis) -> {int(fav_agents)} individuals "
                   f"(amphiphile {fav[-1]['amphiphile']:.4f} M cleared cac); "
                   f"synthesis-ablated -> {int(ablation['n_agents'])} individuals "
                   f"(amphiphile {ablation['amphiphile']:.2e} M, below cac). The boundary "
                   f"is caused by the endogenous chemistry."),
    }
    _write_cross_run_outcomes(study_yaml, run_id, {"boundary-forms-from-chemistry": verdict})
    print("cross-run: boundary-forms-from-chemistry", verdict["result"])
    print(f"canonical run complete: {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
