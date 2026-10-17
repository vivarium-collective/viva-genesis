"""Campaign VI composite — heredity as an agent-based LINEAGE (og-06 deep model).

Where ``heredity_module_comparison`` runs the mean-field quasispecies ODE (populations
of correct vs error templates), this composite runs the agent-based lineage model
(``LineageReplicatorProcess``): individuals that divide into a real lineage tree, each
carrying a chemical phenotype inherited at fission with a MODULE-SPECIFIC mechanism.
One parameterized generator drives every heredity module — the study's "do NOT presume
RNA":

  - template      : RNA-like sequence; Eigen ratchet (Q = fidelity^length). Above the
                    error threshold it persists; a long low-fidelity template collapses.
  - compositional : GARD (Segré 2000) — an autocatalytic composition inherited by
                    multinomial fission split, NO template, length-independent.
  - hybrid        : a short template focuses the compositional attractor (cheap +
                    heritable).
  - non-heritable : daughters get a fresh random phenotype — the control.

Emits the population mean function, functional fraction, size, lineage depth and the
realized heritability. ``module`` picks the mechanism; the phenotype tree is exposed to
the Decision view via ``LineageReplicatorProcess.lineage_state()``.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

_EMIT_PATHS = [
    "herd/mean_function", "herd/functional_fraction", "herd/population",
    "herd/lineage_depth", "herd/heritability",
    "env/temperature",
    "global_time",
]


@composite_generator(
    name="heredity_lineage_comparison",
    methods=["agent-based lineage model"],
    fidelity="reproduction",
    description=(
        "A reusable agent-based heredity-lineage comparison (Module K). Individuals carry "
        "a chemical phenotype inherited at fission into a real lineage tree, with a module-"
        "specific mechanism: template Eigen ratchet (Q=fidelity^length), compositional GARD "
        "split (length-independent, no template), a template-focused hybrid, or a severed "
        "non-heritable control. Emits population mean function, functional fraction, size, "
        "lineage depth and realized heritability. Reproduces the Eigen error catastrophe at "
        "the agent level AND shows compositional heredity escaping the length catastrophe — "
        "heredity need not presume a long high-fidelity template."
    ),
    parameters={
        "module": {"type": "string", "default": "template",
                   "description": "Heredity module: template | compositional | hybrid | non-heritable"},
        "per_site_fidelity": {"type": "float", "default": 0.99, "description": "Per-site replication fidelity (template/hybrid)"},
        "length": {"type": "integer", "default": 30, "description": "Template length (template/hybrid cost driver)"},
        "temperature": {"type": "float", "default": 353.15, "description": "Temperature (K; ~80 C vent)"},
        "seed": {"type": "integer", "default": 1, "description": "RNG seed (reproducible lineage)"},
    },
    visualizations=[
        {"name": "heredity-lineage-tree", "address": "local:HeredityLineageTree",
         "config": {"title": "Heredity as an inherited lineage"}},
    ],
    default_n_steps=40,
    preferred_time="40 generations",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def heredity_lineage_comparison(core=None, *, module="template", per_site_fidelity=0.99,
                                length=30, temperature=353.15, seed=1):
    return {
        "herd_proc": {
            "_type": "process",
            "address": "local:LineageReplicatorProcess",
            "config": {"module": module, "per_site_fidelity": per_site_fidelity,
                       "length": length, "seed": seed},
            "interval": 1.0,
            "inputs": {"temperature": ["env", "temperature"]},
            "outputs": {"mean_function": ["herd", "mean_function"],
                        "functional_fraction": ["herd", "functional_fraction"],
                        "population": ["herd", "population"],
                        "lineage_depth": ["herd", "lineage_depth"],
                        "heritability": ["herd", "heritability"]},
        },
        "env": {"temperature": temperature},
        "herd": {"mean_function": 0.0, "functional_fraction": 0.0, "population": 0,
                 "lineage_depth": 0, "heritability": 0.0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {"mean_function": "float", "functional_fraction": "float",
                                "population": "integer", "lineage_depth": "integer",
                                "heritability": "float", "temperature": "float",
                                "global_time": "float"}},
            "inputs": {"mean_function": ["herd", "mean_function"],
                       "functional_fraction": ["herd", "functional_fraction"],
                       "population": ["herd", "population"],
                       "lineage_depth": ["herd", "lineage_depth"],
                       "heritability": ["herd", "heritability"],
                       "temperature": ["env", "temperature"],
                       "global_time": ["global_time"]},
        },
    }
