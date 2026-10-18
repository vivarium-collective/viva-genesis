"""Study 34 (Gate D, second half) — Chemical Heredity & Selection.

A population of study-33 dividing protocells under selection on an inherited NETWORK
COMPOSITION trait (⚑3 Option B: compositional / GARD-style inheritance; template
copying is the follow-on og-34a). Fitness is GROUNDED in the real study-32/33
coupling: the composition trait sets membrane retention via the study-32 MD-informed
relation (short di-C12 retention ~0.333 -> long di-C16 ~0.661), and higher retention
raises the standing pool and so the division rate (study 33) = fitness. So selection
acts on a trait with a real mechanistic fitness consequence through the merged
machinery, not a toy fitness function.

``inheritance=True`` inherits the parent composition + heritable noise; ``False`` is
the matched NO-INHERITANCE null (daughters reset to the common/population composition,
breaking the parent-offspring link). The vasas-2010 evolvability caveat is TESTED
(does the inheriting population actually shift above the null?), not assumed. The
metabolism is the sustained A1 carbon-fixing network, not autocatalytic (A2 refuted).

Thin wrapper over :class:`~viva_genesis.compartments.heredity_population.HeredityPopulationProcess`
(one update = one generation); the feed/porosity parameters document the vent
metabolic regime whose study-32 retention endpoints ground fitness.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core


@composite_generator(
    name="og_34_chemical_heredity_and_selection",
    methods=["inherited network-composition trait (compositional / GARD-style)",
             "fitness grounded in study-32/33 retention -> division-rate coupling",
             "Wright-Fisher selection vs a matched no-inheritance null",
             "vasas-2010 evolvability caveat tested, not assumed"],
    fidelity="real",
    description=(
        "Gate D second half: selection on an inherited NETWORK COMPOSITION trait in a protocell population "
        "(⚑3 Option B; template copying = follow-on og-34a). Fitness is grounded in the real study-32/33 "
        "coupling (composition -> membrane retention [study-32 MD endpoints 0.333/0.661] -> standing pool -> "
        "division rate). inheritance=False is the matched no-inheritance null (daughters reset to the common "
        "composition). Reports parent-offspring fitness correlation + population composition shift; the "
        "vasas-2010 evolvability caveat is TESTED (does the population shift above the null?), not assumed. "
        "Metabolism = sustained A1 network, NOT autocatalytic (A2 refuted)."
    ),
    parameters={
        "inheritance": {"type": "boolean", "default": True,
                        "description": "Inherit parent composition (True) vs no-inheritance null (False)"},
        "n_pop": {"type": "integer", "default": 80, "description": "Population size"},
        "sigma": {"type": "float", "default": 0.03, "description": "Heritable mutation std (declared, not tuned)"},
        "seed": {"type": "integer", "default": 7, "description": "RNG seed"},
        "base_CO2": {"type": "float", "default": 1.0e-3, "description": "Vent feed (provenance for the fitness regime)"},
        "base_H2": {"type": "float", "default": 1.0e-3, "description": "Vent feed (provenance for the fitness regime)"},
        "porosity": {"type": "float", "default": 0.88, "description": "Gate-B pore porosity (provenance)"},
        "max_carbons": {"type": "integer", "default": 4, "description": "Carbon cap (provenance)"},
    },
    default_n_steps=40,
    preferred_time="2 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter",
               "paths": ["pop/parent_offspring_fitness_correlation", "pop/population_composition_shift",
                         "pop/mean_composition", "pop/selection_response"]}],
)
def og_34_chemical_heredity_and_selection(
        core=None, *, inheritance=True, n_pop=80, sigma=0.03, seed=7,
        base_CO2=1.0e-3, base_H2=1.0e-3, porosity=0.88, max_carbons=4):
    if core is None:
        core = build_core()
    doc = {
        "population": {
            "_type": "process",
            "address": "local:HeredityPopulationProcess",
            "config": {"inheritance": bool(inheritance), "n_pop": int(n_pop),
                       "sigma": float(sigma), "seed": int(seed)},
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
    }
    return doc
