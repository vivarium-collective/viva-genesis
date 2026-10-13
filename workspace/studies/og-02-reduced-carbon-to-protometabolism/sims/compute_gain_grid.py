#!/usr/bin/env python
"""Compute + persist the og-02 protometabolic ignition grid (the Decision view).

Sweeps the real libRoadRunner rTCA composite over (feed CO₂ × washout rate) and
writes the decision surfaces (OAA hub pool, net throughput, autocatalytic gain) to
``artifacts/protometabolism_gain_grid.json``. The study's declared
``ProtometabolismGainPhaseMap`` renders from that artifact. Re-run to refresh:

    PYTHONPATH=<worktree> python workspace/studies/og-02-.../sims/compute_gain_grid.py [--fine]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"


def main() -> int:
    from viva_genesis.phase_maps import protometabolism_gain_phase_map
    from viva_genesis.viz_phase import sweep_to_json

    fine = "--fine" in sys.argv
    n = 24 if fine else 16
    n_jobs = 6 if fine else 4
    t0 = time.time()
    res = protometabolism_gain_phase_map(feed_CO2=(1.0e-4, 1.0e-2, n),
                                         k_wash=(2.0e-3, 1.0, n), n_steps=60, n_jobs=n_jobs)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / "protometabolism_gain_grid.json"
    out.write_text(json.dumps({"gain": json.loads(sweep_to_json(res))}))
    print(f"wrote {out} ({n}x{n}, {time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
