#!/usr/bin/env python3
"""Canonical run for og-04-alt — the endogenous boundary.

Runs the FAVORABLE arm (amphiphile synthesised from acetate+formate) as the
canonical run — the endogenous amphiphile clears cac, a viable boundary forms
and individuals appear in the agents map by an _add structural rewrite — and the
synthesis-ABLATED control (k_synth -> 0). Writes a committed JSON report
(``artifacts/endogenous_boundary_report.json``) holding both arms' series + a
headline block, persists an isolated sqlite store, and auto-grades the two
derived gates — ``boundary_forms_from_chemistry`` (favorable forms, control does
not) and ``endogenous_rewrite_conservation_ok`` — which read the committed
artifact (not the gitignored run.db), so every number verifies from the tree.
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
ARTIFACT_REL = "artifacts/endogenous_boundary_report.json"

# Process-bigraph's config merge ignores a falsy 0.0 override, so the
# synthesis-ablated control uses a negligible (~10 orders below favorable)
# k_synth instead of 0.0.
_ABLATION_K_SYNTH = 1.0e-12
_FAVORABLE_PARAMS = {"model_boundary": "mixed", "k_synth": 5.0e-2,
                     "acetate0": 5.0e-2, "formate0": 5.0e-2, "pH": 9.0,
                     "ionic_strength": 0.35}


def _run(core, **params):
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.composites.endogenous_boundary import endogenous_boundary
    sim = Composite({"state": endogenous_boundary(core, **params)}, core=core)
    sim.run(float(N_STEPS))
    return gather_emitter_results(sim)[("emitter",)]


def _series(rows, key):
    return [float(r.get(key, 0.0)) for r in rows]


def _write_artifact(fav, abl) -> None:
    art = STUDY_DIR / ARTIFACT_REL
    art.parent.mkdir(parents=True, exist_ok=True)
    fav_rewrite = _series(fav, "rewrite_ok")
    report = {
        "study": STUDY_SLUG,
        "spec_id": SPEC_ID,
        "n_steps": N_STEPS,
        "favorable": {
            "params": _FAVORABLE_PARAMS,
            "series": {k: _series(fav, k) for k in ("n_agents", "amphiphile", "rewrite_ok")},
            "final": {"n_agents": fav[-1]["n_agents"], "amphiphile": fav[-1]["amphiphile"],
                      "rewrite_ok": fav[-1]["rewrite_ok"]},
        },
        "ablated": {
            "params": {**_FAVORABLE_PARAMS, "k_synth": _ABLATION_K_SYNTH},
            "final": {"n_agents": abl[-1]["n_agents"], "amphiphile": abl[-1]["amphiphile"]},
        },
        "headline": {
            "n_agents_favorable": float(fav[-1]["n_agents"]),
            "n_agents_ablated": float(abl[-1]["n_agents"]),
            "amphiphile_favorable": float(fav[-1]["amphiphile"]),
            "amphiphile_ablated": float(abl[-1]["amphiphile"]),
            # caused by the chemistry: forms favorable, not when synthesis ablated
            "boundary_forms_from_chemistry": bool(fav[-1]["n_agents"] >= 1
                                                  and abl[-1]["n_agents"] == 0),
            # 1.0 iff EVERY step's rewrite conserved matter (min over the run)
            "rewrite_conservation_ok": float(min(fav_rewrite)) if fav_rewrite else 0.0,
        },
    }
    art.write_text(json.dumps(report, indent=1))
    return report["headline"]


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


def main() -> int:
    from viva_genesis.core import build_core
    from vivarium_workbench.lib.auto_evaluate import evaluate_on_run_completion

    run_id = f"{SPEC_ID}__{int(time.time())}__{uuid.uuid4().hex[:6]}"
    store_rel = f"canonical-runs/{run_id}/run.db"
    study_yaml = STUDY_DIR / "study.yaml"

    core = build_core()
    fav = _run(core, **_FAVORABLE_PARAMS)         # favorable: endogenous synthesis on
    abl = _run(core, **{**_FAVORABLE_PARAMS, "k_synth": _ABLATION_K_SYNTH})  # ablated
    headline = _write_artifact(fav, abl)
    print("artifact headline:", json.dumps(headline))

    _write_store(STUDY_DIR / store_rel, fav, run_id)
    _upsert_run_entry(study_yaml, run_id, store_rel)
    summary = evaluate_on_run_completion(STUDY_DIR, run_id, ws_root=WORKSPACE_ROOT,
                                         overwrite_authored=True)
    print("gate grading:", summary)
    try:
        from viva_genesis.viz import render_declared_viz_json
        print("viz.json panels:", render_declared_viz_json(STUDY_DIR, run_id, WORKSPACE_ROOT))
    except Exception as _viz_exc:  # noqa: BLE001
        print("viz render skipped:", _viz_exc)
    print(f"canonical run complete: {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
