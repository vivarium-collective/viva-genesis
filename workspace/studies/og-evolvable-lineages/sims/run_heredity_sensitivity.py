"""Heredity selection-strength × population-size sensitivity sweep for og-evolvable-lineages.

New-simulation sweep (figure-review Priority 4, LOCAL — the Wright-Fisher
HeredityPopulationProcess is ~1 s/run; the composite's "2 hours" is biological time, not
wall-clock). Measures the parent-offspring fitness correlation (the selectable-heredity
readout) across selection strength (fitness_exponent) × population size (n_pop), with
REPLICATE SEEDS for genuine uncertainty bands, and against the inheritance-shuffle null
(inheritance=False → daughters reset to the common composition).

Reports mean ± std across seeds (not just means), per the feedback's uncertainty ask.
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, pstdev

STUDY_DIR = Path(__file__).resolve().parents[1]
OUT = STUDY_DIR / "artifacts" / "og-evolvable-lineages" / "heredity_sensitivity.json"
SELECTION = [1.0, 2.0, 4.0]      # fitness_exponent
POPSIZE = [30, 120, 480]         # n_pop
SEEDS = list(range(8))           # replicate seeds for uncertainty bands
N_STEPS = 40


def main() -> int:
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.core import build_core
    from viva_genesis.composites.evolvable_lineages import og_evolvable_lineages

    def run(inheritance, fexp, npop, seed) -> float:
        core = build_core()
        doc = og_evolvable_lineages(core=core, inheritance=inheritance,
                                    fitness_exponent=fexp, n_pop=npop, seed=seed)
        sim = Composite({"state": doc}, core=core)
        sim.run(float(N_STEPS))
        last = (gather_emitter_results(sim).get(("emitter",)) or next(iter(gather_emitter_results(sim).values())))[-1]
        return last.get("parent_offspring_fitness_correlation")

    def band(inheritance, fexp, npop):
        vals = [v for s in SEEDS if (v := run(inheritance, fexp, npop, s)) is not None]
        return {"mean": mean(vals), "std": pstdev(vals), "n": len(vals)} if vals else None

    # main grid (with inheritance) — selection × popsize, bands over seeds
    grid = [{"fitness_exponent": fe, "n_pop": np_, **band(True, fe, np_)}
            for fe in SELECTION for np_ in POPSIZE]
    # inheritance-shuffle null at the canonical point (fexp=2, n_pop=120)
    null = band(False, 2.0, 120)
    canonical = band(True, 2.0, 120)

    artifact = {
        "study": "og-evolvable-lineages",
        "sweep": "parent-offspring fitness correlation vs selection strength × population size (seeds = uncertainty bands)",
        "axes": {"fitness_exponent": SELECTION, "n_pop": POPSIZE, "seeds": SEEDS},
        "grid": grid,
        "canonical_inheritance": canonical,
        "no_inheritance_null": null,
        "verdict": (
            f"inherited composition produces a selectable parent-offspring fitness correlation "
            f"{canonical['mean']:.3f} ± {canonical['std']:.3f} at the canonical point vs "
            f"{null['mean']:.3f} ± {null['std']:.3f} for the no-inheritance (shuffle) null; "
            "sensitivity to selection strength + population size reported with replicate bands."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2))
    print(f"canonical (inherit): {canonical['mean']:.3f} ± {canonical['std']:.3f}")
    print(f"no-inheritance null: {null['mean']:.3f} ± {null['std']:.3f}")
    for g in grid:
        print(f"  fexp={g['fitness_exponent']} n_pop={g['n_pop']}: {g['mean']:.3f} ± {g['std']:.3f}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
