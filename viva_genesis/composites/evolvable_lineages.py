"""NEW D — og-evolvable-lineages: evolvability GIVEN a granted individual.

The last bridge (Pass 3, evolution synthesis) and the second §9 open transition.
C refuted endogenous closure, so the self-maintaining individual D needs does NOT
form endogenously under defensible vent conditions. D therefore tests evolvability
CONDITIONAL ON A GRANTED INDIVIDUAL - the protocell/membrane is an explicit stated
assumption and the fitness grounding runs at B's favorable S_T corner regime - never
as if the individual were free.

Given an individual, the honest question: does stochastic chemical partition +
variation at (mechanically-defensible, og-reproduction) division produce heritable,
selectable organization across generations ABOVE two matched nulls - and is it
OPEN-ENDED or merely BOUNDED fixed-trait selection?

This reuses the real HeredityPopulationProcess (og_34): a population of og_33-dividing
protocells under Wright-Fisher selection on an inherited network-COMPOSITION trait
c in [0,1], with fitness GROUNDED in the real composition -> membrane retention
(study-32 MD endpoints) -> standing pool -> division rate coupling (not a toy fitness).
The two matched nulls and the changed-environment adaptation test are realized through
its existing config (see sims/run.py):

  - no-inheritance null : inheritance=False (daughters reset to the common composition)
  - shared-feed null    : a FLAT fitness landscape (retention_lo == retention_hi) - the
                          fitness differential removed, heredity intact
  - changed environment : swap retention_lo/hi mid-run (flip which composition is favored)

D's false-demonstration knob (A's feed / B's Soret / C's aggregation-gate equivalent):
claiming OPEN-ENDED evolvability when the demonstration is BOUNDED fixed-trait selection
saturating at the modeled optimum. The trait is a fixed scalar with a single optimum;
heritable variance DECLINES as the population converges. The runner demonstrates the
real selection response + adaptation above the nulls AND explicitly reports the bounded,
fixed-trait character (declining variance, fixed scalar space) - it never claims
open-endedness from bounded re-selection.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

# Flat-landscape shared-feed null uses this common retention (no fitness differential).
_FLAT_RETENTION = 0.5


@composite_generator(
    name="og_evolvable_lineages",
    methods=["inherited network-composition trait (compositional / GARD-style)",
             "fitness grounded in composition -> retention -> division-rate coupling",
             "Wright-Fisher selection vs matched no-inheritance AND shared-feed nulls",
             "open-ended-vs-bounded fixed-trait test (heritable-variance trajectory)"],
    fidelity="real",
    description=(
        "NEW D (one static-environment condition): selection on an inherited network-composition trait in a "
        "population of og_33-dividing protocells, fitness grounded in the real composition->retention->division "
        "coupling. GIVEN a granted individual (C refuted endogenous closure). The runner drives this across the "
        "full condition, the no-inheritance null (inheritance=False), the shared-feed null (flat retention "
        "landscape), and a changed environment (swapped optimum), and reports whether evolvability is real above "
        "the nulls and whether it is open-ended or bounded fixed-trait selection."
    ),
    parameters={
        "inheritance": {"type": "boolean", "default": True,
                        "description": "Inherit parent composition (True) vs no-inheritance null (False)"},
        "fitness_exponent": {"type": "float", "default": 2.0,
                             "description": "Sharpens selection on retention (grounded fitness)"},
        "retention_lo": {"type": "float", "default": 0.333,
                         "description": "Retention at c=0 (study-32 short-chain MD endpoint); == retention_hi = shared-feed null"},
        "retention_hi": {"type": "float", "default": 0.661,
                         "description": "Retention at c=1 (study-32 long-chain MD endpoint); swap with lo = changed environment"},
        "sigma": {"type": "float", "default": 0.03, "description": "Heritable partition/mutation std (declared, not tuned)"},
        "n_pop": {"type": "integer", "default": 120, "description": "Population size"},
        "seed": {"type": "integer", "default": 7, "description": "RNG seed (replicate)"},
    },
    default_n_steps=40,
    preferred_time="2 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter",
               "paths": ["pop/mean_composition", "pop/selection_response",
                         "pop/parent_offspring_fitness_correlation", "pop/heritable_fitness_variance"]}],
)
def og_evolvable_lineages(core=None, *, inheritance=True, fitness_exponent=2.0,
                          retention_lo=0.333, retention_hi=0.661, sigma=0.03, n_pop=120, seed=7):
    if core is None:
        core = build_core()
    return {
        "population": {
            "_type": "process",
            "address": "local:HeredityPopulationProcess",
            "config": {"inheritance": bool(inheritance), "n_pop": int(n_pop), "sigma": float(sigma),
                       "seed": int(seed), "fitness_exponent": float(fitness_exponent),
                       "retention_lo": float(retention_lo), "retention_hi": float(retention_hi)},
            "interval": 1.0,
            "inputs": {"metabolic_flux": ["env", "metabolic_flux"]},
            "outputs": {
                "parent_offspring_fitness_correlation": ["pop", "parent_offspring_fitness_correlation"],
                "population_composition_shift": ["pop", "population_composition_shift"],
                "heritable_fitness_variance": ["pop", "heritable_fitness_variance"],
                "selection_response": ["pop", "selection_response"],
                "mean_composition": ["pop", "mean_composition"],
                "generation": ["pop", "generation"],
            },
        },
        "env": {"metabolic_flux": 0.0},
        "pop": {"parent_offspring_fitness_correlation": 0.0, "population_composition_shift": 0.0,
                "heritable_fitness_variance": 0.0, "selection_response": 0.0,
                "mean_composition": 0.0, "generation": 0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {"mean_composition": "float", "selection_response": "float",
                                "parent_offspring_fitness_correlation": "float",
                                "heritable_fitness_variance": "float", "generation": "float",
                                "global_time": "float"}},
            "inputs": {
                "mean_composition": ["pop", "mean_composition"],
                "selection_response": ["pop", "selection_response"],
                "parent_offspring_fitness_correlation": ["pop", "parent_offspring_fitness_correlation"],
                "heritable_fitness_variance": ["pop", "heritable_fitness_variance"],
                "generation": ["pop", "generation"],
                "global_time": ["global_time"],
            },
        },
    }
