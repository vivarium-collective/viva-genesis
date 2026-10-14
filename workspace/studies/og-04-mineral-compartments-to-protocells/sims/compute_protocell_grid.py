#!/usr/bin/env python
"""Compute + persist the og-04 protocell grid (the Decision view).

Sweeps the real ``mixed_amphiphile_protocell`` composite twice: a 1-D temperature arc
(the retention-access plane — too-closed → viable → too-open) and a 2-D (co-surfactant
fraction × ionic strength) feasibility map (the viable salt ceiling rises with mixed
amphiphiles, individuality = retention × access with a PASS boundary at 0.1). Both are
persisted into one artifact so the declared ``ProtocellPhaseMap`` visualization renders
from it rather than recomputing live. Re-run to refresh:

    PYTHONPATH=<worktree> python workspace/studies/og-04-.../sims/compute_protocell_grid.py [--fine]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"


def main() -> int:
    from viva_genesis.phase_maps import protocell_feasibility_map, protocell_retention_access_arc
    from viva_genesis.viz_phase import sweep_to_json

    fine = "--fine" in sys.argv
    n = 22 if fine else 16
    n_temp = 36 if fine else 28

    t0 = time.time()
    arc = protocell_retention_access_arc(temperature=(285.0, 360.0, n_temp), n_steps=20)
    feas = protocell_feasibility_map(mix_fraction=(0.0, 0.6, n), ionic_strength=(0.05, 1.2, n),
                                     n_steps=20)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    blob = {"arc": json.loads(sweep_to_json(arc)), "feas": json.loads(sweep_to_json(feas))}
    out = ARTIFACTS / "protocell_grid.json"
    out.write_text(json.dumps(blob))
    print(f"wrote {out} (arc n_temp={n_temp}, feas {n}x{n}, {time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
