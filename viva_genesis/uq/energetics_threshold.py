"""Phase 6 — the internalization threshold, worked concretely.

Model Upgrade plan, Phase 6 (*proto-energetics*). Exit criterion: the
**energy-capture efficiency and the threshold at which internalization beats
leakage + maintenance**, per energy-coupling class. The gate
``internalization-pays`` asks, for each class on the ``energy_coupling`` face,
at what coupling activity the individual's net power first exceeds the passive
baseline's at the same membrane and gradient — i.e. where the energetic benefit
of an internal store exceeds its leak and the machinery's maintenance.

Pipeline (every step is real; nothing is fitted to pass):

1. **Sweep** — :func:`internalization_map` runs
   :func:`~viva_genesis.composites.protocell_energetics.protocell_energetics`
   over (class x coupling_activity x membrane permeability x external pmf),
   reducing each run to the settled power budget, autonomy, store state and
   the free-energy-ledger witnesses.
2. **Attribution** — :func:`attribute_thresholds` subtracts the passive class's
   net power point by point (the baseline is activity-independent), marks where
   each class *pays* (advantage > tolerance), finds the threshold activity
   ``a*`` per (permeability, pmf) and the autonomy and capture efficiency there,
   the permeability ceiling below which the class ever pays, the cross-class
   structure agreement on "pays", and the ledger summary per class.
3. **Report** — a :class:`~viva_genesis.uq.report.TransitionReport` whose
   Robustness is the pays-fraction per class with the cross-class agreement,
   the paired class differences of autonomy / net power / store potential as
   the Discrimination, the provenance audit of ``energy_currencies`` and the
   ledger verification.

Honesty: the thresholds are reported whatever they are, including "never pays
on this grid" (a NaN threshold), which is itself the Phase-6 finding for a
class.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from ..provenance import load_package
from ..sweep import SweepResult, sweep_grid
from .ensemble import paired_class_difference, structure_agreement
from .report import Discrimination, EvidenceTier, Feasibility, Robustness, TransitionReport

CLASS_AXIS = "model_energy_coupling"
PASSIVE = "passive_gradient"
ACTIVE_CLASSES = ("h_na_gradient_leaky_membrane", "thioester_acyl_phosphate", "polyphosphate", "fe_redox")
DEFAULT_CLASSES = (PASSIVE,) + ACTIVE_CLASSES
HEADLINE = "thioester_acyl_phosphate"

DEFAULT_AXES = {
    "coupling_activity": [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0],
    "permeability": [float(v) for v in np.geomspace(1.0e-8, 1.0e-4, 9)],
    "electric_potential": [0.216, 0.02],
}
NOMINAL = {"permeability": 1.0e-6, "electric_potential": 0.216}
ADVANTAGE_TOL = 1.0e-21   # W — an advantage below this is rounding, not a benefit
SURFACES = ("net_power", "internal_power", "external_power", "maintenance_power", "leak_power", "autonomy",
            "charge_fraction", "store_potential", "capture_efficiency", "free_energy_residual_max",
            "second_law_margin_min", "dissipation_min", "free_energy_ledger_ok")


# --------------------------------------------------------------------------- #
# 1. the sweep
# --------------------------------------------------------------------------- #
def internalization_map(*, classes: Sequence[str] = DEFAULT_CLASSES, axes: Mapping[str, Sequence] | None = None,
                        n_steps: int = 300, n_jobs: int | str = 1,
                        fixed: Mapping[str, float] | None = None) -> SweepResult:
    """Sweep the Phase-6 composite over (class x activity x permeability x pmf)."""
    from ..composites.protocell_energetics import PHASE6_REDUCERS, protocell_energetics
    axes = dict(axes or DEFAULT_AXES)
    return sweep_grid(
        protocell_energetics,
        axes={CLASS_AXIS: list(classes), **axes},
        reduce=dict(PHASE6_REDUCERS),
        fixed=dict(fixed or {}),
        n_steps=int(n_steps), n_jobs=n_jobs, tolerant=True,
    )


# --------------------------------------------------------------------------- #
# 2. attribution
# --------------------------------------------------------------------------- #
def _nearest(values, target) -> int:
    arr = np.asarray(values, dtype=float)
    pos = arr > 0
    if target > 0 and pos.all():
        return int(np.argmin(np.abs(np.log10(arr) - np.log10(target))))
    return int(np.argmin(np.abs(arr - target)))


def attribute_thresholds(result: SweepResult, *, advantage_tol: float = ADVANTAGE_TOL,
                         nominal: Mapping[str, float] | None = None) -> dict:
    """Per class: where internalization pays against the passive baseline, the
    threshold activity, the autonomy there, the permeability ceiling, and the
    ledger summary; across classes: structure agreement on 'pays'."""
    nominal = dict(nominal or NOMINAL)
    classes = [str(c) for c in result.axes[CLASS_AXIS]]
    phys = [ax for ax in result.axis_order if ax != CLASS_AXIS]
    if PASSIVE not in classes:
        raise ValueError(f"the sweep must include the {PASSIVE!r} baseline; have {classes}")
    ia, ip, iv = (phys.index(k) for k in ("coupling_activity", "permeability", "electric_potential"))
    acts = np.asarray(result.axes["coupling_activity"], dtype=float)
    perms = np.asarray(result.axes["permeability"], dtype=float)
    pmfs = np.asarray(result.axes["electric_potential"], dtype=float)
    base = result.slice_along(CLASS_AXIS, PASSIVE)
    # the passive baseline is activity-independent: take its activity-mean (they are identical)
    base_net = np.nanmean(base.surfaces["net_power"], axis=ia)
    base_ok = np.isfinite(base.surfaces["net_power"]).all(axis=ia)
    i_p, i_v = _nearest(perms, nominal["permeability"]), _nearest(pmfs, nominal["electric_potential"])

    per_class, pays_masks = {}, {}
    for c in classes:
        sub = result.slice_along(CLASS_AXIS, c)
        net = sub.surfaces["net_power"]
        ok = np.isfinite(net)
        adv = net - np.expand_dims(base_net, ia)
        pays = ok & np.expand_dims(base_ok, ia) & (adv > advantage_tol)
        if c == PASSIVE:
            pays = np.zeros_like(pays)
        pays_masks[c] = pays
        # threshold activity per (permeability, pmf): the smallest activity that pays
        shape_pv = tuple(n for i, n in enumerate(net.shape) if i != ia)
        thr = np.full(shape_pv, np.nan)
        auto_thr = np.full(shape_pv, np.nan)
        eff_thr = np.full(shape_pv, np.nan)
        best_a = np.full(shape_pv, np.nan)
        best_adv = np.full(shape_pv, np.nan)
        for j in range(len(perms)):
            for k in range(len(pmfs)):
                taker = [slice(None)] * net.ndim
                taker[ip], taker[iv] = j, k
                col = pays[tuple(taker)]
                advc = adv[tuple(taker)]
                jk = (j, k) if ip < iv else (k, j)
                if col.any():
                    i0 = int(np.argmax(col))
                    thr[jk] = acts[i0]
                    t2 = list(taker)
                    t2[ia] = i0
                    auto_thr[jk] = float(sub.surfaces["autonomy"][tuple(t2)])
                    eff_thr[jk] = float(sub.surfaces["capture_efficiency"][tuple(t2)])
                if np.isfinite(advc).any():
                    ib = int(np.nanargmax(advc))
                    best_a[jk] = acts[ib]
                    best_adv[jk] = float(advc[ib])
        # permeability ceiling per pmf: the largest permeability at which any activity pays
        ceiling = {}
        for k in range(len(pmfs)):
            col = [thr[(j, k) if ip < iv else (k, j)] for j in range(len(perms))]
            paying = [perms[j] for j in range(len(perms)) if np.isfinite(col[j])]
            ceiling[f"{pmfs[k]:.3g}"] = float(max(paying)) if paying else None
        nom = (i_p, i_v) if ip < iv else (i_v, i_p)
        taker = [slice(None)] * net.ndim
        taker[ip], taker[iv] = i_p, i_v
        per_class[c] = {
            "n_points": int(net.size), "n_ok": int(ok.sum()), "n_failed": int((~ok).sum()),
            "pays_fraction": float(pays[ok].mean()) if ok.any() else float("nan"),
            "pays_fraction_active": (float(pays[ok & (np.expand_dims(acts, [i for i in range(net.ndim) if i != ia]) > 0)].mean())
                                     if ok.any() else float("nan")),
            "threshold_activity": thr.tolist(), "autonomy_at_threshold": auto_thr.tolist(),
            "capture_efficiency_at_threshold": eff_thr.tolist(),
            "best_activity": best_a.tolist(), "best_advantage": best_adv.tolist(),
            "permeability_ceiling_by_pmf": ceiling,
            "nominal": {
                "permeability": float(perms[i_p]), "electric_potential": float(pmfs[i_v]),
                "threshold_activity": (float(thr[nom]) if np.isfinite(thr[nom]) else None),
                "autonomy_at_threshold": (float(auto_thr[nom]) if np.isfinite(auto_thr[nom]) else None),
                "capture_efficiency_at_threshold": (float(eff_thr[nom]) if np.isfinite(eff_thr[nom]) else None),
                "best_activity": (float(best_a[nom]) if np.isfinite(best_a[nom]) else None),
                "best_advantage_W": (float(best_adv[nom]) if np.isfinite(best_adv[nom]) else None),
                "passive_net_power_W": float(base_net[nom]),
                "autonomy_by_activity": [float(v) for v in sub.surfaces["autonomy"][tuple(taker)]],
                "net_power_by_activity": [float(v) for v in net[tuple(taker)]],
                "internal_power_by_activity": [float(v) for v in sub.surfaces["internal_power"][tuple(taker)]],
                "store_potential_by_activity": [float(v) for v in sub.surfaces["store_potential"][tuple(taker)]],
                "charge_fraction_by_activity": [float(v) for v in sub.surfaces["charge_fraction"][tuple(taker)]],
            },
            "ledger": {
                "all_ok": bool(ok.any()) and bool(np.all(sub.surfaces["free_energy_ledger_ok"][ok] >= 1.0)),
                "max_free_energy_residual": float(np.nanmax(sub.surfaces["free_energy_residual_max"][ok])) if ok.any() else float("nan"),
                "min_second_law_margin": float(np.nanmin(sub.surfaces["second_law_margin_min"][ok])) if ok.any() else float("nan"),
                "min_dissipation": float(np.nanmin(sub.surfaces["dissipation_min"][ok])) if ok.any() else float("nan"),
                "max_capture_efficiency": float(np.nanmax(sub.surfaces["capture_efficiency"][ok])) if ok.any() else float("nan"),
            },
            "max_autonomy": float(np.nanmax(sub.surfaces["autonomy"])) if ok.any() else float("nan"),
        }
    active = [c for c in classes if c != PASSIVE]
    sa = structure_agreement({c: pays_masks[c] for c in active}) if active else {}
    pairwise = {}
    for i, a in enumerate(active):
        for b in active[i + 1:]:
            pairwise[f"{a}|{b}"] = structure_agreement({a: pays_masks[a], b: pays_masks[b]})["agreement"]
    return {
        "classes": classes, "active_classes": active, "headline_class": HEADLINE if HEADLINE in classes else active[0],
        "advantage_tol_W": advantage_tol,
        "axes": {ax: [float(v) for v in result.axes[ax]] for ax in phys}, "axis_order": phys,
        "nominal": {"permeability": float(perms[i_p]), "electric_potential": float(pmfs[i_v])},
        "passive_net_power": base_net.tolist(),
        "per_class": per_class,
        "cross_class": {"structure_agreement_pays": sa, "pairwise_agreement": pairwise,
                        "n_classes_paying_at_nominal": int(sum(1 for c in active
                                                               if per_class[c]["nominal"]["threshold_activity"] is not None))},
        "pays": {c: pays_masks[c].astype(int).tolist() for c in classes},
    }


# --------------------------------------------------------------------------- #
# 3. report
# --------------------------------------------------------------------------- #
def _rows_for_class(result: SweepResult, c: str) -> list[dict]:
    sub = result.slice_along(CLASS_AXIS, c)
    flat = {k: np.asarray(v, dtype=float).ravel() for k, v in sub.surfaces.items()}
    n = next(iter(flat.values())).size
    return [{k: float(v[i]) for k, v in flat.items()} for i in range(n)]


def energetics_report(result: SweepResult, attribution: dict | None = None) -> TransitionReport:
    """The Feasibility / Robustness / Discrimination triple for Phase 6."""
    att = attribution or attribute_thresholds(result)
    head = att["headline_class"]
    pc = att["per_class"][head]
    classes, active = att["classes"], att["active_classes"]
    pkg = load_package("energy_currencies")
    nom = pc["nominal"]
    example = {}
    if nom["threshold_activity"] is not None:
        example = {"point": {"model_energy_coupling": head, "coupling_activity": nom["threshold_activity"],
                             "permeability": nom["permeability"], "electric_potential": nom["electric_potential"]},
                   "readouts": {"autonomy": nom["autonomy_at_threshold"],
                                "capture_efficiency": nom["capture_efficiency_at_threshold"],
                                "passive_net_power_W": nom["passive_net_power_W"]}}
    n_sup = int(sum(att["per_class"][c]["pays_fraction"] * att["per_class"][c]["n_ok"] for c in active))
    feas = Feasibility(
        feasible=bool(any(att["per_class"][c]["pays_fraction"] > 0 for c in active)),
        n_admissible=int(sum(att["per_class"][c]["n_ok"] for c in active)),
        n_supporting=n_sup, example=example,
        admissibility=("grid points (activity x permeability x pmf) where the class and the passive baseline ran with "
                       "the free-energy ledger closed; 'pays' = settled net power exceeds the passive baseline's at the "
                       f"same membrane and gradient by > {att['advantage_tol_W']:.0e} W"),
    )
    sa = att["cross_class"]["structure_agreement_pays"]
    rob = Robustness(
        fraction=float(pc["pays_fraction"]),
        by_class={c: float(att["per_class"][c]["pays_fraction"]) for c in active},
        structure_agreement=(float(sa["agreement"]) if sa else None),
        structure_uncertainty=(float(sa["structure_uncertainty"]) if sa else None),
        n_posterior=n_sup, n_prior=int(pc["n_points"]),
        binding_observation="Lost City vent-ocean pH gradient (vg-data energy_currencies; external_pmf calibrated to the Phase-1 posterior)",
        note=("fraction of the swept grid (uniform in activity, log in permeability, two gradient states; NOT a conditioned "
              "posterior) where internalization pays; structure_agreement = fraction of the grid on which every active class "
              "gives the same pays / does-not-pay answer"),
    )
    disc_rows = []
    others = [c for c in active if c != head]
    if others:
        pcd = paired_class_difference({head: _rows_for_class(result, head), others[0]: _rows_for_class(result, others[0])},
                                      ["autonomy", "net_power", "internal_power", "store_potential", "charge_fraction",
                                       "capture_efficiency", "leak_power"])
        disc_rows = sorted([{"readout": k, **v} for k, v in pcd.items() if np.isfinite(v.get("d", np.nan))],
                           key=lambda r: -abs(r["d"]))
    disc = Discrimination(
        alternatives=others,
        discriminating=[r for r in disc_rows if abs(r["d"]) >= 0.5],
        non_discriminating=[r["readout"] for r in disc_rows if abs(r["d"]) < 0.5],
        proposed_perturbations=[
            "tighten the membrane (lower P_H by 100x, e.g. mixed amphiphiles + divalent cations): the ion-gradient class "
            "predicts its store potential rises to the load and internalization starts to pay, the chemical carriers "
            "barely change — the leak law separates them",
            "lower the load (a 20 kJ/mol step): the polyphosphate class predicts a threshold appears, the thioester "
            "class predicts a lower threshold activity",
            "collapse the external gradient (og-05): every active class predicts autonomy -> 1 and the passive baseline "
            "falls to -maintenance; the surviving net power ranks the classes by their leak-independent store",
        ],
        note="paired standardised difference d between model classes on identical grid points",
    )
    led = pc["ledger"]
    nv = {"ok": bool(all(att["per_class"][c]["ledger"]["all_ok"] for c in classes)),
          "free_energy_residual": led["max_free_energy_residual"],
          "second_law_margin_min": led["min_second_law_margin"], "dissipation_min": led["min_dissipation"],
          "capture_efficiency_max": max(att["per_class"][c]["ledger"]["max_capture_efficiency"] for c in classes),
          "n_failed_points": int(sum(att["per_class"][c]["n_failed"] for c in classes))}
    return TransitionReport(
        transition="Phase 6 — internalizing the energy budget: where an internal store beats leakage + maintenance, per coupling class",
        tier=EvidenceTier.CONCEPTUAL_DEMONSTRATION,
        feasibility=feas, robustness=rob, discrimination=disc,
        gate="internalization-pays", model_classes=list(classes),
        provenance_audit=pkg.audit(), numerical_verification=nv,
        sensitivity={"permeability_ceiling_by_pmf": {c: att["per_class"][c]["permeability_ceiling_by_pmf"] for c in active}},
        meta={"n_points_per_class": pc["n_points"], "n_steps": result.meta.get("n_steps"), "fixed": result.meta.get("fixed"),
              "headline_class": head, "package": f"{pkg.name} v{pkg.version}", "nominal": att["nominal"],
              "thresholds_at_nominal": {c: att["per_class"][c]["nominal"]["threshold_activity"] for c in active},
              "autonomy_at_threshold": {c: att["per_class"][c]["nominal"]["autonomy_at_threshold"] for c in active}},
    )


# --------------------------------------------------------------------------- #
# artifacts
# --------------------------------------------------------------------------- #
def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, float) and not np.isfinite(o):
        return None
    raise TypeError(f"not JSON serialisable: {type(o)}")


def threshold_map_to_dict(result: SweepResult, attribution: dict) -> dict:
    classes = [str(c) for c in result.axes[CLASS_AXIS]]
    phys = [ax for ax in result.axis_order if ax != CLASS_AXIS]
    return {
        "axis_order": phys, "axes": {ax: [float(v) for v in result.axes[ax]] for ax in phys},
        "classes": classes,
        "surfaces": {c: {k: result.slice_along(CLASS_AXIS, c).surfaces[k].tolist() for k in SURFACES if k in result.surfaces}
                     for c in classes},
        "passive_net_power": attribution["passive_net_power"],
        "pays": attribution["pays"],
        "thresholds": {c: attribution["per_class"][c]["threshold_activity"] for c in classes},
        "meta": dict(result.meta),
    }


def headline(attribution: dict) -> str:
    bits = []
    for c in attribution["active_classes"]:
        n = attribution["per_class"][c]["nominal"]
        if n["threshold_activity"] is None:
            pmf_key = f"{n['electric_potential']:.3g}"
            ceiling = attribution["per_class"][c]["permeability_ceiling_by_pmf"].get(pmf_key)
            bits.append(f"{c}: never pays at the nominal membrane (ceiling {ceiling} m/s)")
        else:
            bits.append(f"{c}: pays from activity {n['threshold_activity']:.2f} (autonomy {n['autonomy_at_threshold']:.2f}, "
                        f"best +{n['best_advantage_W']:.1e} W at {n['best_activity']:.2f})")
    sa = attribution["cross_class"]["structure_agreement_pays"]
    return ("; ".join(bits) + (f"; cross-class agreement on 'pays' {sa['agreement']:.2f}" if sa else ""))


def save_artifacts(result: SweepResult, attribution: dict, report: TransitionReport, artifacts_dir: str | Path,
                   trajectories: dict | None = None) -> dict[str, Path]:
    from .report import decision_discipline
    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    map_path = artifacts_dir / "internalization_threshold_map.json"
    rep_path = artifacts_dir / "internalization_threshold_report.json"
    map_path.write_text(json.dumps(threshold_map_to_dict(result, attribution), default=_json_default))
    out = {"attribution": attribution, "report": report.to_dict(),
           "decision_discipline": decision_discipline(report),
           "headline": headline(attribution), "trajectories": trajectories or {}, "written_at": time.time()}
    rep_path.write_text(json.dumps(out, indent=1, default=_json_default))
    return {"threshold_map": map_path, "report": rep_path}


def budget_trajectories(*, classes: Sequence[str] = DEFAULT_CLASSES, activities: Sequence[float] = (0.3, 1.0),
                        n_steps: int = 300, every: int = 5, **fixed) -> dict:
    """Per class and activity at the nominal membrane: the power-budget time
    series (external / internal / maintenance / leak / net, store, autonomy)
    for the Mechanism view — real runs of the same composite."""
    from process_bigraph import Composite, gather_emitter_results
    from ..composites.protocell_energetics import protocell_energetics
    from ..core import build_core
    keys = ("external_power", "internal_power", "maintenance_power", "leak_power", "net_power", "autonomy",
            "energy_charge_fraction", "store_potential", "energy_stored", "free_energy_residual", "second_law_margin",
            "electric_potential", "global_time")
    core = build_core()
    out = {"classes": list(classes), "activities": [float(a) for a in activities], "fixed": dict(fixed), "series": {}}
    for c in classes:
        out["series"][c] = {}
        for a in activities:
            sim = Composite({"state": protocell_energetics(core, model_energy_coupling=c, coupling_activity=float(a), **fixed)}, core=core)
            sim.run(float(n_steps))
            rows = gather_emitter_results(sim)[("emitter",)]
            sel = rows[::max(int(every), 1)]
            out["series"][c][f"{a:g}"] = {k: [float(r.get(k, float("nan"))) for r in sel] for k in keys}
    return out


__all__ = ["CLASS_AXIS", "PASSIVE", "ACTIVE_CLASSES", "DEFAULT_CLASSES", "HEADLINE", "DEFAULT_AXES", "NOMINAL",
           "ADVANTAGE_TOL", "internalization_map", "attribute_thresholds", "energetics_report",
           "threshold_map_to_dict", "headline", "save_artifacts", "budget_trajectories"]
