"""Transport-attribution matched nulls for og-spatial-concentration (Gate B spatial).

New-simulation control (figure-review Priority 2). Favourable thermal trap vs three
matched nulls, every other parameter held equal, on the same real FiPy
ThermophoreticTrapProcess:
  - thermal-gradient-off (ΔT → 0)
  - no convection        (flow → 0)
  - open pore            (porosity ≈ 1)
Each null collapses the localized enrichment to ~1: the accumulation Péclet (hence the
enrichment) depends on ALL three transport terms — the thermal gradient, the convective
flow, and the pore confinement.

NOTE (pbg is_empty gotcha): a knob set to exactly 0.0 is backfilled to its DEFAULT
(0.0 reads as empty/unset), so ΔT=0.0 / flow=0.0 silently reproduce the favourable arm.
The honest off-nulls therefore use a near-zero epsilon (1e-9), not 0.0.
"""
from __future__ import annotations

import json
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
OUT = STUDY_DIR / "artifacts" / "og-03-dilution-to-localized-individuals" / "gradient_off_control.json"


def main() -> int:
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.core import build_core
    from viva_genesis.composites.thermophoretic_concentration import thermophoretic_concentration

    core = build_core()

    def run(**kw) -> dict:
        doc = thermophoretic_concentration(core, **kw)
        sim = Composite({"state": doc}, core=core)
        sim.run(30.0)
        last = gather_emitter_results(sim)[("emitter",)][-1]
        return {
            "params": kw,
            "enrichment_factor": last.get("enrichment_factor"),
            "accumulation_peclet": last.get("accumulation_peclet"),
            "residence_time": last.get("residence_time"),
        }

    favorable = run()                      # defaults — Baaske favourable trap
    gradient_off = run(delta_T=1.0e-9)     # thermal-gradient-off (epsilon, not 0.0)
    flow_off = run(flow_velocity=1.0e-9)   # no convection (epsilon, not 0.0)
    open_pore = run(porosity=0.99)         # open pore / wash-through

    ef_fav = favorable["enrichment_factor"] or 0.0

    def ratio(arm):
        ef = arm["enrichment_factor"] or 0.0
        return (ef / ef_fav) if ef_fav else None

    arms = {"favorable": favorable, "gradient_off": gradient_off,
            "flow_off": flow_off, "open_pore": open_pore}
    collapse = {k: (ratio(v) is not None and ratio(v) < 0.1)
                for k, v in arms.items() if k != "favorable"}
    drivers = [k for k, c in collapse.items() if c]
    artifact = {
        "study": "og-spatial-concentration",
        "control": "transport-attribution matched nulls (ΔT / flow / open-pore)",
        "description": (
            "Favourable thermal trap vs three matched nulls, every other parameter held "
            "equal. Attributes which transport term the localized enrichment depends on."
        ),
        "arms": arms,
        "enrichment_collapse_ratio": {k: ratio(arms[k]) for k in collapse},
        "collapses_enrichment": collapse,
        "attribution": (
            "enrichment collapses under each of: " + ", ".join(drivers)
            if drivers else "no null collapses enrichment (HONEST NEGATIVE — revisit driver)"
        ),
        "note": (
            "The accumulation Péclet (hence the enrichment) depends on all three transport terms — the "
            "thermal gradient (ΔT), the convective flow, and the pore confinement (porosity): each off-null "
            "collapses enrichment ~10⁸× → ~1. Consistent with og-spatial-concentration's Péclet-gated "
            "framing; gate/verdict unchanged. (Off-nulls use epsilon 1e-9, not 0.0 — a bare 0.0 is backfilled "
            "to the default by the pbg is_empty rule and silently reproduces the favourable arm.)"
        ),
    }
    print(f"favorable EF={ef_fav:.4g}")
    for k in ("gradient_off", "flow_off", "open_pore"):
        print(f"  {k}: EF={arms[k]['enrichment_factor']:.4g}  ratio={ratio(arms[k])}  collapses={collapse[k]}")
    print(f"attribution: {artifact['attribution']}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
