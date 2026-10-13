#!/usr/bin/env python
"""Compute + persist the og-01 carbon-fixation phase-map grid (the Decision view).

Sweeps the real open-flow carbon-fixation composite over (vent pH × dissolved H₂)
for the favourable and Tutolo-2026 parameterizations, and writes the reduced
decision surfaces to ``artifacts/carbon_fixation_phase_grid.json``. The study's
declared ``CarbonFixationPhaseMap`` visualization renders from that artifact, so the
expensive sweep runs here (parallel), not at page-load. Re-run to refresh the grid:

    PYTHONPATH=<worktree> python workspace/studies/og-01-.../sims/compute_phase_grid.py [--fine]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"


def main() -> int:
    from viva_genesis.phase_maps import carbon_fixation_phase_map
    from viva_genesis.viz_phase import sweep_to_json

    fine = "--fine" in sys.argv
    n = 20 if fine else 14
    n_jobs = 6 if fine else 5
    kw = dict(ph_vent=(7.0, 11.0, n), h2=(1.0e-4, 2.0e-2, n),
              dilution_rate=2.0, n_steps=60, n_jobs=n_jobs)

    t0 = time.time()
    fav = carbon_fixation_phase_map(gradient_efficiency=1.0, **kw)
    tut = carbon_fixation_phase_map(gradient_efficiency=0.1, **kw)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / "carbon_fixation_phase_grid.json"
    out.write_text(json.dumps({
        "favourable": json.loads(sweep_to_json(fav)),
        "tutolo": json.loads(sweep_to_json(tut)),
    }))
    print(f"wrote {out} ({n}x{n} x2, {time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
