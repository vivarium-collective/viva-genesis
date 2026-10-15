"""Phase 2 — the electrochemical mechanism map, worked concretely.

Model Upgrade plan, Phase 2 (*electrochemical carbon fixation*). Exit
criterion: a **mechanism map** — over (vent pH × dissolved H2 × mineral
conductivity × Ni/Fe) every point is labelled with the limitation that stops
carbon fixation there (thermodynamic / electrical / catalytic / transport),
and the gate ``failure-mode-attributed`` asks whether the model classes on
the ``carbon_fixation`` face **agree on the label in the favorable region**.

Pipeline (every step is real; nothing is fitted to pass):

1. **Sweep** — :func:`mechanism_map` runs
   :func:`~viva_genesis.composites.electrochemical_interface.electrochemical_carbon_fixation`
   over the four physical axes × the runnable classes (``empirical``,
   ``butler_volmer``; ``microkinetic`` is registered on the face but its
   CatMAP/Cantera backend is pixi-only, so it is recorded as *deferred*, never
   faked) in the open-flow regime, reducing each run to the settled throughput,
   the four loss fractions, the limitation code, the circuit readouts and the
   charge-ledger witnesses.
2. **Attribution** — :func:`attribute_mechanisms` labels every point per class
   from its settled loss fractions, defines each class's *favorable region*
   (throughput ≥ a declared fraction of that class's own maximum — the two
   classes live on different absolute scales: the empirical tick is abstract,
   the Butler-Volmer second is physical), and computes label agreement over
   all points, over the region both classes call favorable, the per-label
   confusion matrix, the structure agreement on favorability itself and the
   ledger summary.
3. **Report** — a :class:`~viva_genesis.uq.report.TransitionReport` whose
   Robustness.structure_agreement *is* the gate metric, with the paired class
   differences of the loss fractions as the Discrimination, the provenance
   audit of ``electrochemical_interface`` and the ledger verification.

Honesty: the favorable-region label agreement is reported whatever it is. If
the classes disagree, ``decision_discipline`` flags the mechanism attribution
as structure-sensitive — that is the Phase-2 finding, not a failure to hide.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Mapping, Sequence

import numpy as np

from ..electrochemistry.butler_volmer import (LIMITATION_CODES, LIMITATION_NAMES, default_cell_kwargs,
                                              polarization_curve, solve_cell)
from ..provenance import load_package
from ..sweep import SweepResult, sweep_grid
from .ensemble import paired_class_difference, structure_agreement
from .report import Discrimination, EvidenceTier, Feasibility, Robustness, TransitionReport

CLASS_AXIS = "model_carbon_fixation"
DEFAULT_CLASSES = ("empirical", "butler_volmer")
DEFERRED_CLASSES = {"microkinetic": "CatMAP / Cantera backend is conda-only; runs under pixi (see NEXT_STEPS.md)"}
LABELS = ("thermodynamic", "electrical", "catalytic", "transport")

DEFAULT_AXES = {
    "ph_vent": [7.0, 8.0, 9.0, 10.0, 11.0],
    "h2": [float(v) for v in np.geomspace(1.0e-6, 2.0e-2, 5)],
    "conductivity": [float(v) for v in np.geomspace(1.0e-9, 1.0e-1, 5)],
    "ni_fraction": [0.0, 0.25, 0.75],
}
ALTAIR_WINDOW = (1.0e-5, 1.0e-2)   # A/m^2 — vg-data electrochemical_interface.observations.cell_current_density


# --------------------------------------------------------------------------- #
# 1. the sweep
# --------------------------------------------------------------------------- #
def mechanism_map(*, classes: Sequence[str] = DEFAULT_CLASSES, axes: Mapping[str, Sequence] | None = None,
                  n_steps: int = 40, nx: int = 20, dilution_rate: float = 2.0, n_jobs: int | str = 1,
                  fixed: Mapping[str, float] | None = None) -> SweepResult:
    """Sweep the Phase-2 composite over the four physical axes × the runnable classes."""
    from ..composites.electrochemical_interface import PHASE2_REDUCERS, electrochemical_carbon_fixation
    axes = dict(axes or DEFAULT_AXES)
    return sweep_grid(
        electrochemical_carbon_fixation,
        axes={CLASS_AXIS: list(classes), **axes},
        reduce=dict(PHASE2_REDUCERS),
        fixed={"dilution_rate": float(dilution_rate), "nx": int(nx), **dict(fixed or {})},
        n_steps=int(n_steps), n_jobs=n_jobs, tolerant=True,
    )


# --------------------------------------------------------------------------- #
# 2. attribution
# --------------------------------------------------------------------------- #
def _labels_from_codes(codes: np.ndarray) -> np.ndarray:
    out = np.full(codes.shape, "unresolved", dtype=object)
    finite = np.isfinite(codes)
    for name, code in LIMITATION_CODES.items():
        out[finite & (np.rint(codes) == code)] = name
    return out


def attribute_mechanisms(result: SweepResult, *, favorable_fraction: float = 0.1,
                         headline_class: str = "butler_volmer") -> dict:
    """Label every point per class and measure cross-class agreement (the gate metric)."""
    classes = [str(c) for c in result.axes[CLASS_AXIS]]
    per_class, labels, favorable, ok_masks = {}, {}, {}, {}
    for c in classes:
        sub = result.slice_along(CLASS_AXIS, c)
        thr = sub.surfaces["sustained_throughput"]
        codes = sub.surfaces["limitation_code"]
        ok = np.isfinite(thr) & np.isfinite(codes)
        lab = _labels_from_codes(codes)
        tmax = float(np.nanmax(thr)) if ok.any() else float("nan")
        fav = ok & (thr >= favorable_fraction * tmax) if ok.any() else np.zeros(thr.shape, bool)
        labels[c], favorable[c], ok_masks[c] = lab, fav, ok
        cur = sub.surfaces.get("current_density")
        in_window = (np.isfinite(cur) & (cur >= ALTAIR_WINDOW[0]) & (cur <= ALTAIR_WINDOW[1])) if cur is not None else None
        per_class[c] = {
            "n_points": int(thr.size), "n_ok": int(ok.sum()), "n_failed": int((~ok).sum()),
            "label_coverage": float(ok.mean()),
            "label_counts": {name: int((lab[ok] == name).sum()) for name in LABELS},
            "label_counts_favorable": {name: int((lab[fav] == name).sum()) for name in LABELS},
            "throughput_max": tmax,
            "throughput_min_ok": float(np.nanmin(thr[ok])) if ok.any() else float("nan"),
            "n_favorable": int(fav.sum()), "favorable_fraction_of_grid": float(fav.mean()),
            "favorable_threshold": favorable_fraction * tmax if ok.any() else float("nan"),
            "ledger": {
                "all_ok": bool(ok.any()) and bool(np.all(sub.surfaces["charge_ledger_ok"][ok] >= 1.0)),
                "max_charge_residual": float(np.nanmax(sub.surfaces["charge_residual_max"][ok])) if ok.any() else float("nan"),
                "max_faradaic_efficiency": float(np.nanmax(sub.surfaces["faradaic_efficiency_max"][ok])) if ok.any() else float("nan"),
                "max_iv_residual": float(np.nanmax(sub.surfaces["iv_residual_max"][ok])) if ok.any() else float("nan"),
            },
            "current_in_altair_window_fraction": (float(in_window[ok].mean()) if (in_window is not None and ok.any()) else None),
        }
    cross = {}
    if len(classes) >= 2:
        a, b = classes[0], classes[1]
        if headline_class in classes and headline_class != b:
            a, b = headline_class, [c for c in classes if c != headline_class][0]
        both_ok = ok_masks[a] & ok_masks[b]
        agree = (labels[a] == labels[b]) & both_ok
        fav_both = favorable[a] & favorable[b] & both_ok
        fav_head = favorable[a] & both_ok
        confusion = {la: {lb: int(((labels[a] == la) & (labels[b] == lb) & both_ok).sum()) for lb in LABELS} for la in LABELS}
        marginal = {}
        for ax in [x for x in result.axis_order if x != CLASS_AXIS]:
            idx = [x for x in result.axis_order if x != CLASS_AXIS].index(ax)
            vals = []
            for i in range(len(result.axes[ax])):
                taker = [slice(None)] * agree.ndim
                taker[idx] = i
                m = both_ok[tuple(taker)]
                vals.append(float(agree[tuple(taker)][m].mean()) if m.any() else float("nan"))
            marginal[ax] = {"values": [float(v) if not isinstance(v, str) else v for v in result.axes[ax]], "agreement": vals}
        cross = {
            "classes": [a, b],
            "n_both_ok": int(both_ok.sum()),
            "label_agreement_all": float(agree[both_ok].mean()) if both_ok.any() else float("nan"),
            "n_favorable_both": int(fav_both.sum()),
            "label_agreement_favorable": float(agree[fav_both].mean()) if fav_both.any() else float("nan"),
            "n_favorable_headline": int(fav_head.sum()),
            "label_agreement_favorable_headline": float(agree[fav_head].mean()) if fav_head.any() else float("nan"),
            "favorability_structure_agreement": structure_agreement({a: favorable[a], b: favorable[b]}),
            "confusion": confusion,
            "agreement_by_axis": marginal,
        }
    return {
        "classes": classes,
        "deferred_classes": dict(DEFERRED_CLASSES),
        "favorable_fraction": favorable_fraction,
        "headline_class": headline_class if headline_class in classes else classes[0],
        "axes": {ax: [float(v) for v in result.axes[ax]] for ax in result.axis_order if ax != CLASS_AXIS},
        "per_class": per_class,
        "cross_class": cross,
        "labels": {c: labels[c].tolist() for c in classes},
        "favorable": {c: favorable[c].astype(int).tolist() for c in classes},
    }


# --------------------------------------------------------------------------- #
# 3. report
# --------------------------------------------------------------------------- #
def _rows_for_class(result: SweepResult, c: str) -> list[dict]:
    sub = result.slice_along(CLASS_AXIS, c)
    flat = {k: np.asarray(v, dtype=float).ravel() for k, v in sub.surfaces.items()}
    n = next(iter(flat.values())).size
    rows = []
    for i in range(n):
        r = {k: float(v[i]) for k, v in flat.items()}
        r["log10_throughput"] = float(np.log10(r["sustained_throughput"])) if r["sustained_throughput"] > 0 else float("nan")
        rows.append(r)
    return rows


def electrochemistry_report(result: SweepResult, attribution: dict | None = None) -> TransitionReport:
    """The Feasibility / Robustness / Discrimination triple for Phase 2."""
    att = attribution or attribute_mechanisms(result)
    head = att["headline_class"]
    pc = att["per_class"][head]
    cross = att.get("cross_class") or {}
    classes = att["classes"]
    pkg = load_package("electrochemical_interface")

    # a supporting parameterization: the headline class's best point
    sub = result.slice_along(CLASS_AXIS, head)
    thr = sub.surfaces["sustained_throughput"]
    example = {}
    if np.isfinite(thr).any():
        idx = np.unravel_index(int(np.nanargmax(thr)), thr.shape)
        example = {"point": {ax: float(result.axes[ax][i]) for ax, i in zip(sub.axis_order, idx)},
                   "readouts": {k: float(v[idx]) for k, v in sub.surfaces.items()},
                   "label": att["labels"][head][idx[0]][idx[1]][idx[2]][idx[3]] if len(idx) == 4 else None}
    feas = Feasibility(
        feasible=bool(pc["n_favorable"] > 0),
        n_admissible=int(cross.get("n_both_ok", pc["n_ok"])),
        n_supporting=int(pc["n_favorable"]),
        example=example,
        admissibility=("grid points where every runnable class ran to completion with its charge ledger closed; "
                       "favorable = settled throughput >= "
                       f"{att['favorable_fraction']:.0%} of the class's own maximum (open flow, dilution as swept)"),
    )
    agree_fav = cross.get("label_agreement_favorable")
    rob = Robustness(
        fraction=float(pc["favorable_fraction_of_grid"]),
        by_class={c: float(att["per_class"][c]["favorable_fraction_of_grid"]) for c in classes},
        structure_agreement=(float(agree_fav) if agree_fav is not None and np.isfinite(agree_fav) else None),
        structure_uncertainty=(float(1.0 - agree_fav) if agree_fav is not None and np.isfinite(agree_fav) else None),
        n_posterior=int(cross.get("n_favorable_both", pc["n_favorable"])), n_prior=int(pc["n_points"]),
        binding_observation="Altair-2025 current window (vg-data electrochemical_interface)",
        note=("fraction of the swept grid (uniform in log over the vg-data priors, NOT a conditioned posterior) "
              "that is favorable; structure_agreement = fraction of the region both classes call favorable on "
              "which they agree about the limitation label (the failure-mode-attributed gate metric)"),
    )
    disc_rows = []
    if len(classes) >= 2:
        a, b = cross["classes"]
        pcd = paired_class_difference({a: _rows_for_class(result, a), b: _rows_for_class(result, b)},
                                      ["loss_thermodynamic", "loss_electrical", "loss_catalytic", "loss_transport",
                                       "gradient_efficiency", "log10_throughput"])
        disc_rows = sorted([{"readout": k, **v} for k, v in pcd.items() if np.isfinite(v.get("d", np.nan))],
                           key=lambda r: -abs(r["d"]))
    disc = Discrimination(
        alternatives=[c for c in classes if c != head] + list(DEFERRED_CLASSES),
        discriminating=[r for r in disc_rows if abs(r["d"]) >= 0.5],
        non_discriminating=[r["readout"] for r in disc_rows if abs(r["d"]) < 0.5],
        proposed_perturbations=[
            "measure the current-voltage curve of the wall (polarization): the Butler-Volmer class predicts "
            "an activation-dominated cell whose current scales with the exchange current, the empirical class "
            "a pmf-saturating drive; the two differ in how throughput responds to a 10x catalyst change",
            "vary the wall conductivity across 1e-7..1e-5 S/m: both classes predict the electrical collapse "
            "there, so the location of the knee calibrates the layer thickness / conductivity product",
            "run the microkinetic class under pixi (CatMAP / Cantera) to test whether site coverage and "
            "passivation move the catalytic label toward transport at high current",
        ],
        note="paired standardised difference d between model classes on identical grid points",
    )
    led = pc["ledger"]
    nv = {"ok": bool(all(att["per_class"][c]["ledger"]["all_ok"] for c in classes)),
          "charge_residual": led["max_charge_residual"], "iv_residual": led["max_iv_residual"],
          "faradaic_efficiency_max": led["max_faradaic_efficiency"],
          "n_failed_points": int(sum(att["per_class"][c]["n_failed"] for c in classes))}
    return TransitionReport(
        transition="Phase 2 — explicit electrochemistry attributes the limitation of carbon fixation at the mineral interface",
        tier=EvidenceTier.MECHANISTIC_PREDICTION,
        feasibility=feas, robustness=rob, discrimination=disc,
        gate="failure-mode-attributed",
        model_classes=list(classes) + [f"{k} (deferred)" for k in DEFERRED_CLASSES],
        provenance_audit=pkg.audit(),
        numerical_verification=nv,
        sensitivity={"agreement_by_axis": cross.get("agreement_by_axis", {})},
        meta={"n_points_per_class": pc["n_points"], "n_steps": result.meta.get("n_steps"),
              "fixed": result.meta.get("fixed"), "headline_class": head,
              "package": f"{pkg.name} v{pkg.version}", "altair_window_A_m2": list(ALTAIR_WINDOW),
              "favorable_fraction": att["favorable_fraction"]},
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


def mechanism_map_to_dict(result: SweepResult, attribution: dict) -> dict:
    classes = [str(c) for c in result.axes[CLASS_AXIS]]
    phys = [ax for ax in result.axis_order if ax != CLASS_AXIS]
    return {
        "axis_order": phys,
        "axes": {ax: [float(v) for v in result.axes[ax]] for ax in phys},
        "classes": classes,
        "deferred_classes": dict(DEFERRED_CLASSES),
        "surfaces": {c: {k: result.slice_along(CLASS_AXIS, c).surfaces[k].tolist() for k in result.surfaces}
                     for c in classes},
        "labels": attribution["labels"],
        "favorable": attribution["favorable"],
        "meta": dict(result.meta),
    }


def save_artifacts(result: SweepResult, attribution: dict, report: TransitionReport, artifacts_dir: str | Path,
                   nominal: Mapping[str, float] | None = None) -> dict[str, Path]:
    from .report import decision_discipline
    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    map_path = artifacts_dir / "electrochemistry_mechanism_map.json"
    rep_path = artifacts_dir / "electrochemistry_report.json"
    map_path.write_text(json.dumps(mechanism_map_to_dict(result, attribution), default=_json_default))
    kw = default_cell_kwargs(**dict(nominal or {}))
    out = {"attribution": attribution, "report": report.to_dict(),
           "decision_discipline": decision_discipline(report),
           "nominal_cell": solve_cell(**kw).to_dict(),
           "polarization": polarization_curve(**kw),
           "written_at": time.time()}
    rep_path.write_text(json.dumps(out, indent=1, default=_json_default))
    return {"mechanism_map": map_path, "report": rep_path}


__all__ = ["CLASS_AXIS", "DEFAULT_CLASSES", "DEFERRED_CLASSES", "DEFAULT_AXES", "LABELS", "ALTAIR_WINDOW",
           "mechanism_map", "attribute_mechanisms", "electrochemistry_report", "mechanism_map_to_dict",
           "save_artifacts", "LIMITATION_NAMES"]
