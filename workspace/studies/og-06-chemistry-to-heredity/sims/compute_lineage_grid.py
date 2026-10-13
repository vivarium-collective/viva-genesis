#!/usr/bin/env python
"""Compute + persist the og-06 heredity error-threshold grid (the Decision view).

Sweeps the agent-based lineage model (viva_genesis.heredity.lineage) over
(per-site fidelity × template length) for the RNA-like TEMPLATE module and reduces
each lineage to its functional persistence (mean function × surviving fraction), so
the Eigen error threshold Q = fidelity^length appears as a pass/fail boundary. The
non-template modules (compositional / hybrid / non-heritable) are sampled into the
grid's meta as length-independent reference bands. The study's declared
``HeredityLineageTree`` visualization renders from this artifact, so the sweep runs
here (not at page-load). Re-run to refresh:

    PYTHONPATH=<worktree> python workspace/studies/og-06-.../sims/compute_lineage_grid.py [--fine]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"


def main() -> int:
    from viva_genesis.phase_maps import heredity_error_threshold_map
    from viva_genesis.viz_phase import sweep_to_json

    fine = "--fine" in sys.argv
    n = 22 if fine else 16
    reps = 3 if fine else 2          # replicate seeds average out agent-model stochasticity

    t0 = time.time()
    res = heredity_error_threshold_map(
        per_site_fidelity=(0.90, 0.995, n), length=(6, 44, n),
        n_gen=40, replicates=reps)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / "heredity_error_threshold_grid.json"
    out.write_text(sweep_to_json(res))
    print(f"wrote {out} ({n}x{n}, {reps} reps, {time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
