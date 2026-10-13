#!/usr/bin/env python
"""Compute + persist the og-07 metacommunity-robustness grid (the Decision view).

Sweeps the cross-feeding metacommunity composite over (cross-feeding exchange_rate ×
inter-compartment diversity) and reduces each run to its settled robustness
(functional redundancy), the isolated counterfactual, the collective capability
diversity and the LUCA-overlap boundary — so the robustness-emergence boundary
appears as a phase boundary in the plane. The study's declared
``MetacommunityPhaseMap`` visualization renders from this artifact, so the sweep runs
here (not at page-load). Re-run to refresh:

    PYTHONPATH=<worktree> python workspace/studies/og-07-.../sims/compute_metacommunity_grid.py [--fine]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"


def main() -> int:
    from viva_genesis.phase_maps import _ROBUST_EMERGE_THRESHOLD, metacommunity_robustness_phase_map
    from viva_genesis.viz_phase import sweep_to_json

    fine = "--fine" in sys.argv
    n = 22 if fine else 16

    t0 = time.time()
    res = metacommunity_robustness_phase_map(
        exchange_rate=(0.02, 0.8, n), diversity=(0.05, 1.0, n),
        n_steps=40, n_jobs=1)
    res.meta["robust_emerge_threshold"] = _ROBUST_EMERGE_THRESHOLD
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / "metacommunity_robustness_grid.json"
    out.write_text(sweep_to_json(res))
    print(f"wrote {out} ({n}x{n}, {time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
