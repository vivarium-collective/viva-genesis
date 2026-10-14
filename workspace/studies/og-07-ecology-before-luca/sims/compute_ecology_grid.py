#!/usr/bin/env python
"""Compute + persist the og-07 ecology robustness phase map (the Decision view of the
complete three-view figure).

Sweeps the cross-feeding metacommunity composite over (cross-feeding exchange_rate ×
parasite_load) at the canonical inter-compartment diversity and reduces each run to its
settled robustness (functional redundancy) and the LUCA-overlap boundary — so the
robustness-emergence / parasite-collapse boundary appears as a phase boundary in the
plane. The study's ``EcologyMetacommunityThreeView`` visualization renders its Decision
panel from this artifact, so the sweep runs here (not at page-load). Re-run to refresh:

    PYTHONPATH=<worktree> python workspace/studies/og-07-.../sims/compute_ecology_grid.py [--fine]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"


def main() -> int:
    from viva_genesis.phase_maps import _ROBUST_EMERGE_THRESHOLD, ecology_robustness_parasite_map
    from viva_genesis.viz_phase import sweep_to_json

    fine = "--fine" in sys.argv
    n = 22 if fine else 16

    t0 = time.time()
    res = ecology_robustness_parasite_map(
        exchange_rate=(0.02, 0.8, n), parasite_load=(0.0, 0.9, n),
        diversity=0.75, n_steps=40, n_jobs=1)
    res.meta["robust_emerge_threshold"] = _ROBUST_EMERGE_THRESHOLD
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / "ecology_robustness_grid.json"
    out.write_text(sweep_to_json(res))
    print(f"wrote {out} ({n}x{n}, {time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
