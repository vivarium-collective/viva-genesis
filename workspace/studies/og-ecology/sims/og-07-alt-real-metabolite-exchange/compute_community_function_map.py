#!/usr/bin/env python
"""Compute + persist the Phase-8 community-function artifact (og-07-alt-real-metabolite-exchange).

Runs the real ``metabolite_exchange_community`` composite (a libRoadRunner
copy of the Phase-3 universe inside every agent, masked to its lineage's
rule repertoire; the exchange rules of the bigraphical reactive system on the
Phase-4-shaped pore field; the cross-system C/N/P ledger) and writes
``artifacts/community_function_map.json``:

* **arms** at the canonical point — ``community`` (fixer:4 + reducer:4,
  interleaved), ``mono_fixer`` / ``mono_reducer`` (8 agents of one
  repertoire), ``private`` (the same community, each agent exchanging only
  with its own copy of the background: the isolated counterfactual),
  ``generalist`` (8 complete cells), ``segregated`` (the community with the
  lineages in separate blocks of the pore) and the ``null_*`` arms (the
  Phase-3 matched null inside every agent, community + monocultures).
* **gate** ``community-function-precedes-cell-completeness`` — the product
  classes held in the community (settled, above the floor) that NO lineage
  holds or produces in monoculture, whether they vanish in the private arm,
  the exchanged intermediate and its cross-lineage flux, the generalist's
  level of the same functions, the maximum cell completeness in the
  community (< 1: no cell is complete) and the null arms' count.
* **decision_map** — the same four arms over (acid permeability x pore
  residence): where the community-only function emerges.
* **og07** — og-07's gate readouts per arm from the EcologyReducerStep.
* **ledger** — worst-case C / N / P residual over every run, firings.

    PYTHONPATH=<worktree> python workspace/studies/og-07-alt-real-metabolite-exchange/sims/compute_community_function_map.py [--steps 250] [--workers 6] [--quick]
"""
from __future__ import annotations

import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"

NOMINAL = {"p_diacid": 1.0e-8, "p_monoacid": 1.0e-7, "k_wash": 0.01}
P_DIACID_AXIS = (1.0e-10, 3.0e-10, 1.0e-9, 3.0e-9, 1.0e-8, 3.0e-8, 1.0e-7)
K_WASH_AXIS = (0.05, 0.01, 0.002)
FLOOR = 1.0e-9
COMMUNITY = "fixer:4,reducer:4"
ARMS = {
    "community": {"lineages": COMMUNITY},
    "mono_fixer": {"lineages": "fixer:8"},
    "mono_reducer": {"lineages": "reducer:8"},
    "private": {"lineages": COMMUNITY, "coupling": "private"},
}
EXTRA_ARMS = {
    "generalist": {"lineages": "generalist:8"},
    "segregated": {"lineages": COMMUNITY, "placement": "segregated"},
    "null_community": {"lineages": COMMUNITY, "model_proto_ecology": "null_network", "null_seed": 0},
    "null_mono_fixer": {"lineages": "fixer:8", "model_proto_ecology": "null_network", "null_seed": 0},
    "null_mono_reducer": {"lineages": "reducer:8", "model_proto_ecology": "null_network", "null_seed": 0},
    "null_community_s1": {"lineages": COMMUNITY, "model_proto_ecology": "null_network", "null_seed": 1},
    "null_mono_fixer_s1": {"lineages": "fixer:8", "model_proto_ecology": "null_network", "null_seed": 1},
    "null_mono_reducer_s1": {"lineages": "reducer:8", "model_proto_ecology": "null_network", "null_seed": 1},
    "null_private": {"lineages": COMMUNITY, "coupling": "private", "model_proto_ecology": "null_network", "null_seed": 0},
    "null_private_s1": {"lineages": COMMUNITY, "coupling": "private", "model_proto_ecology": "null_network", "null_seed": 1},
}


def _arg(flag: str, default):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return type(default)(sys.argv[i + 1])
    return default


def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, float) and not math.isfinite(o):
        return None
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    return str(o)


def run_point(spec: dict) -> dict:
    """Build -> run -> reduce one composite (module-level so the pool can pickle it)."""
    import roadrunner
    roadrunner.Logger.setLevel(roadrunner.Logger.LOG_ERROR)
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.core import build_core
    from viva_genesis.composites.metabolite_exchange_community import (metabolite_exchange_community, PHASE8_REDUCERS,
                                                                       settled_functions)
    from viva_genesis.protometabolism import universe as U
    spec = dict(spec)
    n_steps = int(spec.pop("n_steps"))
    core = build_core()
    sim = Composite({"state": metabolite_exchange_community(core, **spec)}, core=core)
    sim.run(float(n_steps))
    rows = gather_emitter_results(sim)[("emitter",)]
    last = rows[-1]
    n_q = max(1, len(rows) // 4)
    out = {k: float(fn(rows)) for k, fn in PHASE8_REDUCERS.items()}
    # settled function levels (max over agents) + who held / produced them at the end
    out["functions"] = settled_functions(rows)
    out["functions_final"] = {f: {"max_conc": float(d["max_conc"]), "held_by": list(d["held_by"]), "produced_by": list(d["produced_by"])}
                              for f, d in (last.get("functions_union") or {}).items()}
    by_l = last.get("functions_by_lineage") or {}
    out["held_by_lineage"] = {l: sorted(f for f, v in (d.get("held") or {}).items() if v) for l, d in by_l.items()}
    out["produced_by_lineage"] = {l: sorted(f for f, v in (d.get("produced") or {}).items() if v) for l, d in by_l.items()}
    # produced anywhere during the last quartile (a function made at least once)
    prod_any = set()
    for r in rows[-n_q:]:
        for l, d in (r.get("functions_by_lineage") or {}).items():
            prod_any.update(f for f, v in (d.get("produced") or {}).items() if v)
    out["produced_any_settled"] = sorted(prod_any)
    # cross-lineage flux per species, settled (mean over last quartile) in mol/tick
    cross = {}
    for r in rows[-n_q:]:
        for s, v in (r.get("cross_lineage_flux") or {}).items():
            cross[s] = cross.get(s, 0.0) + float(v) / n_q
    named = {}
    for s, v in cross.items():
        if v > 0:
            skel = U.skeleton_of(s)
            named[s] = {"name": U.common_name(skel) if skel else s, "moles_per_tick": v}
    out["cross_lineage_flux"] = named
    out["firings"] = {k: float(v) for k, v in (last.get("firings") or {}).items()}
    out["firing_moles"] = {k: float(v) for k, v in (last.get("firing_moles") or {}).items()}
    out["C_residual_max"] = float(last["C_residual_max"]); out["N_residual_max"] = float(last["N_residual_max"])
    out["P_residual_max"] = float(last["P_residual_max"])
    out["C_total"] = float(last["C_total"]); out["N_total"] = float(last["N_total"]); out["P_total"] = float(last["P_total"])
    out["capability_diversity"] = float(np.mean([float(r["capability_diversity"]) for r in rows[-n_q:]]))
    # time series of the key readouts for the figures
    out["series"] = {"t": [float(r["global_time"]) for r in rows],
                     "n_functions_union": [float(r["n_functions_union"]) for r in rows],
                     "robustness_gain": [float(r["robustness_gain"]) for r in rows],
                     "cross_lineage_flux_total": [float(r["cross_lineage_flux_total"]) for r in rows]}
    # per-agent settled pools for the World view (the C4 branch + feeds)
    key_species = ["X_ACKA", "X_ACOA", "X_ACCA", "X_AKM", "X_A", "X_AM", "X_AOM", "X_ACM", "X_DM", U.CO2, U.H2]
    out["field_final"] = {ck: {s: float(cell.get(s, 0.0)) for s in key_species} for ck, cell in (last.get("field") or {}).items()}
    out["rates_final"] = {aid: {k: float(v) for k, v in d.items()} for aid, d in (last.get("rates") or {}).items()}
    return {"spec": spec, "n_steps": n_steps, **out}


def _held(point: dict, floor: float) -> set:
    return {f for f, c in point["functions"].items() if c >= floor}


def _settled_level(point: dict, f: str) -> float:
    return float(point["functions"].get(f, 0.0))


_PRECURSOR_CACHE: dict = {}


def precursor_species(function: str, lineage: str) -> dict[str, str]:
    """Species from which ``lineage``'s own repertoire can make a species of class
    ``function`` (reactants of its reactions producing it, either direction),
    from the universe's stoichiometry: ``{species_id: common name}``."""
    key = (function, lineage)
    if key not in _PRECURSOR_CACHE:
        from viva_genesis.ecology.proto_ecology import REPERTOIRES, function_of
        from viva_genesis.protometabolism import universe as U
        if "universe" not in _PRECURSOR_CACHE:
            _PRECURSOR_CACHE["universe"] = U.build_universe(4)
        u = _PRECURSOR_CACHE["universe"]
        rules = REPERTOIRES.get(lineage, frozenset())
        out = {}
        for r in u.reactions:
            if r.rule not in rules:
                continue
            for side, other in ((r.products, r.reactants), (r.reactants, r.products)):
                if any(function_of(sp) == function for sp in side):
                    for sp in other:
                        if sp not in (U.H2O, U.H2) and function_of(sp) != function:
                            skel = U.skeleton_of(sp)
                            out[sp] = U.common_name(skel) if skel else sp
        _PRECURSOR_CACHE[key] = out
    return _PRECURSOR_CACHE[key]


def evaluate_gate(arms: dict, floor: float, *, precursors: bool = True) -> dict:
    """The pre-registered rule for community-function-precedes-cell-completeness."""
    comm, fx, rd, priv = arms["community"], arms["mono_fixer"], arms["mono_reducer"], arms["private"]
    held_c = _held(comm, floor)
    mono_held = _held(fx, floor) | _held(rd, floor)
    mono_prod = set(fx["produced_any_settled"]) | set(rd["produced_any_settled"])
    community_only = sorted(held_c - mono_held - mono_prod)
    vanish = sorted(f for f in community_only if _settled_level(priv, f) < floor)
    cross = comm["cross_lineage_flux"]
    top = sorted(cross.items(), key=lambda kv: -kv[1]["moles_per_tick"])[:5]
    gen = arms.get("generalist")
    levels = {f: {"community": _settled_level(comm, f), "mono_fixer": _settled_level(fx, f),
                  "mono_reducer": _settled_level(rd, f), "private": _settled_level(priv, f),
                  "generalist": (_settled_level(gen, f) if gen else None),
                  "produced_by_in_community": comm["functions_final"].get(f, {}).get("produced_by", []),
                  "held_by_in_community": comm["functions_final"].get(f, {}).get("held_by", [])}
              for f in community_only}
    # the precursor witness: a species the producing lineage cannot make in
    # monoculture (its class is produced by neither monoculture... of that
    # lineage) but from which its own rules make the function, crossing between
    # lineages with a non-zero flux
    prec: dict[str, list] = {}
    if precursors:
        for f in community_only:
            found = []
            for lin in levels[f]["produced_by_in_community"]:
                mono = arms.get(f"mono_{lin}")
                mono_made = set(mono["produced_any_settled"]) if mono else set()
                for sp, name in precursor_species(f, lin).items():
                    from viva_genesis.ecology.proto_ecology import function_of
                    cls = function_of(sp)
                    if cls in mono_made:
                        continue
                    flux = float(cross.get(sp, {}).get("moles_per_tick", 0.0))
                    if flux > 0.0:
                        found.append({"species": sp, "name": name, "moles_per_tick": flux, "made_by": lin,
                                      "molecules_per_tick": flux * 6.02214076e23})
            prec[f] = sorted(found, key=lambda d: -d["moles_per_tick"])
    sustained = (bool(community_only) and len(vanish) == len(community_only)
                 and (not precursors or all(prec.get(f) for f in community_only)))
    ratio = None
    if gen and community_only:
        rs = [levels[f]["community"] / levels[f]["generalist"] for f in community_only if levels[f]["generalist"]]
        ratio = float(np.mean(rs)) if rs else None
    return {
        "community_only_functions": community_only,
        "n_community_only": len(community_only),
        "vanish_without_exchange": vanish,
        "n_vanish_without_exchange": len(vanish),
        "flux_sustained": sustained,
        "precursors": prec,
        "exchanged_intermediates": [{"species": s, **d} for s, d in top],
        "cross_lineage_flux_total": comm["cross_lineage_flux_total"],
        "levels": levels,
        "community_over_generalist": ratio,
        "max_cell_completeness": comm["max_cell_completeness"],
        "mean_cell_completeness": comm["mean_cell_completeness"],
        "n_functions_union": comm["n_functions_union"],
        "mono_union": sorted(mono_held | mono_prod),
        # molecules per agent of the best species of each community-only class (1 fL agents)
        "molecules_per_agent": {f: levels[f]["community"] * 1.0e-18 * 6.02214076e23 for f in community_only},
    }

def main() -> int:
    from viva_genesis.provenance import load_package

    steps = _arg("--steps", 250)
    workers = _arg("--workers", 6)
    quick = "--quick" in sys.argv
    t0 = time.time()
    p_axis = (1.0e-9, 1.0e-8, 1.0e-7) if quick else P_DIACID_AXIS
    k_axis = (0.05, 0.01) if quick else K_WASH_AXIS

    specs: list[tuple[str, dict]] = []
    for arm, cfg in {**ARMS, **EXTRA_ARMS}.items():
        specs.append((f"nominal/{arm}", {**NOMINAL, **cfg, "n_steps": steps}))
    for pd in p_axis:
        for kw in k_axis:
            for arm, cfg in ARMS.items():
                specs.append((f"map/{pd:.0e}/{kw}/{arm}",
                              {"p_diacid": pd, "p_monoacid": 10.0 * pd, "k_wash": kw, **cfg, "n_steps": steps}))
    print(f"{len(specs)} composite runs on {workers} workers ...", flush=True)
    results: dict[str, dict] = {}
    if int(workers) <= 1:
        for key, spec in specs:
            results[key] = run_point(dict(spec))
            print(f"  {key} ({time.time() - t0:.0f} s)", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=int(workers)) as pool:
            for key, res in zip([k for k, _ in specs], pool.map(run_point, [dict(s) for _, s in specs])):
                results[key] = res
    print(f"runs done in {time.time() - t0:.0f} s", flush=True)

    nominal = {arm: results[f"nominal/{arm}"] for arm in {**ARMS, **EXTRA_ARMS}}
    gate = evaluate_gate(nominal, FLOOR)
    # the null arms: does rewired chemistry also produce a community-only function?
    null_eval = {}
    for suffix in ("", "_s1"):
        arms_n = {"community": nominal[f"null_community{suffix}"], "mono_fixer": nominal[f"null_mono_fixer{suffix}"],
                  "mono_reducer": nominal[f"null_mono_reducer{suffix}"], "private": nominal[f"null_private{suffix}"]}
        g = evaluate_gate(arms_n, FLOOR, precursors=False)
        null_eval[f"seed{suffix or '_s0'}"] = {"community_only_functions": g["community_only_functions"],
                                               "n_community_only": g["n_community_only"],
                                               "n_vanish_without_exchange": g["n_vanish_without_exchange"],
                                               "levels": {f: d["community"] for f, d in g["levels"].items()},
                                               "n_functions_union": g["n_functions_union"],
                                               "cross_lineage_flux_total": g["cross_lineage_flux_total"]}
    seg = nominal["segregated"]
    seg_gate = evaluate_gate({"community": seg, "mono_fixer": nominal["mono_fixer"], "mono_reducer": nominal["mono_reducer"],
                              "private": nominal["private"], "generalist": nominal["generalist"]}, FLOOR)

    # decision map
    dmap = {"p_diacid": list(p_axis), "k_wash": list(k_axis), "cells": []}
    for pd in p_axis:
        for kw in k_axis:
            arms_m = {arm: results[f"map/{pd:.0e}/{kw}/{arm}"] for arm in ARMS}
            g = evaluate_gate(arms_m, FLOOR)
            c4 = max((g["levels"][f]["community"] for f in g["community_only_functions"]), default=0.0)
            dmap["cells"].append({"p_diacid": pd, "k_wash": kw, "residence_s": 1.0 / kw,
                                  "n_community_only": g["n_community_only"],
                                  "community_only_functions": g["community_only_functions"],
                                  "n_vanish_without_exchange": g["n_vanish_without_exchange"],
                                  "max_community_only_level": c4,
                                  "cross_lineage_flux_total": g["cross_lineage_flux_total"],
                                  "robustness_gain": arms_m["community"]["robustness_gain"],
                                  "max_cell_completeness": g["max_cell_completeness"]})
    boundary = {}
    for kw in k_axis:
        cells = [c for c in dmap["cells"] if c["k_wash"] == kw]
        emerge = [c["p_diacid"] for c in cells if c["n_community_only"] >= 1 and c["n_vanish_without_exchange"] >= 1]
        boundary[str(kw)] = min(emerge) if emerge else None
    dmap["emergence_p_diacid_by_k_wash"] = boundary
    nominal_boundary = boundary.get(str(NOMINAL["k_wash"]))

    all_runs = list(results.values())
    ledger = {"C_residual_max": max(r["C_residual_max"] for r in all_runs),
              "N_residual_max": max(r["N_residual_max"] for r in all_runs),
              "P_residual_max": max(r["P_residual_max"] for r in all_runs),
              "carbon_tolerance": 1.0e-4, "np_tolerance": 1.0e-9,
              "all_within_tolerance": all(r["element_ledger_ok"] >= 0.5 for r in all_runs),
              "n_runs": len(all_runs),
              "firings_total_nominal_community": nominal["community"]["exchange_firings_total"],
              "firings_by_rule_nominal_community": nominal["community"]["firings"]}
    og07 = {arm: {k: nominal[arm][k] for k in ("metacommunity_robustness", "isolated_robustness", "robustness_gain",
                                                "luca_capability_overlap", "capability_diversity", "mean_cell_completeness",
                                                "max_cell_completeness", "n_functions_union")}
            for arm in ("community", "mono_fixer", "mono_reducer", "private", "generalist", "segregated")}
    pkg = load_package("cnp_resources")
    gates = {
        "n_community_only_functions": gate["n_community_only"],
        "n_vanish_without_exchange": gate["n_vanish_without_exchange"],
        "flux_sustained": 1.0 if gate["flux_sustained"] else 0.0,
        "community_cross_lineage_flux_total": gate["cross_lineage_flux_total"],
        "community_max_cell_completeness": gate["max_cell_completeness"],
        "community_over_generalist": gate["community_over_generalist"],
        "null_community_only_max": max(v["n_community_only"] for v in null_eval.values()),
        "null_vanish_without_exchange_max": max(v["n_vanish_without_exchange"] for v in null_eval.values()),
        "precursor_molecules_per_tick": (gate["precursors"][gate["community_only_functions"][0]][0]["molecules_per_tick"]
                                         if gate["community_only_functions"] and gate["precursors"].get(gate["community_only_functions"][0]) else None),
        "community_only_molecules_per_agent": (gate["molecules_per_agent"][gate["community_only_functions"][0]]
                                               if gate["community_only_functions"] else None),
        "segregated_n_community_only": seg_gate["n_community_only"],
        "emergence_p_diacid_at_nominal_residence": nominal_boundary,
        "all_ledgers_ok": ledger["all_within_tolerance"],
        "connected_minus_isolated_robustness": nominal["community"]["metacommunity_robustness"] - nominal["private"]["metacommunity_robustness"],
    }
    artifact = {
        "meta": {"study": "og-07-alt-real-metabolite-exchange", "generated": time.strftime("%Y-%m-%d"), "steps": steps,
                 "nominal": NOMINAL, "floor": FLOOR, "wall_s": time.time() - t0, "quick": quick,
                 "arms": {**ARMS, **EXTRA_ARMS},
                 "pass_rule": "a product class held in the community (settled max concentration >= floor) that neither "
                              "monoculture holds or produces, absent in the private (no-sharing) arm, with a non-zero "
                              "cross-lineage flux of its precursor; max cell completeness < 1"},
        "gate": gate, "null": null_eval, "segregated": seg_gate, "decision_map": dmap, "og07": og07,
        "ledger": ledger, "gates": gates, "provenance_audit": pkg.audit(),
        "arms": {arm: {k: v for k, v in nominal[arm].items() if k not in ("series",)} for arm in nominal},
        "series": {arm: nominal[arm]["series"] for arm in ("community", "private", "generalist")},
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / "community_function_map.json"
    out.write_text(json.dumps(artifact, indent=1, default=_json_default))
    print(f"wrote {out} ({time.time() - t0:.0f} s)")
    print("  community-only:", gate["community_only_functions"], "| vanish w/o exchange:", gate["vanish_without_exchange"])
    print("  intermediates:", [(d["name"], f"{d['moles_per_tick']:.2e}") for d in gate["exchanged_intermediates"]])
    print("  precursors:", {f: [(d["name"], d["made_by"], f"{d['molecules_per_tick']:.2e} molecules/tick") for d in v] for f, v in gate["precursors"].items()},
          "| molecules per agent:", gate["molecules_per_agent"])
    print("  levels:", {f: {k: (f"{v:.2e}" if isinstance(v, float) else v) for k, v in d.items()} for f, d in gate["levels"].items()})
    print("  completeness max/mean:", gate["max_cell_completeness"], gate["mean_cell_completeness"],
          "| over generalist:", gate["community_over_generalist"])
    print("  null:", null_eval, "| segregated:", seg_gate["n_community_only"])
    print("  boundary:", boundary, "| ledger:", {k: ledger[k] for k in ("C_residual_max", "N_residual_max", "P_residual_max", "all_within_tolerance")})
    print("  og07:", {a: {k: round(v, 3) for k, v in d.items()} for a, d in og07.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
