#!/usr/bin/env python
"""Compute + persist the og-00 Lost City habitability grid (the Decision view).

Sweeps the real PHREEQC + FiPy ``serpentinizing_vent_reactor`` over (olivine reaction
rate × flow velocity) and reduces each run to its settled outlet temperature, pH and
H2 flux — and the habitability PASS flag (inside the Lost City T/pH window with a
positive H2 flux). The sweep is TOLERANT: an over-reacted / under-flushed point that
over-heats past PHREEQC's 0-100 C aqueous-model validity is recorded NaN and reads as
the too-hot FAIL region. The study's declared ``VentHabitabilityMap`` visualization
renders from this artifact (FiPy is slow, so the grid is computed here, not at
page-load). Re-run to refresh:

    PYTHONPATH=<worktree> python workspace/studies/og-00-.../sims/compute_vent_habitability_grid.py [--fine] [--jobs N]

NOTE: the default is SERIAL (jobs=1). The PHREEQC C extension does not survive a
process-pool worker (a rejected point terminates the worker → BrokenProcessPool), so
the tolerant per-point catch only holds in-process; parallel is unsafe for this sweep.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"


def _arg(flag: str, default: int) -> int:
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return int(sys.argv[i + 1])
    return default


def main() -> int:
    from viva_genesis.phase_maps import vent_habitability_phase_map
    from viva_genesis.viz_phase import sweep_to_json

    fine = "--fine" in sys.argv
    n = 16 if fine else 12
    jobs = _arg("--jobs", 1)

    t0 = time.time()
    res = vent_habitability_phase_map(
        olivine_rate=(0.005, 0.4, n), flow_velocity=(2.0e-4, 3.0e-2, n),
        nx=20, n_steps=30, n_jobs=jobs)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / "vent_habitability_grid.json"
    out.write_text(sweep_to_json(res))
    print(f"wrote {out} ({n}x{n}, jobs={jobs}, {time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
