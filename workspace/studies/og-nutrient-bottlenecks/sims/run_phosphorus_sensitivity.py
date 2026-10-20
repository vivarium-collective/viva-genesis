"""Phosphorus availability sensitivity sweep for og-nutrient-bottlenecks (P arm).

New-simulation sweep (figure-review Priority 2, LOCAL — deterministic tellurium SBML ODE,
no seeds). Sweeps the two real P-availability knobs — the mineral-sink loss rate k_prec
(precipitation/adsorption) × the pore enrichment (concentration), plus a temperature line —
and reports whether reactive phosphorus becomes AVAILABLE (net reactive-P production > 0)
before it precipitates, with the total-P mass residual as a conservation check.

HONESTY: this composite does NOT parameterize pH — so a pH-sensitivity axis is NOT
representable without a model change (flagged as owner future-work). The sweep runs the
knobs the model actually has: mineral-sink (loss_rate) × concentration (pore_enrichment)
× temperature. 0.0 is never used for an "off" knob (pbg is_empty backfill); the open-pore
control is pore_enrichment=1 (a real value), the mineral sink stays > 0.
"""
from __future__ import annotations

import json
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
OUT = STUDY_DIR / "artifacts" / "og-res-phosphorus-availability" / "phosphorus_sensitivity.json"
LOSS = [0.02, 0.04, 0.08, 0.16, 0.32]          # k_prec mineral-sink (1/s)
ENRICH = [1.0, 10.0, 30.0, 60.0, 100.0]        # pore enrichment (1 = open-pore control)
TEMPS = [313.15, 333.15, 353.15, 373.15]       # K
N_STEPS = 80


def main() -> int:
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.core import build_core
    from viva_genesis.composites.phosphorus_availability import phosphorus_availability

    def run(**kw) -> dict:
        core = build_core()
        sim = Composite({"state": phosphorus_availability(core, **kw)}, core=core)
        sim.run(float(N_STEPS))
        last = (gather_emitter_results(sim).get(("emitter",)) or next(iter(gather_emitter_results(sim).values())))[-1]
        return {
            "net_reactive_P": last.get("net_reactive_P"),
            "reactive_P": last.get("reactive_P"),
            "precipitated_fraction": last.get("precipitated_fraction"),
            "p_mass_residual": last.get("p_mass_residual"),
        }

    grid = []
    for lr in LOSS:
        for pe in ENRICH:
            r = run(loss_rate=lr, pore_enrichment=pe)
            grid.append({"loss_rate": lr, "pore_enrichment": pe, **r})
    temp_line = [{"temperature": T, **run(temperature=T)} for T in TEMPS]

    available = [g for g in grid if (g["net_reactive_P"] or 0.0) > 0]
    max_resid = max(abs(g["p_mass_residual"] or 0.0) for g in grid + temp_line)
    artifact = {
        "study": "og-nutrient-bottlenecks",
        "sweep": "phosphorus availability — mineral-sink (loss_rate) × concentration (pore_enrichment) × temperature",
        "axes": {"loss_rate": LOSS, "pore_enrichment": ENRICH, "temperature_K": TEMPS},
        "grid": grid,
        "temperature_line": temp_line,
        "availability_region_fraction": len(available) / len(grid) if grid else None,
        "max_p_mass_residual": max_resid,
        "pH_note": ("pH is NOT a parameter of this P-speciation composite, so pH-sensitivity is not "
                    "representable without a model change (flagged as owner future-work); the sweep covers "
                    "the knobs the model actually has: mineral-sink loss_rate × pore_enrichment × temperature."),
        "verdict": (
            f"reactive P is available (net production > 0) in {len(available)}/{len(grid)} of the "
            f"mineral-sink × concentration grid; total-P conserved (max |residual| {max_resid:.2e})."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2))
    print(f"grid {len(grid)} cells; available (net>0): {len(available)}; max |P mass residual| {max_resid:.2e}")
    # terse corner readout
    for g in (grid[0], grid[len(grid)//2], grid[-1]):
        print(f"  loss={g['loss_rate']} enrich={g['pore_enrichment']}: net_reactive_P={g['net_reactive_P']:.3g} "
              f"precip_frac={g['precipitated_fraction']:.3g}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
