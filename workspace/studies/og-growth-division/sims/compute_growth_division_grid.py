#!/usr/bin/env python
"""Compute + persist the og-growth-division viable-band grid (the Decision view).

Sweeps the real ``osmotic_growth_division`` composite over (network throughput ×
membrane permeability) and reduces each point to its division count and physical-fate
code, so the bounded viable growth→division band — between starvation (too permeable:
the product leaks, no osmotic build-up) and lysis (too impermeable: the osmotic
pressure bursts the membrane) — appears as a pass/fail region. The study's declared
``GrowthDivisionMap`` visualization renders from this artifact, so the sweep runs here
(not at page-load). Re-run to refresh:

    PYTHONPATH=<worktree> python workspace/studies/og-growth-division/sims/compute_growth_division_grid.py [--fine]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"


def main() -> int:
    from viva_genesis.phase_maps import growth_division_map
    from viva_genesis.viz_phase import sweep_to_json

    fine = "--fine" in sys.argv
    n = 28 if fine else 18           # per-axis resolution (the composite is pure-numpy + fast)
    n_steps = 120 if fine else 100
    n_jobs = 4 if fine else 1

    t0 = time.time()
    res = growth_division_map(
        network_throughput=(1.0e-21, 1.0e-18, n),
        membrane_permeability=(1.0e-10, 1.0e-4, n),
        n_steps=n_steps, n_jobs=n_jobs)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / "growth_division_grid.json"
    out.write_text(sweep_to_json(res))
    print(f"wrote {out} ({n}x{n} grid, {n_steps} steps, {time.time() - t0:.1f}s)")
    print(f"viable (growth->division) fraction: {res.meta['viable_fraction']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
