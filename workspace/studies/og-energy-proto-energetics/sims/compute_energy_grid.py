#!/usr/bin/env python
"""Compute + persist the og-proto-energetics free-energy-capture grid (Decision view).

Sweeps the real proto_energetics composite over (geochemical free-energy drive ×
coupling efficiency) and reduces each run to its settled charged fraction (is the
transferable currency maintained under load?), the captured stored-work fraction and
the useful work delivered — so the viability boundary appears as a phase boundary in
the plane. The study's declared ``ProtoEnergeticsMap`` visualization renders from this
artifact, so the sweep runs here (not at page-load). Re-run to refresh:

    PYTHONPATH=<worktree> python workspace/studies/og-energy-proto-energetics/sims/compute_energy_grid.py [--fine]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"


def main() -> int:
    from viva_genesis.phase_maps import proto_energetics_map
    from viva_genesis.viz_phase import sweep_to_json

    fine = "--fine" in sys.argv
    n = 24 if fine else 16
    n_jobs = 6 if fine else 4

    t0 = time.time()
    res = proto_energetics_map(drive_free_energy=(15.0, 70.0, n),
                               coupling_efficiency=(0.05, 1.0, n),
                               n_steps=60, n_jobs=n_jobs)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / "proto_energetics_phase_grid.json"
    out.write_text(sweep_to_json(res))
    print(f"wrote {out} ({n}x{n}, {time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
