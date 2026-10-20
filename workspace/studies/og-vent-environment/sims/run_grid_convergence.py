"""Grid-convergence + PHREEQC-vs-literature speciation control for og-vent-environment.

New-simulation control (figure-review Priority 2, LOCAL — deterministic, ~5 runs, no
mini needed). Sweeps the FiPy cross-section resolution nx and checks (a) that the vent
outlet observables converge (is the study's nx=40 resolved?), and (b) that the converged
PHREEQC speciation sits in the Lost City literature ranges. The genuine PHREEQC + FiPy
reactor, only the mesh resolution varied.

Lost City reference (Kelley 2001/2005; Proskurowski 2008; Seyfried 2015):
  T 40-91 °C ; pH 9.0-11.0 (mineral-buffered ~9-9.8) ; dissolved H2 positive (~1-15 mmol/kg).
"""
from __future__ import annotations

import json
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]
OUT = STUDY_DIR / "artifacts" / "og-00-vent-reactor-baseline" / "grid_convergence_control.json"
NX_GRID = [20, 40, 80, 120, 160]
N_STEPS = 60

# Lost City literature windows (outlet fluid)
LIT = {"temperature_C": (40.0, 91.0), "pH": (9.0, 11.0), "H2_positive": True}


def main() -> int:
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.core import build_core
    from viva_genesis.composites.vent_reactor import serpentinizing_vent_reactor

    def run(nx: int) -> dict:
        core = build_core()
        sim = Composite({"state": serpentinizing_vent_reactor(core, nx=nx)}, core=core)
        sim.run(float(N_STEPS))
        last = (gather_emitter_results(sim).get(("emitter",)) or next(iter(gather_emitter_results(sim).values())))[-1]
        T = last.get("temperature")
        return {
            "nx": nx,
            "temperature_K": T,
            "temperature_C": (T - 273.15) if T is not None else None,
            "pH": last.get("pH"),
            "porosity": last.get("porosity"),
            "H2": last.get("H2"),
            "alkalinity": last.get("alkalinity"),
            "charge_imbalance": last.get("charge_imbalance"),
            "flux_divergence_residual": last.get("flux_divergence_residual"),
        }

    arms = [run(nx) for nx in NX_GRID]
    finest = arms[-1]

    # convergence = relative change of each observable vs the finest mesh
    def rel(a, key):
        va, vf = a.get(key), finest.get(key)
        if va is None or vf is None or vf == 0:
            return None
        return abs(va - vf) / abs(vf)

    obs = ["temperature_C", "pH", "porosity", "H2", "alkalinity"]
    convergence = {a["nx"]: {k: rel(a, k) for k in obs} for a in arms}
    # is nx=40 (the study's choice) converged to <1% of the finest on every observable?
    nx40 = next(a for a in arms if a["nx"] == 40)
    nx40_converged = all((rel(nx40, k) or 0.0) < 0.01 for k in obs)

    lit_ok = {
        "temperature_C": (finest["temperature_C"] is not None
                          and LIT["temperature_C"][0] <= finest["temperature_C"] <= LIT["temperature_C"][1]),
        "pH": (finest["pH"] is not None and LIT["pH"][0] <= finest["pH"] <= LIT["pH"][1]),
        "H2_positive": (finest["H2"] is not None and finest["H2"] > 0),
    }
    max_charge_imbalance = max(abs(a["charge_imbalance"] or 0.0) for a in arms)

    artifact = {
        "study": "og-vent-environment",
        "control": "grid-convergence (nx sweep) + PHREEQC-vs-literature speciation",
        "nx_grid": NX_GRID,
        "arms": arms,
        "convergence_rel_to_finest": convergence,
        "nx40_converged_under_1pct": nx40_converged,
        "max_charge_imbalance_over_sweep": max_charge_imbalance,
        "lostcity_literature_check": {"windows": LIT, "converged_outlet": {
            "temperature_C": finest["temperature_C"], "pH": finest["pH"], "H2": finest["H2"]}, "in_window": lit_ok},
        "verdict": (
            f"nx=40 {'IS' if nx40_converged else 'is NOT'} converged (<1% of nx=160 on every outlet observable); "
            f"outlet speciation {'in' if all(lit_ok.values()) else 'OUTSIDE'} the Lost City literature windows; "
            f"charge balance held (max |imbalance| {max_charge_imbalance:.2e})."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2))
    for a in arms:
        print(f"nx={a['nx']:>3}: T={a['temperature_C']:.1f}C pH={a['pH']:.2f} H2={a['H2']:.3g} "
              f"|charge|={abs(a['charge_imbalance'] or 0):.1e}")
    print(f"nx=40 converged<1%: {nx40_converged} | Lost City in-window: {lit_ok}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
