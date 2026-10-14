#!/usr/bin/env python
"""Compute + persist the og-05 bioenergetic-survival grid (the Decision view).

Sweeps the real ``bioenergetic_internalization`` replicator loop over (pump catalyst
efficiency × gradient floor) under the declining external gradient, reducing each run
to its final surviving fraction and internalization — so the survival frontier and the
Sojo cost line (minimum efficiency to internalize) appear as phase boundaries. The
study's declared ``BioenergeticSurvivalMap`` visualization renders from this artifact
(not at page-load). Re-run to refresh:

    PYTHONPATH=<worktree> python workspace/studies/og-05-.../sims/compute_bioenergetic_survival_grid.py [--fine]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"


def main() -> int:
    from viva_genesis.phase_maps import bioenergetic_survival_map
    from viva_genesis.viz_phase import sweep_to_json

    fine = "--fine" in sys.argv
    n = 24 if fine else 14

    t0 = time.time()
    res = bioenergetic_survival_map(
        catalyst_efficiency=(0.05, 1.3, n), gradient_floor=(0.005, 0.35, n),
        n_steps=40, n_jobs=1)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / "bioenergetic_survival_grid.json"
    out.write_text(sweep_to_json(res))
    print(f"wrote {out} ({n}x{n}, {time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
