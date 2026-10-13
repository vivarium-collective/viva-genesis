#!/usr/bin/env python
"""Compute + persist the og-08 off-gradient survival-frontier grid (the Decision view).

Sweeps the deterministic off-gradient lineage model (viva_genesis.autonomy.off_gradient)
over (environmental-support level × innovation-set) and reduces each point to its
final persistence (surviving fraction), so the survival frontier — the minimum support
at which each innovation set persists — appears as a pass/fail boundary. The full set
reaches support→0 (autonomy); each single knockout is lifted off the gradient. The
study's declared ``OffGradientPhaseMap`` visualization renders from this artifact, so
the sweep runs here (not at page-load). Re-run to refresh:

    PYTHONPATH=<worktree> python workspace/studies/og-08-.../sims/compute_offgradient_grid.py [--fine]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"


def main() -> int:
    from viva_genesis.phase_maps import off_gradient_phase_map
    from viva_genesis.viz_phase import sweep_to_json

    fine = "--fine" in sys.argv
    n = 40 if fine else 28           # support resolution (the model is cheap + deterministic)
    n_steps = 80 if fine else 60

    t0 = time.time()
    res = off_gradient_phase_map(support=(0.0, 1.0, n), n_steps=n_steps)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / "off_gradient_grid.json"
    out.write_text(sweep_to_json(res))
    print(f"wrote {out} ({n} supports x {len(res.meta['innovation_sets'])} sets, "
          f"{n_steps} steps, {time.time() - t0:.1f}s)")
    print("frontier:", res.meta["frontier"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
