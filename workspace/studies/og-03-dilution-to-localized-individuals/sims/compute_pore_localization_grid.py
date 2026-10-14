#!/usr/bin/env python
"""Compute + persist the og-03 pore-localization grid (the native Decision view).

Sweeps the real FiPy ``thermophoretic_concentration`` trap over (pore porosity × pore
length) and reduces each run to its settled fold-enrichment and accumulation Peclet —
so the localization frontier (enrichment ~ 1e6, Peclet ~ 18) appears as a phase
boundary. The study's declared ``PoreLocalizationMap`` visualization renders from this
artifact (not at page-load). Re-run to refresh:

    PYTHONPATH=<worktree> python workspace/studies/og-03-.../sims/compute_pore_localization_grid.py [--fine]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"


def main() -> int:
    from viva_genesis.phase_maps import pore_localization_map
    from viva_genesis.viz_phase import sweep_to_json

    fine = "--fine" in sys.argv
    n = 20 if fine else 12

    t0 = time.time()
    res = pore_localization_map(
        porosity=(0.05, 0.95, n), pore_length=(5.0e-4, 8.0e-3, n),
        n_steps=15, n_jobs=1)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / "pore_localization_grid.json"
    out.write_text(sweep_to_json(res))
    print(f"wrote {out} ({n}x{n}, {time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
