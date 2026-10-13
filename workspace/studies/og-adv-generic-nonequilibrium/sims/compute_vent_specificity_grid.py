#!/usr/bin/env python
"""Compute + persist the og-adv vent-specificity grid (the Decision view).

Sweeps the real og-01 carbon-fixation composite over (dissolved H2 x Fe/Ni/S catalyst
activity) and reduces each run to the peak net-carbon-fixation flux the og-01 gate
reads, so the gate's pass/fail boundary appears as a contour: the PASS region is the
vent corner, and generic non-vent chemistry (H2~0, no catalyst) sits far below it.
The per-gate rejection of the generic control (og-01/02/03 gates, vent vs generic)
is computed once and stored in the grid meta as ``gate_rows`` so the declared
``VentSpecificityMap`` visualization renders both panels from this artifact. Re-run:

    PYTHONPATH=<worktree> python workspace/studies/og-adv-.../sims/compute_vent_specificity_grid.py [--fine]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"


def main() -> int:
    from viva_genesis.adversarial import adversarial_verdict
    from viva_genesis.core import build_core
    from viva_genesis.phase_maps import vent_specificity_map
    from viva_genesis.viz_phase import sweep_to_json

    fine = "--fine" in sys.argv
    n = 22 if fine else 16

    t0 = time.time()
    res = vent_specificity_map(h2=(1.0e-9, 2.0e-2, n), catalyst_active=(0.0, 1.0, n), n_steps=60)
    # Per-gate rejection of the generic control (og-01/02/03 gates) for the Mechanism panel.
    res.meta["gate_rows"] = adversarial_verdict(build_core())["gate_rows"]

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / "vent_specificity_grid.json"
    out.write_text(sweep_to_json(res))
    print(f"wrote {out} ({n}x{n}, {time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
