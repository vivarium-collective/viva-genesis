#!/usr/bin/env python
"""Compute + persist the Phase-9 robust-innovation-set artifact (og-08-alt-robust-innovation-set).

Runs the real ``integrated_autonomy_world`` composite — every innovation a
process of an earlier phase, the seven ledgers beside it, the AblationStep
withdrawing the gradient, the mineral access and the feed — over a sampled
ensemble of model structures (storage model x inheritance class x boundary
class x permeability anchor x transport law x maintenance function), each at a
Phase-1 posterior draw, and writes ``artifacts/robust_innovation_set.json``:

* **lattice** — at the nominal ocean floor (``--floor``, 1e-2) every one of
  the eight innovation subsets of {pump, importer, heredity} under every
  structure: which subsets persist, each structure's required set (the
  intersection of its sufficient subsets) and, across structures, the
  intersection and union of the required sets, the lattice node statistics
  and the per-axis breakdown — the gate ``minimum-sufficient-innovation-set``;
* **lattice_rich** — the same lattice at a rich ocean (``--rich-floor``, 1e-1);
* **generic** — the og-adv reject control (the full set with every driver at
  its floor from t = 0 and no pore concentration) under every structure;
* **floor_map** — the full set over the ocean floors (1e-3 .. 1e-1) under
  every structure: where autonomy off-gradient is possible at all;
* **autonomy** — the continuous autonomy value of the persisting full-set
  runs, decomposed by function (work / material / information);
* **discrimination**, **ledger**, the **report** (TransitionReport) and its
  decision-discipline audit, the vg-data audit, and the canonical structure's
  **series** and **events** (full set, the three single knockouts, generic).

    PYTHONPATH=<worktree> python workspace/studies/og-08-alt-robust-innovation-set/sims/compute_robust_innovation_set.py [--structures 24] [--ticks 300] [--workers 6] [--quick]
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
VIZ = STUDY_DIR / "viz"

NOMINAL_FLOOR = 1.0e-2
RICH_FLOOR = 1.0e-1
FLOOR_AXIS = (1.0e-3, 3.0e-3, 1.0e-2, 3.0e-2, 1.0e-1)
CANONICAL = {"model_energy_coupling": "thioester_acyl_phosphate", "model_heredity": "rna_like", "model_boundary": "single_chain",
             "permeability_anchor": "extrapolated", "model_localization": "multisolute_surrogate", "maintenance_law": "constant"}


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


def main() -> int:
    from viva_genesis.provenance import load_package
    from viva_genesis.uq import robust_innovation as RI
    from viva_genesis.uq.phase1_posterior import posterior_draws, posterior_summary
    from viva_genesis.uq.report import decision_discipline
    from viva_genesis.viz_autonomy import ablation_trace_figure, lattice_figure

    n_struct = _arg("--structures", 24)
    n_ticks = _arg("--ticks", 300)
    workers = _arg("--workers", 6)
    seed = _arg("--seed", 0)
    quick = "--quick" in sys.argv
    extra = {}
    if quick:
        n_struct, n_ticks = 4, 120
        extra = {"ablation_start": 1200.0, "ablation_duration": 2400.0}
    t0 = time.time()
    draws = posterior_draws()
    structures = RI.sample_structures(n_struct, seed=seed, n_draws=len(draws))
    floor_axis = (NOMINAL_FLOOR, RICH_FLOOR) if quick else FLOOR_AXIS

    specs: list[tuple[tuple, dict]] = []
    for s in structures:
        base = {**RI.structure_kwargs(s, draws), "n_ticks": n_ticks, **extra}
        for floor_name, floor in (("nominal", NOMINAL_FLOOR), ("rich", RICH_FLOOR)):
            for subset in RI.INNOVATION_SETS:
                specs.append(((s["id"], floor_name, RI.set_label(subset)),
                              {**base, **RI.subset_flags(subset), "feed_floor": floor}))
        specs.append(((s["id"], "nominal", "generic"), {**base, **RI.subset_flags(RI.INNOVATIONS), "feed_floor": NOMINAL_FLOOR,
                                                        "environment": "generic"}))
        for floor in floor_axis:
            if floor in (NOMINAL_FLOOR, RICH_FLOOR):
                continue
            specs.append(((s["id"], f"floor:{floor:.0e}", "pump+importer+heredity"),
                          {**base, **RI.subset_flags(RI.INNOVATIONS), "feed_floor": floor}))
    # the canonical structure's traces (full set, the three knockouts, generic) at the nominal floor
    canon = {**CANONICAL, **draws[0]["endmember"], "n_ticks": n_ticks, "feed_floor": NOMINAL_FLOOR, "series": True, **extra}
    specs.append((("canonical", "nominal", "full"), {**canon, **RI.subset_flags(RI.INNOVATIONS)}))
    for i in RI.INNOVATIONS:
        specs.append((("canonical", "nominal", f"-{i}"), {**canon, **RI.subset_flags(tuple(x for x in RI.INNOVATIONS if x != i))}))
    specs.append((("canonical", "nominal", "generic"), {**canon, **RI.subset_flags(RI.INNOVATIONS), "environment": "generic"}))
    print(f"{len(specs)} integrated-world runs ({n_struct} structures x 8 subsets x 2 floors + generic + {len(floor_axis) - 2} floors + "
          f"5 canonical traces; {n_ticks} ticks) on {workers} workers ...", flush=True)

    results: dict = {}
    cache = ARTIFACTS / ".runs_cache.pkl"
    if "--from-cache" in sys.argv and cache.exists():
        import pickle
        cached = pickle.loads(cache.read_bytes())
        structures, results = cached["structures"], cached["results"]
        print(f"loaded {len(results)} cached runs", flush=True)
    elif int(workers) <= 1:
        for i, (key, spec) in enumerate(specs):
            results[key] = RI.run_point(dict(spec))
            print(f"  [{i + 1}/{len(specs)}] {key} persists={RI.persists(results[key])} ({time.time() - t0:.0f} s)", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=int(workers)) as pool:
            for i, (key, res) in enumerate(zip([k for k, _ in specs], pool.map(RI.run_point, [dict(sp) for _, sp in specs], chunksize=2))):
                results[key] = res
                if (i + 1) % 25 == 0:
                    print(f"  {i + 1}/{len(specs)} done ({time.time() - t0:.0f} s)", flush=True)
    print(f"runs done in {time.time() - t0:.0f} s", flush=True)
    if "--cache" in sys.argv:
        import pickle
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        (ARTIFACTS / ".runs_cache.pkl").write_bytes(pickle.dumps({"structures": structures, "results": results}))

    by_floor = {fn: {(sid, lab): r for (sid, f, lab), r in results.items() if f == fn and sid != "canonical" and lab != "generic"}
                for fn in ("nominal", "rich")}
    generic_results = {(sid, "generic"): r for (sid, f, lab), r in results.items() if lab == "generic" and sid != "canonical"}
    lattice = RI.evaluate_lattice(structures, by_floor["nominal"])
    lattice_rich = RI.evaluate_lattice(structures, by_floor["rich"])
    autonomy = RI.autonomy_summary(structures, by_floor["nominal"], lattice)
    autonomy_rich = RI.autonomy_summary(structures, by_floor["rich"], lattice_rich)
    generic = RI.generic_control(structures, generic_results)
    discrimination = RI.paired_knockouts(structures, by_floor["nominal"])
    discrimination_rich = RI.paired_knockouts(structures, by_floor["rich"])
    ledger = RI.ledger_summary(results)

    # the floor map of the full set
    full = RI.set_label(RI.INNOVATIONS)
    cells = []
    for s in structures:
        for floor in floor_axis:
            if floor == NOMINAL_FLOOR:
                r = results.get((s["id"], "nominal", full))
            elif floor == RICH_FLOOR:
                r = results.get((s["id"], "rich", full))
            else:
                r = results.get((s["id"], f"floor:{floor:.0e}", full))
            if r is None:
                continue
            cells.append({"structure": s["id"], "floor": floor, "persists": RI.persists(r), "net_power": r["settled"]["net_power"],
                          "machinery": r["settled"]["machinery"], "autonomy": r["settled"]["autonomy"],
                          "autonomy_work": r["settled"]["autonomy_work"], "autonomy_material": r["settled"]["autonomy_material"]})
    by_f = {}
    for c in cells:
        by_f.setdefault(c["floor"], []).append(c["persists"])
    emergence = {}
    for s in structures:
        ok = sorted(c["floor"] for c in cells if c["structure"] == s["id"] and c["persists"])
        emergence[s["id"]] = (ok[0] if ok else None)
    floor_map = {"floors": list(floor_axis), "structures": [s["id"] for s in structures], "cells": cells,
                 "persistence_fraction_by_floor": {str(f): float(np.mean(v)) for f, v in by_f.items()},
                 "emergence_floor_by_structure": emergence,
                 "lowest_floor_any_persists": min((f for f in emergence.values() if f is not None), default=None),
                 "lowest_floor_majority_persists": min((f for f, v in by_f.items() if np.mean(v) >= 0.5), default=None)}

    pkg = load_package("integrated_autonomy")
    report = RI.innovation_report(lattice, autonomy, generic, discrimination, ledger, pkg.audit(),
                                  meta={"n_structures": n_struct, "n_ticks": n_ticks, "nominal_floor": NOMINAL_FLOOR,
                                        "rich_floor": RICH_FLOOR, "seed": seed})
    rich_intersection = lattice_rich["required_intersection"]
    gates = {
        "full_set_persistence_fraction": lattice["full_set_persistence_fraction"],
        "full_set_persistence_fraction_rich": lattice_rich["full_set_persistence_fraction"],
        "viable_fraction": lattice["viable_fraction"], "viable_fraction_rich": lattice_rich["viable_fraction"],
        "robust_required_count": len(lattice["required_intersection"]),
        "robust_required_count_rich": len(rich_intersection),
        "required_union_count": len(lattice["required_union"]),
        "required_union_count_rich": len(lattice_rich["required_union"]),
        "required_set_agreement": lattice["required_set_agreement"],
        "required_set_agreement_rich": lattice_rich["required_set_agreement"],
        "og08_intersection_matches": 1.0 if lattice["og08_hypothesis"]["intersection_matches"] else 0.0,
        "og08_intersection_matches_rich": 1.0 if lattice_rich["og08_hypothesis"]["intersection_matches"] else 0.0,
        "minimum_sufficient_set_resolved": 1.0 if (lattice["full_set_persistence_fraction"] >= 0.5 and len(lattice["required_intersection"]) >= 1) else 0.0,
        "minimum_sufficient_set_resolved_rich": 1.0 if (lattice_rich["full_set_persistence_fraction"] >= 0.5 and len(rich_intersection) >= 1) else 0.0,
        "generic_persistence_fraction": generic["persistence_fraction"],
        "generic_rejected": 1.0 if (generic["n"] > 0 and generic["persistence_fraction"] < 0.5 * max(lattice_rich["full_set_persistence_fraction"], 1e-9)
                                    and generic["persistence_fraction"] <= 0.25) else 0.0,
        "all_ledgers_ok": 1.0 if ledger["all_ok"] else 0.0,
        "ledger_ok_runs": ledger["n_ok"], "n_runs": ledger["n_runs"],
        "events_total": ledger["events_total"],
        "autonomy_persisting_full_set": autonomy["persisting_full_set"]["autonomy"]["mean"],
        "autonomy_work_persisting_full_set": autonomy["persisting_full_set"]["autonomy_work"]["mean"],
        "autonomy_material_persisting_full_set": autonomy["persisting_full_set"]["autonomy_material"]["mean"],
        "autonomy_information_persisting_full_set": autonomy["persisting_full_set"]["autonomy_information"]["mean"],
        "autonomy_persisting_full_set_rich": autonomy_rich["persisting_full_set"]["autonomy"]["mean"],
        "autonomy_work_persisting_full_set_rich": autonomy_rich["persisting_full_set"]["autonomy_work"]["mean"],
        "autonomy_material_persisting_full_set_rich": autonomy_rich["persisting_full_set"]["autonomy_material"]["mean"],
        "autonomy_information_persisting_full_set_rich": autonomy_rich["persisting_full_set"]["autonomy_information"]["mean"],
        "autonomy_persisting_any": autonomy["persisting_any"]["autonomy"]["mean"],
        "autonomy_persisting_any_rich": autonomy_rich["persisting_any"]["autonomy"]["mean"],
        "autonomy_work_persisting_any_rich": autonomy_rich["persisting_any"]["autonomy_work"]["mean"],
        "autonomy_material_persisting_any_rich": autonomy_rich["persisting_any"]["autonomy_material"]["mean"],
        "autonomy_information_persisting_any_rich": autonomy_rich["persisting_any"]["autonomy_information"]["mean"],
        "n_persisting_any_rich": autonomy_rich["persisting_any"]["autonomy"]["n"],
        "n_persisting_any": autonomy["persisting_any"]["autonomy"]["n"],
        "autonomy_all_full_set_rich": autonomy_rich["all_full_set"]["autonomy"]["mean"],
        "lowest_floor_majority_persists": floor_map["lowest_floor_majority_persists"],
        "lowest_floor_any_persists": floor_map["lowest_floor_any_persists"],
        "n_posterior_draws": len(draws),
    }
    # the canonical traces at the world tick (the emitter runs at the finer store step) and the
    # per-run reductions without their event lists (the counts stay; the canonical events are kept)
    step = max(int(round(60.0 / 10.0)), 1)
    series = {lab: {k: v[::step] for k, v in results[("canonical", "nominal", lab)]["series"].items()}
              for lab in ("full", "-pump", "-importer", "-heredity", "generic")}
    events = {lab: results[("canonical", "nominal", lab)]["events"] for lab in series}
    runs = {f"{sid}/{f}/{lab}": {k: v for k, v in r.items() if k not in ("series", "events")} | {"persists": RI.persists(r)}
            for (sid, f, lab), r in results.items()}
    artifact = {
        "meta": {"study": "og-08-alt-robust-innovation-set", "generated": time.strftime("%Y-%m-%d"), "n_structures": n_struct,
                 "n_ticks": n_ticks, "tick_seconds": 60.0, "ablation_start": 3600.0, "ablation_duration": 6000.0,
                 "nominal_floor": NOMINAL_FLOOR, "rich_floor": RICH_FLOOR, "floor_axis": list(floor_axis), "seed": seed, "series_step_s": 60.0,
                 "wall_s": time.time() - t0, "quick": quick, "n_runs": len(results), "axes": RI.STRUCTURE_AXES,
                 "canonical_structure": CANONICAL, "posterior": posterior_summary(draws),
                 "pass_rule": "a subset persists under a structure when, over the final 15 % of the run with every driver at its "
                              "floor, the settled work budget and material budget are both non-negative and >= half the founders "
                              "are alive; a structure's required set is the intersection of its sufficient subsets; the gate "
                              "resolves when the full set persists under >= 50 % of the sampled structures and the intersection of "
                              "the required sets over the viable structures is non-empty"},
        "structures": structures, "lattice": lattice, "lattice_rich": lattice_rich, "autonomy": autonomy,
        "autonomy_rich": autonomy_rich, "generic": generic, "discrimination": discrimination,
        "discrimination_rich": discrimination_rich, "floor_map": floor_map, "ledger": ledger, "gates": gates,
        "report": report.to_dict(), "decision_discipline": decision_discipline(report), "provenance_audit": pkg.audit(),
        "series": series, "events": events, "runs": runs,
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / "robust_innovation_set.json"
    out.write_text(json.dumps(artifact, separators=(",", ":"), default=_json_default))
    VIZ.mkdir(parents=True, exist_ok=True)
    (VIZ / "robust-innovation-lattice.html").write_text(lattice_figure(artifact, title="Phase 9 — the innovation lattice across model structures (Decision view)"))
    (VIZ / "autonomy-ablation-trace.html").write_text(ablation_trace_figure(artifact, title="Phase 9 — the integrated world through the withdrawal (Mechanism / World view)"))
    print(f"wrote {out} ({time.time() - t0:.0f} s)")
    print("  nominal lattice:", {k: lattice[k] for k in ("n_structures", "n_viable", "full_set_persistence_fraction",
                                                         "required_intersection", "required_union", "required_fraction", "modal_required")})
    print("  rich lattice:", {k: lattice_rich[k] for k in ("n_viable", "full_set_persistence_fraction", "required_intersection",
                                                           "required_union", "required_fraction", "modal_required")})
    print("  nodes (nominal):", {k: v["persistence_fraction"] for k, v in lattice["nodes"].items()})
    print("  nodes (rich):", {k: v["persistence_fraction"] for k, v in lattice_rich["nodes"].items()})
    print("  generic:", generic, "| floor map:", floor_map["persistence_fraction_by_floor"])
    print("  autonomy (persisting full set, nominal / rich):", autonomy["persisting_full_set"], autonomy_rich["persisting_full_set"])
    print("  ledger:", {k: ledger[k] for k in ("n_runs", "n_ok", "all_ok", "worst_residuals", "events_total")})
    print("  " + report.headline())
    print("  decision discipline:", artifact["decision_discipline"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
