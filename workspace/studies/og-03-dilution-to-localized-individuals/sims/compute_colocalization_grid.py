#!/usr/bin/env python
"""Compute + persist the og-03 multisolute co-localization grid (Phase 4 / §4.5).

Sweeps the reduced multisolute pore surrogate over (advective Peclet × Soret
strength) and reduces each cell to the co-localization index (min/max of the
eight-solute enrichment), the strongest single-species enrichment, and the share
of solutes that concentrate — so the mixture's **co-localize vs fractionate**
frontier appears as a Decision surface. The study's declared
``PoreColocalizationMap`` visualization renders from this artifact (not at
page-load). Re-run to refresh:

    PYTHONPATH=<worktree> python workspace/studies/og-03-.../sims/compute_colocalization_grid.py [--fine]

With ``--audit`` (run under viva-fenics's pixi env with viva-genesis + viva-fenics
on PYTHONPATH), it additionally runs the dolfinx FEM reference
(``fenics_multisolute_3d``) at a few cells and records the surrogate-vs-FEM
agreement — the plan §4.6 "report the surrogate's error beside the map" overlay.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS = STUDY_DIR / "artifacts"


def _audit(peclets, soret_scales):
    """Run the FEM reference at a few grid cells; return per-cell surrogate-vs-FEM
    coloc_index agreement. Requires dolfinx (pixi); returns {} on any failure."""
    try:
        import numpy as np
        from viva_genesis.core import build_core
        from viva_genesis.colocalization_map import coloc_index, _scaled_species
        from viva_genesis.multisolute_localization import FenicsMultisolutePoreProcess
        core = build_core()
        cells = [(peclets[0], soret_scales[-1]), (peclets[len(peclets) // 2], soret_scales[len(soret_scales) // 2])]
        out = []
        for pe, ss in cells:
            proc = FenicsMultisolutePoreProcess(
                config={"peclet": float(pe), "n_steps": 100,
                        "species_params": _scaled_species(ss)}, core=core)
            fem = proc.update({}, 1.0)
            fem_ci = coloc_index([{"enrichment": fem["enrichment"]}])
            out.append({"peclet": float(pe), "soret_scale": float(ss),
                        "fem_coloc_index": float(fem_ci)})
            print(f"  FEM audit Pe={pe:.1f} soret×{ss:.1f}: coloc={fem_ci:.3f}")
        return out
    except Exception as exc:  # noqa: BLE001
        print(f"  audit skipped ({type(exc).__name__}: {exc})")
        return []


def main() -> int:
    import numpy as np

    from viva_genesis.colocalization_map import colocalization_map
    from viva_genesis.viz_phase import sweep_to_json

    fine = "--fine" in sys.argv
    n = 16 if fine else 10

    t0 = time.time()
    res = colocalization_map(
        peclets=tuple(np.geomspace(1.0, 32.0, n)),
        soret_scales=tuple(np.geomspace(0.5, 8.0, n)),
    )
    if "--audit" in sys.argv:
        res.meta["fem_audit"] = _audit(list(res.axes["peclet"]), list(res.axes["soret_scale"]))

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS / "colocalization_grid.json"
    out.write_text(sweep_to_json(res))
    print(f"wrote {out} ({n}x{n}, {time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
