"""The robust innovation set — og-08's gate across model structures (Phase 9).

Model Upgrade plan, Phase 9: re-run the ``{pump, importer, heredity}`` result
of og-08 inside the integrated world under an ENSEMBLE of model structures and
report the *intersection* of the innovations required across them, as a
lattice, with the continuous autonomy value decomposed by function.

* :func:`sample_structures` — a balanced categorical design over the five
  structural axes (storage model, inheritance class, permeability assumption
  = boundary class x permeability anchor, transport law, maintenance law),
  each structure paired with one Phase-1 posterior draw (cycled);
* :func:`run_point` — build, run and reduce one world (module-level, so a
  process pool can pickle it);
* :func:`persists` — the pre-registered persistence rule: over the final
  window, with every driver at its floor, the lineage's work budget AND its
  material budget are non-negative and at least half its founding individuals
  are alive;
* :func:`evaluate_lattice` — per structure the sufficient subsets, their
  minimal elements and the *required* set (the intersection of the sufficient
  subsets; undefined where no subset persists); across structures the
  lattice node statistics, the intersection and union of the required sets
  and the per-level breakdown of each innovation's necessity;
* :func:`autonomy_summary` — the autonomy value of the persisting full-set
  runs, decomposed (work / material / information) and work-weighted;
* :func:`innovation_report` — the :class:`~viva_genesis.uq.report.TransitionReport`.
"""

from __future__ import annotations

import itertools
import math
from typing import Iterable

import numpy as np

from .report import Discrimination, EvidenceTier, Feasibility, Robustness, TransitionReport

INNOVATIONS = ("pump", "importer", "heredity")
INNOVATION_SETS = tuple(tuple(i for i in INNOVATIONS if (mask >> k) & 1) for mask in range(8) for k in [0]
                        for _ in [0]) if False else tuple(
    tuple(i for k, i in enumerate(INNOVATIONS) if (mask >> k) & 1) for mask in range(8))

STRUCTURE_AXES = {
    "model_energy_coupling": ("h_na_gradient_leaky_membrane", "thioester_acyl_phosphate", "polyphosphate", "fe_redox"),
    "model_heredity": ("compositional", "network", "peptide", "rna_like", "hybrid", "mineral_state"),
    "model_boundary": ("single_chain", "mixed", "thioester_aminothiol"),
    "permeability_anchor": ("extrapolated", "measured"),
    "model_localization": ("multisolute_surrogate", "surrogate", "fipy"),
    "maintenance_law": ("constant", "leak_repair", "turnover"),
}
AXIS_LABELS = {"model_energy_coupling": "storage model", "model_heredity": "inheritance class",
               "model_boundary": "boundary class", "permeability_anchor": "permeability anchor",
               "model_localization": "transport law", "maintenance_law": "maintenance function"}
SETTLE_FRACTION = 0.15


def set_label(subset: Iterable[str]) -> str:
    s = tuple(subset)
    return "+".join(s) if s else "none"


def subset_flags(subset: Iterable[str]) -> dict:
    s = set(subset)
    return {i: ("on" if i in s else "off") for i in INNOVATIONS}


# --------------------------------------------------------------------------- #
# The structural design
# --------------------------------------------------------------------------- #
def sample_structures(n: int, seed: int = 0, n_draws: int = 6, axes: dict | None = None) -> list[dict]:
    """``n`` structures over the categorical axes with near-uniform marginals
    (each axis: its levels repeated and shuffled independently — a categorical
    Latin design), each with a posterior-draw index cycled over ``n_draws``."""
    axes = dict(axes or STRUCTURE_AXES)
    rng = np.random.default_rng(int(seed))
    cols = {}
    for name, levels in axes.items():
        reps = int(math.ceil(n / len(levels)))
        col = list(levels) * reps
        rng.shuffle(col)
        cols[name] = col[:n]
    out = []
    for i in range(n):
        s = {name: cols[name][i] for name in axes}
        s["draw"] = i % max(int(n_draws), 1)
        s["id"] = f"s{i:02d}"
        out.append(s)
    return out


def structure_kwargs(structure: dict, draws: list[dict]) -> dict:
    """Generator kwargs for a structure: its classes + its posterior draw's endmembers."""
    kw = {k: structure[k] for k in STRUCTURE_AXES}
    kw.update(draws[int(structure["draw"]) % len(draws)]["endmember"])
    return kw


# --------------------------------------------------------------------------- #
# One run
# --------------------------------------------------------------------------- #
def _settled(rows, key, frac=SETTLE_FRACTION):
    n = max(1, int(round(len(rows) * frac)))
    v = [float(r.get(key, float("nan"))) for r in rows[-n:]]
    return float(sum(v) / len(v)) if v else float("nan")


def _at_hold_end(rows, key, start_s: float):
    """The value just before the ablation starts (the in-vent steady state)."""
    before = [r for r in rows if float(r.get("global_time", 0.0)) <= start_s]
    tail = before[-5:] if before else rows[:1]
    v = [float(r.get(key, float("nan"))) for r in tail]
    return float(sum(v) / len(v)) if v else float("nan")


SERIES_KEYS = ("gradient_support", "feed_support", "external_power", "internal_power", "maintenance_power", "import_power",
               "heredity_power", "net_power", "material_net", "machinery", "attached", "survivors", "n_alive",
               "autonomy", "autonomy_work", "autonomy_material", "autonomy_information", "energy_charge_fraction",
               "total_organic_carbon", "drive_availability")
SETTLED_KEYS = ("external_power", "internal_power", "maintenance_power", "import_power", "heredity_power", "net_power",
                "material_supply", "material_net", "passive_carbon", "active_carbon", "fixation_carbon", "degradation_carbon",
                "machinery", "drive_availability", "autonomy", "autonomy_work", "autonomy_material", "autonomy_information",
                "survivors", "n_alive", "attached", "mean_function", "information_content", "mi_converged",
                "total_organic_carbon", "energy_charge_fraction")


def run_point(spec: dict) -> dict:
    """Build -> run -> reduce one integrated world (picklable for a process pool)."""
    import roadrunner
    roadrunner.Logger.setLevel(roadrunner.Logger.LOG_ERROR)
    from process_bigraph import Composite, gather_emitter_results
    from ..core import build_core
    from ..composites.integrated_autonomy import (LEDGER_FLAGS, PHASE9_REDUCERS, integrated_autonomy_world,
                                                  worst_residuals)
    spec = dict(spec)
    n_ticks = int(spec.pop("n_ticks"))
    keep_series = bool(spec.pop("series", False))
    core = build_core()
    doc = integrated_autonomy_world(core, **spec)
    dt = float(spec.get("tick_seconds", 60.0))
    sim = Composite({"state": doc}, core=core)
    sim.run(float(n_ticks) * dt)
    rows = gather_emitter_results(sim)[("emitter",)]
    last = rows[-1]
    start = float(spec.get("ablation_start", 3600.0))
    out = {k: float(fn(rows)) for k, fn in PHASE9_REDUCERS.items()}
    out["settled"] = {k: _settled(rows, k) for k in SETTLED_KEYS}
    out["in_vent"] = {k: _at_hold_end(rows, k, start) for k in SETTLED_KEYS}
    out["ledgers"] = {k: float(last.get(k, float("nan"))) for k in LEDGER_FLAGS}
    out["ledgers"]["information_energy_residual"] = float(last.get("energy_residual", float("nan")))
    out["residuals"] = worst_residuals(rows)
    ev = last.get("events") or {}
    out["events"] = sorted(({"t": float(v["t"]), "kind": str(v["kind"]), "detail": str(v.get("detail", ""))}
                            for v in ev.values()), key=lambda e: e["t"])
    out["n_events"] = len(out["events"])
    out["divisions"] = sum(1 for e in out["events"] if e["kind"] == "division")
    out["extinctions"] = sum(1 for e in out["events"] if e["kind"] == "extinction")
    out["final"] = {k: float(last.get(k, float("nan"))) for k in ("survivors", "n_alive", "max_generation", "event_count",
                                                                   "exchange_firings_total", "import_firings")}
    if keep_series:
        out["series"] = {"t": [float(r["global_time"]) for r in rows],
                         **{k: [float(r.get(k, float("nan"))) for r in rows] for k in SERIES_KEYS}}
    out["spec"] = spec
    out["n_ticks"] = n_ticks
    return out


# --------------------------------------------------------------------------- #
# The persistence rule and the lattice
# --------------------------------------------------------------------------- #
def persists(point: dict, survivor_floor: float = 0.5) -> bool:
    """Pre-registered: with every driver at its floor, the settled work budget
    and material budget are both non-negative and at least ``survivor_floor``
    of the founders are alive."""
    s = point["settled"]
    return bool(point.get("ablation_complete", 0.0) >= 0.5 and s["net_power"] >= 0.0 and s["material_net"] >= 0.0
                and s["survivors"] >= survivor_floor)


def every_ledger_ok(point: dict) -> bool:
    return bool(point.get("every_ledger_ok", 0.0) >= 0.5)


def _minimal(sets: list[tuple]) -> list[tuple]:
    out = []
    for s in sets:
        if not any(set(o) < set(s) for o in sets):
            out.append(s)
    return out


def evaluate_structure(by_set: dict) -> dict:
    """``by_set``: ``{innovation subset (tuple): persists (bool)}`` for one structure."""
    sufficient = [s for s, ok in by_set.items() if ok]
    minimal = _minimal(sufficient)
    if sufficient:
        required = set(INNOVATIONS)
        for s in sufficient:
            required &= set(s)
        required = tuple(i for i in INNOVATIONS if i in required)
    else:
        required = None
    return {"sufficient": [set_label(s) for s in sufficient], "minimal_sufficient": [set_label(s) for s in minimal],
            "required": (list(required) if required is not None else None),
            "full_set_persists": bool(by_set.get(tuple(INNOVATIONS), False)),
            "none_persists": bool(by_set.get((), False)),
            "persists": {set_label(s): bool(ok) for s, ok in by_set.items()}}


def evaluate_lattice(structures: list[dict], results: dict) -> dict:
    """``results``: ``{(structure_id, set_label): point}``. Returns the lattice
    over structures: per-subset persistence fractions, per-structure required
    sets, the intersection / union of the required sets over the structures
    where some subset persists, the per-axis breakdown and the agreement."""
    per_structure = {}
    for s in structures:
        by_set = {}
        for subset in INNOVATION_SETS:
            p = results.get((s["id"], set_label(subset)))
            if p is not None:
                by_set[subset] = persists(p)
        per_structure[s["id"]] = evaluate_structure(by_set)
    sids = list(per_structure)
    n = len(sids)
    nodes = {}
    for subset in INNOVATION_SETS:
        lab = set_label(subset)
        flags = [per_structure[sid]["persists"].get(lab, False) for sid in sids]
        nodes[lab] = {"innovations": list(subset), "n_persist": int(sum(flags)), "n": n,
                      "persistence_fraction": (float(np.mean(flags)) if flags else float("nan"))}
    viable = [sid for sid in sids if per_structure[sid]["required"] is not None]
    inter = set(INNOVATIONS) if viable else set()
    union = set()
    for sid in viable:
        req = set(per_structure[sid]["required"])
        inter &= req
        union |= req
    counts = {i: sum(1 for sid in viable if i in per_structure[sid]["required"]) for i in INNOVATIONS}
    modal = None
    if viable:
        from collections import Counter
        modal_key, modal_n = Counter(tuple(per_structure[sid]["required"]) for sid in viable).most_common(1)[0]
        modal = {"required": list(modal_key), "fraction": modal_n / len(viable)}
    # per-axis breakdown: full-set persistence and each innovation's necessity per level
    by_axis = {}
    for axis, levels in STRUCTURE_AXES.items():
        by_axis[axis] = {}
        for lev in levels:
            ids = [s["id"] for s in structures if s.get(axis) == lev]
            if not ids:
                continue
            full = [per_structure[sid]["full_set_persists"] for sid in ids]
            v = [sid for sid in ids if per_structure[sid]["required"] is not None]
            by_axis[axis][lev] = {
                "n": len(ids), "full_set_persistence": float(np.mean(full)) if full else float("nan"),
                "n_viable": len(v),
                "required_fraction": {i: (float(np.mean([i in per_structure[sid]["required"] for sid in v])) if v else float("nan"))
                                      for i in INNOVATIONS},
            }
    return {
        "n_structures": n, "n_viable": len(viable), "viable_fraction": (len(viable) / n if n else float("nan")),
        "full_set_persistence_fraction": nodes[set_label(INNOVATIONS)]["persistence_fraction"],
        "none_persistence_fraction": nodes["none"]["persistence_fraction"],
        "nodes": nodes, "per_structure": per_structure,
        "required_intersection": [i for i in INNOVATIONS if i in inter],
        "required_union": [i for i in INNOVATIONS if i in union],
        "required_counts": counts,
        "required_fraction": {i: (counts[i] / len(viable) if viable else float("nan")) for i in INNOVATIONS},
        "modal_required": modal,
        "required_set_agreement": (modal["fraction"] if modal else float("nan")),
        "og08_hypothesis": {"set": list(INNOVATIONS),
                            "intersection_matches": sorted(inter) == sorted(INNOVATIONS) if viable else False,
                            "union_matches": sorted(union) == sorted(INNOVATIONS) if viable else False},
        "by_axis": by_axis,
    }


def autonomy_summary(structures: list[dict], results: dict, lattice: dict) -> dict:
    """The autonomy value of the persisting full-set runs, decomposed."""
    full = set_label(INNOVATIONS)
    keys = ("autonomy", "autonomy_work", "autonomy_material", "autonomy_information")
    rows_p, rows_all, in_vent = [], [], []
    for s in structures:
        p = results.get((s["id"], full))
        if p is None:
            continue
        rows_all.append({k: p["settled"][k] for k in keys})
        in_vent.append({k: p["in_vent"][k] for k in keys})
        if lattice["per_structure"][s["id"]]["full_set_persists"]:
            rows_p.append({k: p["settled"][k] for k in keys})

    def _stats(rows):
        if not rows:
            return {k: {"mean": float("nan"), "min": float("nan"), "max": float("nan"), "n": 0} for k in keys}
        return {k: {"mean": float(np.mean([r[k] for r in rows])), "min": float(np.min([r[k] for r in rows])),
                    "max": float(np.max([r[k] for r in rows])), "n": len(rows)} for k in keys}
    return {"persisting_full_set": _stats(rows_p), "all_full_set": _stats(rows_all), "in_vent_full_set": _stats(in_vent),
            "definition": {"autonomy_work": "internal store work / (internal + external tap)",
                           "autonomy_material": "(active import + own fixation) / (passive uptake + active + fixation) of organic carbon",
                           "autonomy_information": "heredity-held machinery / (machinery + mineral catalysis)",
                           "autonomy": "work-weighted: (internal + own material x dG_C) / (all work + all material x dG_C)"}}


def generic_control(structures: list[dict], results: dict) -> dict:
    """The og-adv reject control: the full set in the generic environment must NOT persist."""
    flags, ids = [], []
    for s in structures:
        p = results.get((s["id"], "generic"))
        if p is None:
            continue
        flags.append(persists(p))
        ids.append(s["id"])
    return {"n": len(flags), "n_persist": int(sum(flags)),
            "persistence_fraction": (float(np.mean(flags)) if flags else float("nan")), "ids": ids}


def paired_knockouts(structures: list[dict], results: dict, readouts=("net_power", "autonomy", "machinery", "internal_power")) -> dict:
    """Discrimination: the paired difference between the full set and each single
    knockout on identical structures (the standardised d of uq.ensemble)."""
    from .ensemble import paired_class_difference
    full = set_label(INNOVATIONS)
    out = {}
    for i in INNOVATIONS:
        ko = set_label(tuple(x for x in INNOVATIONS if x != i))
        a, b = [], []
        for s in structures:
            pa, pb = results.get((s["id"], full)), results.get((s["id"], ko))
            if pa is None or pb is None:
                continue
            a.append(pa["settled"])
            b.append(pb["settled"])
        if len(a) >= 2:
            out[f"-{i}"] = paired_class_difference({"full": a, f"-{i}": b}, list(readouts))
    return out


def ledger_summary(results: dict) -> dict:
    pts = list(results.values())
    worst = {}
    for p in pts:
        for k, v in (p.get("residuals") or {}).items():
            if v == v:
                worst[k] = max(worst.get(k, 0.0), float(v))
    flags = {}
    for p in pts:
        for k, v in (p.get("ledgers") or {}).items():
            if k == "information_energy_residual":
                continue
            flags.setdefault(k, []).append(float(v) >= 0.5)
    return {"n_runs": len(pts), "all_ok": all(every_ledger_ok(p) for p in pts),
            "n_ok": int(sum(every_ledger_ok(p) for p in pts)),
            "ok_fraction_by_ledger": {k: float(np.mean(v)) for k, v in flags.items()},
            "worst_residuals": worst,
            "events_total": int(sum(p.get("n_events", 0) for p in pts)),
            "divisions_total": int(sum(p.get("divisions", 0) for p in pts)),
            "extinctions_total": int(sum(p.get("extinctions", 0) for p in pts))}


def innovation_report(lattice: dict, autonomy: dict, generic: dict, discrimination: dict, ledgers: dict,
                      provenance_audit: dict, meta: dict | None = None) -> TransitionReport:
    n = int(lattice["n_structures"])
    n_full = int(lattice["nodes"][set_label(INNOVATIONS)]["n_persist"])
    example = {}
    for sid, ps in lattice["per_structure"].items():
        if ps["full_set_persists"]:
            example = {"structure": sid, "required": ps["required"]}
            break
    by_class = {}
    for axis, levels in lattice["by_axis"].items():
        for lev, d in levels.items():
            by_class[f"{axis}={lev}"] = d["full_set_persistence"]
    disc = []
    for ko, d in discrimination.items():
        for r, v in d.items():
            if v.get("d") == v.get("d"):
                disc.append({"readout": f"{r} ({ko})", "d": v["d"], "mean_diff": v["mean_diff"], "n": v["n"]})
    disc.sort(key=lambda x: -abs(x["d"]))
    return TransitionReport(
        transition="integrated autonomy: the minimum sufficient innovation set across model structures (og-08 re-run in the integrated world)",
        tier=EvidenceTier.CONCEPTUAL_DEMONSTRATION,
        feasibility=Feasibility(feasible=n_full > 0, n_admissible=n, n_supporting=n_full, example=example,
                                admissibility="a sampled model structure (storage x inheritance x boundary x anchor x transport x maintenance) at a Phase-1 posterior draw, every driver withdrawn to its ocean floor"),
        robustness=Robustness(fraction=float(lattice["full_set_persistence_fraction"]), by_class=by_class,
                              structure_agreement=float(lattice["required_set_agreement"]) if lattice["required_set_agreement"] == lattice["required_set_agreement"] else None,
                              structure_uncertainty=(1.0 - float(lattice["required_set_agreement"])) if lattice["required_set_agreement"] == lattice["required_set_agreement"] else None,
                              n_posterior=n, n_prior=n,
                              binding_observation="the ocean floor of the feed (hypothetical) and the membrane leakiness",
                              note=f"required intersection {lattice['required_intersection']}; union {lattice['required_union']}; generic control persists in {generic['n_persist']}/{generic['n']}"),
        discrimination=Discrimination(alternatives=[f"-{i}" for i in INNOVATIONS], discriminating=disc[:6],
                                      non_discriminating=[x["readout"] for x in disc if abs(x["d"]) < 0.2],
                                      proposed_perturbations=["the ocean substrate floor (H2, organics)", "a tighter boundary class (measured charged-solute permeability)",
                                                              "the heredity precursor demand (attachment thresholds)", "the maintenance law"]),
        gate="minimum-sufficient-innovation-set",
        model_classes=[f"{a}: {', '.join(l)}" for a, l in STRUCTURE_AXES.items()],
        provenance_audit=provenance_audit, numerical_verification=ledgers, meta=dict(meta or {}),
    )


__all__ = ["INNOVATIONS", "INNOVATION_SETS", "STRUCTURE_AXES", "AXIS_LABELS", "set_label", "subset_flags",
           "sample_structures", "structure_kwargs", "run_point", "persists", "every_ledger_ok", "evaluate_structure",
           "evaluate_lattice", "autonomy_summary", "generic_control", "paired_knockouts", "ledger_summary",
           "innovation_report"]
