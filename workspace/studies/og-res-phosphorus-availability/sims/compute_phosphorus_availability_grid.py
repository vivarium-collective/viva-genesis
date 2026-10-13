#!/usr/bin/env python
"""Compute + persist the phosphorus reactive-P availability grid (the Decision view).

Sweeps the real libRoadRunner P-speciation composite over (phosphate source ×
pore/thermal enrichment) and writes the decision surfaces (settled reactive-P pool,
net availability = production − precipitation loss, precipitated fraction) to
``artifacts/phosphorus_availability_grid.json``. The study's declared
``PhosphorusAvailabilityMap`` renders from that artifact. Re-run to refresh:

    PYTHONPATH=<worktree> python workspace/studies/og-res-.../sims/compute_phosphorus_availability_grid.py [--fine]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"


def main() -> int:
    from viva_genesis.phase_maps import phosphorus_availability_map
    from viva_genesis.viz_phase import sweep_to_json

    fine = "--fine" in sys.argv
    n = 24 if fine else 16
    n_jobs = 6 if fine else 4
    t0 = time.time()
    res = phosphorus_availability_map(phosphate_supply=(1.0e-6, 1.0e-3, n),
                                      pore_enrichment=(1.0, 60.0, n),
                                      n_steps=100, n_jobs=n_jobs)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / "phosphorus_availability_grid.json"
    out.write_text(json.dumps({"phosphorus": json.loads(sweep_to_json(res))}))
    print(f"wrote {out} ({n}x{n}, {time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
