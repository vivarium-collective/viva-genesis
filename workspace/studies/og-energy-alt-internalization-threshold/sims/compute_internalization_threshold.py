#!/usr/bin/env python
"""Compute + persist the Phase-6 internalization-threshold artifacts (og-energy-alt-internalization-threshold).

Sweeps ``protocell_energetics`` over the five ``energy_coupling`` classes x
coupling activity (0 .. 1) x membrane H+ permeability (1e-8 .. 1e-4 m/s) x the
external gradient (the Phase-1-calibrated 0.216 V and the collapsed 0.02 V
floor of og-05), 300 ticks of 10 s each, with the FreeEnergyLedgerProcess on
every run; attributes where each class PAYS against the passive baseline
(threshold activity a*, autonomy there, permeability ceiling, cross-class
agreement, ledger summary); writes the TransitionReport; records the
power-budget trajectories at the nominal membrane for the Mechanism view; and
renders the two declared figures to ``viz/``. Writes

    artifacts/internalization_threshold_map.json
    artifacts/internalization_threshold_report.json
    viz/internalization-threshold-map.html
    viz/protocell-energy-budget.html

    PYTHONPATH=<worktree> python workspace/studies/og-energy-alt-internalization-threshold/sims/compute_internalization_threshold.py [--steps 300] [--jobs 6]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"
VIZ = STUDY_DIR / "viz"


def _arg(flag: str, default):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return type(default)(sys.argv[i + 1])
    return default


def main() -> int:
    from viva_genesis.uq import energetics_threshold as ET
    from viva_genesis.viz_energetics import energy_budget_figure, threshold_map_figure

    n_steps = _arg("--steps", 300)
    n_jobs = _arg("--jobs", 6)
    t0 = time.time()
    print(f"== sweep: {len(ET.DEFAULT_CLASSES)} classes x {len(ET.DEFAULT_AXES['coupling_activity'])} activities x "
          f"{len(ET.DEFAULT_AXES['permeability'])} permeabilities x {len(ET.DEFAULT_AXES['electric_potential'])} gradients, "
          f"{n_steps} ticks, {n_jobs} workers", flush=True)
    res = ET.internalization_map(n_steps=n_steps, n_jobs=n_jobs)
    print(f"   {res.meta['n_points']} points in {time.time() - t0:.0f}s", flush=True)
    att = ET.attribute_thresholds(res)
    for c in att["classes"]:
        pc = att["per_class"][c]
        print(f"   {c:30s} pays {pc['pays_fraction']:.2f} of grid; nominal a* {pc['nominal']['threshold_activity']}; "
              f"autonomy@a* {pc['nominal']['autonomy_at_threshold']}; ceiling {pc['permeability_ceiling_by_pmf']}; "
              f"ledger ok {pc['ledger']['all_ok']} (res {pc['ledger']['max_free_energy_residual']:.1e})", flush=True)
    rep = ET.energetics_report(res, att)
    print("   " + rep.headline(), flush=True)
    traj = ET.budget_trajectories(n_steps=n_steps, every=3)
    paths = ET.save_artifacts(res, att, rep, ARTIFACTS, trajectories=traj)
    art = json.loads(paths["report"].read_text())
    mmap = json.loads(paths["threshold_map"].read_text())
    VIZ.mkdir(parents=True, exist_ok=True)
    (VIZ / "internalization-threshold-map.html").write_text(
        threshold_map_figure(mmap, art, title="Phase 6 — where internalization pays, per energy-coupling class (Decision view)"))
    (VIZ / "protocell-energy-budget.html").write_text(
        energy_budget_figure(art, activity="1", title="Phase 6 — one individual's power budget per coupling class (Mechanism view)"))
    print(f"wrote {paths['threshold_map']}, {paths['report']} and viz/ ({time.time() - t0:.0f}s)")
    print(art["headline"])
    print("decision discipline:", art["decision_discipline"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
