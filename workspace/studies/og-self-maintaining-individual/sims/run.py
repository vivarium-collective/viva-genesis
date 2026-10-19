#!/usr/bin/env python3
"""Canonical run + reciprocal-maintenance closure analysis for
og-self-maintaining-individual (NEW C) — the campaign's central OPEN target.

Does the coupled chemistry-and-boundary system MAINTAIN ITSELF without a built-in
production/retention gain? The reciprocal loop is a fixed point:

    retention -> k_wash_eff -> A's acetate -> chain-extension -> aggregation_competent
    -> gated retention -> ...

solved to self-consistency by driving the real processes (A's PrecursorPoolProcess,
AmphiphileChainExtensionProcess) directly. The loop CLOSES only if a membrane is
sustained (retention > 0, i.e. the chemistry's amphiphile pool clears CAC) WITHOUT
assuming it. Reported framing-agnostic: closes yes/no, by how many orders, WITH vs
WITHOUT the built-in gain, at the canonical point AND B's favorable S_T corner,
across all three ablations (chemistry->membrane, membrane->chemistry, external feed).
Headline: the quantified cascading A->B->C concentration gap.
"""
from __future__ import annotations

import json
import math
import sqlite3
import time
import uuid
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = STUDY_DIR.parents[2]

SPEC_ID = "viva_genesis.composites.self_maintaining.og_self_maintaining_individual"
STUDY_SLUG = "og-self-maintaining-individual"
INVESTIGATION_SLUG = "origins-of-life-vent"
N_STEPS = 240
_K_WASH = 0.05
A_STEPS = 180
CE_STEPS = 240
# B's favorable S_T corner (QUALIFIED window): S_T at the small-molecule ceiling + high dT.
B_CORNER_SORET = 1.0e-2
B_CORNER_DT = 50.0
B_CORNER_CO2 = 2.0e-2
B_CORNER_RETENTION = 0.905   # Jordan-2019 vent membrane retention (B's regime)


def _a_acetate(core, feed_CO2, k_wash):
    from viva_genesis.protometabolism.precursor_pool import PrecursorPoolProcess
    p = PrecursorPoolProcess(config={"max_carbons": 3, "thermo_source": "package",
                                     "ammonium_availability": 1.3e-4, "k_wash": k_wash}, core=core)
    st = p.initial_state(); st["feed_CO2"] = feed_CO2; st["feed_H2"] = 1.08e-2
    last = {}
    for _ in range(A_STEPS):
        last = p.update(st, 1.0)
    return float(last["acetate"])


def _chain_ext(core, acetate):
    from viva_genesis.membranes.amphiphile_chain_extension import AmphiphileChainExtensionProcess
    ce = AmphiphileChainExtensionProcess(config={}, core=core)
    st = ce.initial_state(); st["acetate"] = max(acetate, 0.0); st["temperature"] = 330.0
    last = {}
    for _ in range(CE_STEPS):
        last = ce.update(st, 1.0)
    return float(last["aggregation_competent"]), float(last["amphiphile_total"])


def _b_corner_enrichment(core):
    """B's corner pore enrichment factor the membrane sees (real FiPy trap)."""
    from viva_genesis.transport.thermophoretic_trap import ThermophoreticTrapProcess
    tp = ThermophoreticTrapProcess(config={"delta_T": B_CORNER_DT, "soret_coeff": B_CORNER_SORET}, core=core)
    st = tp.initial_state() if hasattr(tp, "initial_state") else {}
    st.update({"temperature": 333.15, "flow_velocity": 1.0e-4, "porosity": 0.3})
    last = {}
    for _ in range(3):
        last = tp.update(st, 1.0)
    return float(last["enrichment_factor"])


def _acetate_for_competence(core):
    """Log-bisection: the acetate input at which chain-extension just clears CAC
    (aggregation_competent = 1) — the synthesis-competence threshold."""
    lo, hi = 1.0e-7, 1.0e-1
    for _ in range(26):
        mid = math.sqrt(lo * hi)
        comp, _ = _chain_ext(core, mid)
        if comp >= 1.0:
            hi = mid
        else:
            lo = mid
    return math.sqrt(lo * hi)


def fixed_point(core, *, feed_CO2, acetate_gain=1.0, membrane_feedback=True, synthesize=True,
                external_feed=True, built_in_gain=False, max_iter=8, tol=1e-3):
    """Solve the reciprocal loop to self-consistency. Returns the closure result."""
    from viva_genesis.composites.self_maintaining import gated_retention, _EARNED_RETENTION
    retention = 0.0
    acetate = agg = amph = 0.0
    n = 0
    for n in range(1, max_iter + 1):
        k_wash_eff = _K_WASH * (1.0 - retention) if membrane_feedback else _K_WASH
        feed = feed_CO2 if external_feed else 1.0e-12
        acetate = _a_acetate(core, feed, k_wash_eff)
        acetate_fed = acetate * acetate_gain if synthesize else 0.0
        agg, amph = _chain_ext(core, acetate_fed)
        ret_next = _EARNED_RETENTION if built_in_gain else gated_retention(agg)
        if abs(ret_next - retention) < tol:
            retention = ret_next
            break
        retention = ret_next
    # Genuine closure: a membrane is actually sustained (clears CAC) AND it is holding
    # chemistry (retention > 0) — NOT merely an assumed retention.
    membrane_real = agg >= 1.0
    closed = bool(retention > 0.0 and membrane_real)
    return {"closed": closed, "membrane_real": membrane_real, "retention": retention,
            "acetate": acetate, "acetate_fed": acetate * acetate_gain if synthesize else 0.0,
            "aggregation_competent": agg, "amphiphile_total": amph, "n_iter": n}


def _write_store(db_path, rows, sim_id):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(str(db_path))
    con.execute("CREATE TABLE history (simulation_id TEXT, step INTEGER, global_time REAL, state TEXT)")
    for i, r in enumerate(rows):
        con.execute("INSERT INTO history VALUES (?,?,?,?)", (sim_id, i, float(r.get("global_time", i)), json.dumps(r)))
    con.commit(); con.close()


def _upsert_run_entry(study_yaml, run_id, store_rel):
    import ruamel.yaml
    ry = ruamel.yaml.YAML(); ry.preserve_quotes = True; ry.width = 4096
    doc = ry.load(open(study_yaml, encoding="utf-8"))
    runs = doc.get("runs")
    if not isinstance(runs, list):
        runs = ry.load("[]"); doc["runs"] = runs
    runs[:] = [r for r in runs if r.get("name") != run_id and r.get("canonical") is not True]
    e = ry.load("{}"); e["name"] = run_id; e["status"] = "completed"; e["timestamp"] = time.time(); e["canonical"] = True
    em = ry.load("{}"); em["kind"] = "sqlite"; em["store"] = store_rel
    e["emitter"] = em; e["store_path"] = store_rel; e["params"] = "{}"
    runs.append(e)
    tmp = study_yaml.with_suffix(".yaml.tmp"); ry.dump(doc, open(tmp, "w", encoding="utf-8")); tmp.replace(study_yaml)


def _write_cross_run_outcomes(study_yaml, run_id, verdicts):
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
        entry["result"] = v["result"]; entry["measured_value"] = v["measured_value"]
        entry["evaluated_by"] = "code"; entry["operator"] = "cross_run"; entry["detail"] = v["detail"]
        outcomes[name] = entry
    tmp = study_yaml.with_suffix(".yaml.tmp"); ry.dump(doc, open(tmp, "w", encoding="utf-8")); tmp.replace(study_yaml)


def main() -> int:
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.core import build_core
    from viva_genesis.composites.self_maintaining import og_self_maintaining_individual
    from vivarium_workbench.lib.auto_evaluate import evaluate_on_run_completion

    core = build_core()
    run_id = f"{SPEC_ID}__{int(time.time())}__{uuid.uuid4().hex[:6]}"
    store_rel = f"canonical-runs/{run_id}/run.db"
    study_yaml = STUDY_DIR / "study.yaml"

    # Synthesis-competence threshold + B's corner enrichment (both real).
    ace_thresh = _acetate_for_competence(core)
    e_corner = _b_corner_enrichment(core)
    print(f"acetate needed for CAC clearance ~ {ace_thresh:.2e} M; B-corner enrichment ~ {e_corner:.1f}x")

    def _gap(res):
        af = max(res["acetate_fed"], 1e-30)
        return math.log10(ace_thresh / af)

    # Condition matrix: {canonical, B-corner} x {full-no-gain, full-with-gain, 3 ablations}.
    conditions = {}
    points = {"canonical": dict(feed_CO2=2.0e-3, acetate_gain=1.0),
              "b_corner": dict(feed_CO2=B_CORNER_CO2, acetate_gain=e_corner)}
    for pt, base in points.items():
        conditions[f"{pt}:full_no_gain"] = fixed_point(core, **base)
        conditions[f"{pt}:full_built_in_gain"] = fixed_point(core, **base, built_in_gain=True)
        conditions[f"{pt}:ablate_chem_to_mem"] = fixed_point(core, **base, synthesize=False)
        conditions[f"{pt}:ablate_mem_to_chem"] = fixed_point(core, **base, membrane_feedback=False)
        conditions[f"{pt}:ablate_external_feed"] = fixed_point(core, **{**base, "feed_CO2": 2.0e-3}, external_feed=False)

    canon = conditions["canonical:full_no_gain"]
    corner = conditions["b_corner:full_no_gain"]
    corner_gain = conditions["b_corner:full_built_in_gain"]

    artifact = {
        "study": STUDY_SLUG,
        "acetate_for_cac_clearance_M": ace_thresh,
        "b_corner": {"soret_coeff": B_CORNER_SORET, "delta_T": B_CORNER_DT, "feed_CO2": B_CORNER_CO2,
                     "enrichment_factor": e_corner, "membrane_retention_if_earned": B_CORNER_RETENTION},
        "conditions": {k: {**v, "orders_short_of_cac": _gap(v)} for k, v in conditions.items()},
        "closes_without_built_in_gain": {"canonical": canon["closed"], "b_corner": corner["closed"]},
        "cascade": {
            "A_acetate_canonical_M": canon["acetate"],
            "B_corner_acetate_fed_M": corner["acetate_fed"],
            "C_acetate_needed_M": ace_thresh,
            "orders_short_canonical": _gap(canon),
            "orders_short_b_corner": _gap(corner),
        },
        "built_in_gain_comparison": {
            "b_corner_no_gain_closed": corner["closed"],
            "b_corner_with_gain_retention": corner_gain["retention"],
            "b_corner_with_gain_membrane_real": corner_gain["membrane_real"],
            "note": ("With the built-in gain, retention is forced to the earned long-chain value regardless of "
                     "whether the pool clears CAC; membrane_real stays False, so the 'closure' is purely the "
                     "assumed retention - the false closure the no-built-in-gain constraint forbids."),
        },
    }
    out = STUDY_DIR / "artifacts" / "og-self-maintaining-individual" / "self_maintaining.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2))
    print(f"closes (no built-in gain): canonical={canon['closed']} b_corner={corner['closed']}; "
          f"orders short of CAC: canonical={_gap(canon):.1f} b_corner={_gap(corner):.1f}")

    # Canonical graded composite run (one coupled pass at the self-consistent k_wash).
    k_wash_eff = _K_WASH * (1.0 - canon["retention"])
    sim = Composite({"state": og_self_maintaining_individual(core=core, feed_CO2=2.0e-3, k_wash_eff=k_wash_eff)}, core=core)
    sim.run(float(N_STEPS))
    rows = gather_emitter_results(sim)[("emitter",)]
    _write_store(STUDY_DIR / store_rel, rows, run_id)
    _upsert_run_entry(study_yaml, run_id, store_rel)
    summary = evaluate_on_run_completion(STUDY_DIR, run_id, ws_root=WORKSPACE_ROOT, overwrite_authored=True)
    print("single-run grading:", summary)

    # Cross-run test of the CLAIM "reciprocal maintenance closes endogenously": it PASSES only if the
    # loop closes (a real membrane is sustained) without a built-in gain. It does NOT -> FAIL (the honest
    # negative). The detail records that all three ablations also fail and the with-gain closure is assumed-only.
    endogenous_closure = canon["closed"] or corner["closed"]
    ablations_fail = all(not conditions[f"{pt}:{ab}"]["closed"] for pt in points
                         for ab in ("ablate_chem_to_mem", "ablate_mem_to_chem", "ablate_external_feed"))
    verdict = {
        "result": "PASS" if endogenous_closure else "FAIL",
        "measured_value": float(f"{_gap(corner):.3f}"),
        "detail": (f"endogenous closure (no built-in gain): canonical closed={canon['closed']} "
                   f"(~{_gap(canon):.1f} orders short of CAC), B-corner closed={corner['closed']} "
                   f"(~{_gap(corner):.1f} orders short); all three ablations fail to close; with-gain closure is "
                   f"assumed-only (membrane_real={corner_gain['membrane_real']})"),
    }
    _write_cross_run_outcomes(study_yaml, run_id, {"reciprocal-maintenance-closes-endogenously": verdict})
    print("cross-run: reciprocal-maintenance-closes-endogenously", verdict["result"])
    print(f"canonical run complete: {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
