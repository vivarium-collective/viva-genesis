#!/usr/bin/env python
"""Compute + persist the Phase-1 environmental-calibration ensemble (og-cal-vent-environment).

Draws the vg-data ``vent_environment`` prior (LHS), runs every draw through the
real PHREEQC + FiPy ``geochemical_world`` once per spatial-transport model class
(convecting wall vs prescribed uniform upflow), ABC-conditions on the Lost City
observation windows, evaluates og-01's downstream requirements on the posterior,
runs a Morris screening of the prior, and writes:

    artifacts/vent_environment_ensemble.json   (raw draws + outcomes per class + morris)
    artifacts/vent_environment_report.json     (conditioning + Feasibility/Robustness/Discrimination)

Serial on purpose (the PHREEQC extension does not survive a process pool).

    PYTHONPATH=<worktree> python workspace/studies/og-cal-vent-environment/sims/compute_vent_environment_ensemble.py [--draws N] [--steps N] [--nx N] [--seed S] [--no-morris]
"""
from __future__ import annotations

import json
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
    from viva_genesis.uq import environment_calibration as EC

    n_draws = _arg("--draws", 48)
    n_steps = _arg("--steps", 30)
    nx = _arg("--nx", 20)
    seed = _arg("--seed", 0)
    t0 = time.time()

    def log(msg):
        print(msg, flush=True)

    ens = EC.vent_environment_ensemble(n_draws=n_draws, seed=seed, n_steps=n_steps, nx=nx, progress=log)
    if "--no-morris" not in sys.argv:
        ens.morris = EC.morris_screening(r=4, levels=4, seed=seed, n_steps=n_steps, nx=nx, progress=log)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    ens.save(ARTIFACTS / "vent_environment_ensemble.json")

    cond = EC.condition_ensemble(ens)
    rep = EC.vent_calibration_report(ens, cond)
    out = {"conditioning": cond, "report": rep.to_dict(),
           "decision_discipline": __import__("viva_genesis.uq.report", fromlist=["decision_discipline"]).decision_discipline(rep)}
    (ARTIFACTS / "vent_environment_report.json").write_text(json.dumps(out, indent=1, default=EC._json_default))
    log(f"wrote {ARTIFACTS} ({n_draws} draws x {len(ens.classes)} classes, nx={nx}, {time.time() - t0:.0f}s)")
    log(rep.headline())
    for label, pc in cond["per_class"].items():
        log(f"  {label}: consistent {pc['n_consistent']}/{pc['n_runs']} (binding: {pc['binding_observation']}); "
            f"viable|consistent {pc['p_viable_given_consistent']:.2f}; failed points {pc['n_failed']}; "
            f"ledger ok {pc['ledger']['all_ok']}")
    log(f"  cross-class agreement (viable): {cond['cross_class']['viable']['agreement']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
