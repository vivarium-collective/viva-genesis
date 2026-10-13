#!/usr/bin/env python
"""Compute + persist the og-res nitrogen phase-map grid (the Decision view).

Sweeps the real open-flow reduced-nitrogen reactor over (nitrate supply × FeS
activity) and writes the reduced decision surfaces (C:N supply ratio, keeps-pace
mask, ammonium production, standing pool) to
``artifacts/nitrogen_assimilation_phase_grid.json``. The study's declared
``NitrogenAssimilationPhaseMap`` visualization renders from that artifact, so the
sweep runs here (parallel), not at page-load. Re-run to refresh the grid:

    PYTHONPATH=<worktree> python workspace/studies/og-res-.../sims/compute_nitrogen_grid.py [--fine]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"


def main() -> int:
    from viva_genesis.phase_maps import (_CN_KEEPS_PACE_THRESHOLD,
                                         nitrogen_assimilation_phase_map)
    from viva_genesis.viz_phase import sweep_to_json

    fine = "--fine" in sys.argv
    n = 22 if fine else 16
    n_jobs = 6 if fine else 5

    t0 = time.time()
    res = nitrogen_assimilation_phase_map(
        no3_supply=(2.0e-6, 1.0e-4, n), fes_activity=(0.05, 1.0, n),
        n_steps=140, n_jobs=n_jobs)
    res.meta["cn_keeps_pace_threshold"] = _CN_KEEPS_PACE_THRESHOLD
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / "nitrogen_assimilation_phase_grid.json"
    out.write_text(sweep_to_json(res))
    print(f"wrote {out} ({n}x{n}, {time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
