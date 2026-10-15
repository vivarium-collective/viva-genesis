#!/usr/bin/env python
"""Compute + persist the Phase-7 information-per-cost artifact (og-06-alt-information-per-cost).

Runs the six ``heredity`` classes through the real ``competing_heredity``
composite (exact Gillespie lineages, matched chemostat budgets, the
information ledger) and writes ``artifacts/information_frontier.json``:

* **frontier** — every class with heredity forced ``on`` and, as its own
  control, forced ``off`` (daughters re-form their heritable material de novo
  from the same budget), ``--seeds`` seeds each, ``--steps`` ticks: realised
  heritable bits (parent→offspring MI net of the permutation null, with the
  convergence flag), energy and precursors per offspring, bits per joule and
  per precursor, the (bits ↑, energy ↓) Pareto front — and the gate
  ``ancestry-predicts-phenotype`` evaluated per class (converged, ≥ 0.1 bit,
  ≥ 0.05 bit above its control).
* **attachment_map** — with the ``HeredityAttachmentStep`` deciding, the
  fraction of ticks heredity is attached and the bits it transmits, per class,
  across a matched budget scale (every feed set-point and the power scaled
  together) — the swept, hypothetical attachment thresholds.
* **fidelity_transition** — the template-type classes across their copy
  fidelity (rna_like / hybrid: q; peptide: q_p; mineral_state: p_m) with the
  step deciding: where the Eigen floor lets templated heredity attach and
  where its bits overtake the best non-templated class ("transition to
  templated heredity").

    PYTHONPATH=<worktree> python workspace/studies/og-06-alt-information-per-cost/sims/compute_information_frontier.py [--seeds 4] [--steps 80] [--workers 6]
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

CLASSES = ("compositional", "network", "peptide", "rna_like", "hybrid", "mineral_state")
TEMPLATED = ("rna_like", "hybrid", "peptide")
BUDGET_SCALES = (0.01, 0.03, 0.1, 0.3, 1.0, 3.0)
FIDELITY_AXES = {
    "rna_like": ("per_site_fidelity", (0.85, 0.90, 0.93, 0.95, 0.967, 0.99)),
    "hybrid": ("per_site_fidelity", (0.85, 0.90, 0.93, 0.95, 0.967, 0.99)),
    "peptide": ("peptide_fidelity", (0.5, 0.6, 0.7, 0.8, 0.9, 0.95)),
    "mineral_state": ("defect_copy_error", (0.05, 0.02, 0.01, 0.005, 0.002, 0.001)),
}
NOMINAL_FEED, NOMINAL_POWER = 1.0e-4, 8.0e-16
MIN_BITS, MIN_DELTA = 0.1, 0.05        # pre-registered per-class pass rule (ancestry-predicts-phenotype)


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
    return str(o)


def run_point(spec: dict) -> dict:
    """Build -> run -> reduce one composite (module-level so the pool can pickle it)."""
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.core import build_core
    from viva_genesis.composites.competing_heredity import competing_heredity, PHASE7_REDUCERS
    n_steps = int(spec.pop("n_steps"))
    core = build_core()
    sim = Composite({"state": competing_heredity(core, **spec)}, core=core)
    sim.run(float(n_steps))
    rows = gather_emitter_results(sim)[("emitter",)]
    last = rows[-1]
    out = {k: float(fn(rows)) for k, fn in PHASE7_REDUCERS.items()}
    out.update({
        "mi_standard_error": float(last["mi_standard_error"]),
        "information_capacity": float(last["information_capacity"]),
        "precursors_per_offspring": float(last["precursors_per_offspring"]),
        "bits_per_precursor": float(last["bits_per_precursor"]),
        "fidelity": float(last["fidelity"]),
        "fidelity_floor": float(last["fidelity_floor"]),
        "attachment_margin": float(last["attachment_margin"]),
        "energy_residual_max": max(float(r["energy_residual"]) for r in rows),
        "energy_used": float(last["energy_used"]), "energy_in": float(last["energy_in"]),
        "mean_molecules": float(last["mean_molecules"]), "population": float(last["population"]),
        "functional_fraction": float(last["functional_fraction"]),
        "function_series": [float(r["mean_function"]) for r in rows],
        "bits_series": [float(r["information_content"]) for r in rows],
        "attached_series": [float(r["attached"]) for r in rows],
    })
    return {"spec": spec, "n_steps": n_steps, **out}


def _mean_sd(vals):
    v = [float(x) for x in vals if x is not None and math.isfinite(float(x))]
    if not v:
        return float("nan"), float("nan")
    return float(np.mean(v)), (float(np.std(v, ddof=1)) if len(v) > 1 else 0.0)


def _aggregate(points: list[dict]) -> dict:
    agg = {"n": len(points), "per_seed": points}
    for k in ("heritable_bits", "energy_per_offspring", "precursors_per_offspring", "bits_per_joule",
              "bits_per_precursor", "fidelity", "heritability", "settled_mean_function", "mean_molecules",
              "attached_fraction", "information_capacity", "energy_residual_max"):
        m, s = _mean_sd([p[k] for p in points])
        agg[k] = m
        agg[k + "_sd"] = s
    agg["mi_converged_all"] = all(p["mi_converged"] >= 0.5 for p in points)
    agg["mi_converged_fraction"] = float(np.mean([p["mi_converged"] >= 0.5 for p in points]))
    agg["ledger_all_ok"] = all(p["information_ledger_ok"] >= 0.5 for p in points)
    # information per cost from the pooled means (bits / mean cost per offspring)
    e, pr, b = agg["energy_per_offspring"], agg["precursors_per_offspring"], agg["heritable_bits"]
    agg["bits_per_joule_pooled"] = (b / e) if e > 0 else (float("inf") if b > 0 else 0.0)
    agg["bits_per_precursor_pooled"] = (b / pr) if pr > 0 else (float("inf") if b > 0 else 0.0)
    return agg


def main() -> int:
    from viva_genesis.heredity.information import pareto_front
    from viva_genesis.provenance import load_package

    seeds = _arg("--seeds", 4)
    steps = _arg("--steps", 80)
    workers = _arg("--workers", 6)
    map_seeds = max(2, seeds // 2)
    t0 = time.time()

    specs: list[tuple[str, dict]] = []
    for cls in CLASSES:
        for arm in ("on", "off"):
            for s in range(seeds):
                specs.append((f"frontier/{cls}/{arm}/{s}",
                              {"model_heredity": cls, "attachment": arm, "seed": 100 + s, "n_steps": steps}))
    for cls in CLASSES:
        for sc in BUDGET_SCALES:
            for s in range(map_seeds):
                specs.append((f"map/{cls}/{sc}/{s}",
                              {"model_heredity": cls, "attachment": "step", "seed": 200 + s, "n_steps": max(40, steps * 3 // 4),
                               "nucleotide_feed": NOMINAL_FEED * sc, "amino_feed": NOMINAL_FEED * sc,
                               "amphiphile_feed": NOMINAL_FEED * sc, "mineral_feed": NOMINAL_FEED * sc,
                               "power": NOMINAL_POWER * sc}))
    for cls, (knob, values) in FIDELITY_AXES.items():
        for v in values:
            for s in range(map_seeds):
                specs.append((f"fidelity/{cls}/{v}/{s}",
                              {"model_heredity": cls, "attachment": "step", "seed": 300 + s,
                               "n_steps": max(40, steps * 3 // 4), knob: v}))
    print(f"{len(specs)} composite runs on {workers} workers ...", flush=True)
    results: dict[str, dict] = {}
    with ProcessPoolExecutor(max_workers=int(workers)) as pool:
        for key, res in zip([k for k, _ in specs], pool.map(run_point, [dict(s) for _, s in specs])):
            results[key] = res
    print(f"runs done in {time.time() - t0:.0f} s", flush=True)

    # ---- frontier ---------------------------------------------------------------
    classes = {}
    for cls in CLASSES:
        on = _aggregate([results[f"frontier/{cls}/on/{s}"] for s in range(seeds)])
        off = _aggregate([results[f"frontier/{cls}/off/{s}"] for s in range(seeds)])
        delta = on["heritable_bits"] - off["heritable_bits"]
        passes = bool(on["mi_converged_all"] and on["heritable_bits"] >= MIN_BITS and delta >= MIN_DELTA)
        classes[cls] = {"attached": on, "control": off, "delta_bits": delta, "passes_ancestry": passes,
                        "templated": cls in TEMPLATED}
    points = {cls: (classes[cls]["attached"]["heritable_bits"], classes[cls]["attached"]["energy_per_offspring"])
              for cls in CLASSES if classes[cls]["attached"]["mi_converged_all"]}
    pareto = pareto_front(points)
    bpj = {cls: classes[cls]["attached"]["bits_per_joule_pooled"] for cls in CLASSES}
    finite = [v for v in bpj.values() if math.isfinite(v) and v > 0]
    span = (math.log10(max(finite)) - math.log10(min(finite))) if len(finite) >= 2 else float("nan")
    rna_bits = classes["rna_like"]["attached"]["heritable_bits"]
    nonrna = {c: classes[c]["attached"]["heritable_bits"] for c in CLASSES if c != "rna_like" and classes[c]["attached"]["mi_converged_all"]}
    best_nonrna = max(nonrna, key=nonrna.get) if nonrna else None
    nonrna_fraction = (nonrna[best_nonrna] / rna_bits) if (best_nonrna and rna_bits > 0) else float("nan")
    # class substitution in the other currency: the best non-RNA class's bits per joule
    # over the rna_like class's (certified classes only)
    rna_bpj = bpj["rna_like"] if classes["rna_like"]["attached"]["mi_converged_all"] else float("nan")
    nonrna_bpj = {c: bpj[c] for c in nonrna}
    best_nonrna_bpj = max(nonrna_bpj, key=nonrna_bpj.get) if nonrna_bpj else None
    nonrna_bpj_fraction = (nonrna_bpj[best_nonrna_bpj] / rna_bpj) if (best_nonrna_bpj and rna_bpj and math.isfinite(rna_bpj) and rna_bpj > 0) else float("nan")
    cheapest = max(bpj, key=lambda c: bpj[c] if math.isfinite(bpj[c]) else -1)
    richest = max(CLASSES, key=lambda c: classes[c]["attached"]["heritable_bits"])

    # ---- attachment map ------------------------------------------------------------
    amap = {"budget_scales": list(BUDGET_SCALES), "nominal_feed": NOMINAL_FEED, "nominal_power": NOMINAL_POWER, "per_class": {}}
    for cls in CLASSES:
        rows = []
        for sc in BUDGET_SCALES:
            pts = [results[f"map/{cls}/{sc}/{s}"] for s in range(map_seeds)]
            rows.append({"scale": sc, "attached_fraction": float(np.mean([p["attached_fraction"] for p in pts])),
                         "heritable_bits": float(np.mean([p["heritable_bits"] for p in pts])),
                         "mi_converged_fraction": float(np.mean([p["mi_converged"] >= 0.5 for p in pts])),
                         "settled_mean_function": float(np.mean([p["settled_mean_function"] for p in pts])),
                         "attachment_margin": float(np.mean([p["attachment_margin"] for p in pts])),
                         "fidelity_floor": float(pts[0]["fidelity_floor"])})
        can_attach = any(r["attached_fraction"] > 0 for r in rows)
        amap["per_class"][cls] = {"rows": rows, "can_attach_at_nominal_fidelity": can_attach,
                                  "span": (rows[-1]["attached_fraction"] - rows[0]["attached_fraction"]) if can_attach else None}
    spans = [v["span"] for v in amap["per_class"].values() if v["span"] is not None]
    amap["attachment_budget_span"] = float(np.mean(spans)) if spans else 0.0
    amap["n_classes_attachable"] = sum(1 for v in amap["per_class"].values() if v["can_attach_at_nominal_fidelity"])

    # ---- fidelity transition -------------------------------------------------------
    fmap = {"per_class": {}}
    best_nontemplated_bits = max(classes[c]["attached"]["heritable_bits"] for c in CLASSES if c not in TEMPLATED)
    # the organic non-templated classes (compositional, network) — the comparison the
    # "transition to templated heredity" is usually posed against; mineral_state is reported beside it
    best_organic_bits = max(classes[c]["attached"]["heritable_bits"] for c in ("compositional", "network"))
    for cls, (knob, values) in FIDELITY_AXES.items():
        rows = []
        for v in values:
            pts = [results[f"fidelity/{cls}/{v}/{s}"] for s in range(map_seeds)]
            rows.append({knob: v, "attached_fraction": float(np.mean([p["attached_fraction"] for p in pts])),
                         "heritable_bits": float(np.mean([p["heritable_bits"] for p in pts])),
                         "mi_converged_fraction": float(np.mean([p["mi_converged"] >= 0.5 for p in pts])),
                         "settled_mean_function": float(np.mean([p["settled_mean_function"] for p in pts])),
                         "fidelity": float(np.mean([p["fidelity"] for p in pts]))})
        attach_from = next((r[knob] for r in rows if r["attached_fraction"] > 0.5), None)
        overtake_from = next((r[knob] for r in rows if r["attached_fraction"] > 0.5 and r["heritable_bits"] > best_nontemplated_bits), None)
        overtake_organic = next((r[knob] for r in rows if r["attached_fraction"] > 0.5 and r["heritable_bits"] > best_organic_bits), None)
        fmap["per_class"][cls] = {"knob": knob, "rows": rows, "attaches_from": attach_from,
                                  "overtakes_nontemplated_from": overtake_from, "overtakes_organic_from": overtake_organic}
    fmap["best_nontemplated_bits"] = best_nontemplated_bits
    fmap["best_organic_bits"] = best_organic_bits
    fmap["templated_takeover_fidelity"] = fmap["per_class"]["rna_like"]["overtakes_organic_from"]
    fmap["templated_takeover_vs_mineral"] = fmap["per_class"]["rna_like"]["overtakes_nontemplated_from"]

    # ---- ledger + provenance -------------------------------------------------------
    all_runs = list(results.values())
    ledger = {"energy_residual_max": max(r["energy_residual_max"] for r in all_runs),
              "energy_tolerance": 1.0e-9,
              "all_energy_within_tolerance": all(r["energy_residual_max"] <= 1.0e-9 for r in all_runs),
              "n_runs": len(all_runs),
              "n_converged": sum(1 for r in all_runs if r["mi_converged"] >= 0.5),
              # the ledger certifies one tick behind the class (it reads the flag published last tick)
              "n_ledger_certified": sum(1 for r in all_runs if r["information_ledger_ok"] >= 0.5)}
    pkg = load_package("inheritance_budgets")
    gates = {"n_classes_ancestry_predicts": sum(1 for c in classes.values() if c["passes_ancestry"]),
             "frontier_pareto_size": len(pareto), "frontier_span_decades": span,
             "nonrna_bits_fraction": nonrna_fraction, "best_nonrna_class": best_nonrna,
             "nonrna_bits_per_joule_fraction": nonrna_bpj_fraction, "best_nonrna_bits_per_joule_class": best_nonrna_bpj,
             "n_classes_converged_all_seeds": sum(1 for c in classes.values() if c["attached"]["mi_converged_all"]),
             "attachment_budget_span": amap["attachment_budget_span"],
             "templated_takeover_fidelity": fmap["templated_takeover_fidelity"],
             "templated_takeover_vs_mineral": fmap["templated_takeover_vs_mineral"],
             "all_energy_within_tolerance": ledger["all_energy_within_tolerance"],
             "cheapest_bits_class": cheapest, "richest_bits_class": richest}
    artifact = {
        "meta": {"study": "og-06-alt-information-per-cost", "generated": time.strftime("%Y-%m-%d"),
                 "seeds": seeds, "steps": steps, "map_seeds": map_seeds, "wall_s": time.time() - t0,
                 "pass_rule": {"min_bits": MIN_BITS, "min_delta_vs_control": MIN_DELTA, "requires_mi_convergence": True},
                 "classes": list(CLASSES)},
        "classes": classes,
        "frontier": {"points": {c: list(v) for c, v in points.items()}, "pareto": pareto, "bits_per_joule": bpj,
                     "span_decades_bits_per_joule": span},
        "attachment_map": amap, "fidelity_transition": fmap, "ledger": ledger, "gates": gates,
        "provenance_audit": pkg.audit(),
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / "information_frontier.json"
    out.write_text(json.dumps(artifact, indent=1, default=_json_default))
    print(f"wrote {out} ({time.time() - t0:.0f} s)")
    for cls in CLASSES:
        a, c = classes[cls]["attached"], classes[cls]["control"]
        print(f"  {cls:14s} bits {a['heritable_bits']:.3f}±{a['heritable_bits_sd']:.3f} (ctrl {c['heritable_bits']:.3f}) "
              f"conv={a['mi_converged_all']} E/off {a['energy_per_offspring']:.2e} J  bits/J {a['bits_per_joule_pooled']:.2e}  "
              f"prec/off {a['precursors_per_offspring']:.1f}  phi {a['settled_mean_function']:.2f}  pass={classes[cls]['passes_ancestry']}")
    print("  pareto:", pareto, "| gates:", gates)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
