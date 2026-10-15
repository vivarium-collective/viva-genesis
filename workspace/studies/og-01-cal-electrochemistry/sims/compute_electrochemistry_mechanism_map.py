#!/usr/bin/env python
"""Compute + persist the Phase-2 electrochemical mechanism map (og-01-cal-electrochemistry).

Sweeps the real ``electrochemical_carbon_fixation`` composite over
(vent pH × dissolved H2 × mineral conductivity × Ni fraction) for every runnable
class on the ``carbon_fixation`` face (``empirical``: og-01's FiPy Nernst-Planck
+ eQuilibrator + lab-calibrated kinetics with the circuit-derived gradient
efficiency; ``butler_volmer``: the Nernst + Butler-Volmer galvanic cell;
``microkinetic`` is recorded as deferred — its CatMAP/Cantera backend is
pixi-only), labels every point with its dominant limitation, measures the
cross-class label agreement (the ``failure-mode-attributed`` gate) and writes:

    artifacts/electrochemistry_mechanism_map.json   (axes + surfaces + labels per class)
    artifacts/electrochemistry_report.json          (attribution, Feasibility/Robustness/Discrimination,
                                                     decision discipline, nominal cell + polarization curve)

    PYTHONPATH=<worktree> python workspace/studies/og-01-cal-electrochemistry/sims/compute_electrochemistry_mechanism_map.py [--jobs N] [--steps N] [--nx N] [--coarse]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"


def _arg(flag: str, default):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return type(default)(sys.argv[i + 1])
    return default


def main() -> int:
    import numpy as np
    from viva_genesis.uq import electrochemistry_calibration as EC

    n_jobs = _arg("--jobs", 6)
    n_steps = _arg("--steps", 40)
    nx = _arg("--nx", 20)
    axes = dict(EC.DEFAULT_AXES)
    if "--coarse" in sys.argv:
        axes = {"ph_vent": [7.0, 9.5, 11.0], "h2": [float(v) for v in np.geomspace(1e-6, 2e-2, 3)],
                "conductivity": [1e-9, 1e-5, 1e-1], "ni_fraction": [0.0, 0.75]}
    t0 = time.time()
    res = EC.mechanism_map(classes=EC.DEFAULT_CLASSES, axes=axes, n_steps=n_steps, nx=nx, n_jobs=n_jobs)
    print(f"sweep done: shape {res.shape} ({res.meta['n_points']} runs) in {time.time() - t0:.0f}s", flush=True)
    att = EC.attribute_mechanisms(res)
    rep = EC.electrochemistry_report(res, att)
    paths = EC.save_artifacts(res, att, rep, ARTIFACTS)
    from viva_genesis.uq.report import decision_discipline
    print(f"wrote {paths['mechanism_map']} and {paths['report']} ({time.time() - t0:.0f}s)")
    print(rep.headline())
    for c, pc in att["per_class"].items():
        print(f"  {c}: coverage {pc['label_coverage']:.2f}; labels {pc['label_counts']}; favorable {pc['n_favorable']}/{pc['n_points']} "
              f"(labels there {pc['label_counts_favorable']}); ledger ok {pc['ledger']['all_ok']} "
              f"(charge res {pc['ledger']['max_charge_residual']:.1e}, FE max {pc['ledger']['max_faradaic_efficiency']:.3f}, "
              f"iv res {pc['ledger']['max_iv_residual']:.1e}); Altair window {pc['current_in_altair_window_fraction']}")
    cross = att["cross_class"]
    print(f"  label agreement: all {cross['label_agreement_all']:.2f} ({cross['n_both_ok']} pts); "
          f"favorable-both {cross['label_agreement_favorable']} ({cross['n_favorable_both']} pts); "
          f"favorable-headline {cross['label_agreement_favorable_headline']} ({cross['n_favorable_headline']} pts)")
    print(f"  favorability structure agreement: {cross['favorability_structure_agreement']['agreement']:.2f}")
    print(f"  confusion (rows {cross['classes'][0]}, cols {cross['classes'][1]}): {cross['confusion']}")
    print(f"  decision discipline: {decision_discipline(rep)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
