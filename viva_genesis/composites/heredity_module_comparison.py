"""Campaign VI composite — chemistry to heredity (og-06).

A reusable heredity-module comparison: the real libRoadRunner quasispecies
replicator (``HeredityReplicatorProcess``, Eigen error threshold) run as a given
heredity MODULE and compared head-to-head. One parameterized generator drives
every condition:

  - RNA-like     : long, high-fidelity, costly template (the favorable module)
  - peptide      : shorter, cheaper, lower-fidelity (a viable alternative)
  - low-fidelity : below the error threshold → catastrophe (information lost)
  - non-heritable: k_rep≈0 → no inheritance (the function degrades away)

Emits information retention, functional templates, polymer length and lineage
fitness. ``module`` picks a preset; individual knobs override it.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

_EMIT_PATHS = [
    "herd/information_retention", "herd/functional_templates",
    "herd/polymer_length", "herd/lineage_fitness",
    "env/temperature",
    "global_time",
]

# Heredity-module presets (per_site_fidelity, polymer_length, k_rep, cost_per_rep).
_MODULES = {
    "rna-like": dict(per_site_fidelity=0.99, polymer_length=30, k_rep=1.0, cost_per_rep=0.10),
    "peptide": dict(per_site_fidelity=0.97, polymer_length=12, k_rep=0.7, cost_per_rep=0.04),
    "low-fidelity": dict(per_site_fidelity=0.90, polymer_length=30, k_rep=1.0, cost_per_rep=0.10),
    "non-heritable": dict(per_site_fidelity=0.99, polymer_length=30, k_rep=1.0e-6, cost_per_rep=0.10),
}


@composite_generator(
    name="heredity_module_comparison",
    description=(
        "A reusable heredity-module comparison (Module J). Genuine libRoadRunner "
        "quasispecies replicator (Eigen error threshold): a heredity module "
        "(RNA-like / peptide / low-fidelity / non-heritable) replicates a polymer with "
        "whole-sequence fidelity Q = fidelity^length; above the threshold the functional "
        "information is retained and inheritance pays, below it errors win. Compares "
        "modules head-to-head on lineage fitness. Requires tellurium/libroadrunner."
    ),
    parameters={
        "module": {"type": "string", "default": "rna-like",
                   "description": "Heredity-module preset: rna-like | peptide | low-fidelity | non-heritable"},
        "temperature": {"type": "float", "default": 353.15, "description": "Temperature (K; ~80 C vent)"},
    },
    default_n_steps=50,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def heredity_module_comparison(core=None, *, module="rna-like", temperature=353.15):
    cfg = dict(_MODULES.get(module, _MODULES["rna-like"]))
    return {
        "herd_proc": {
            "_type": "process",
            "address": "local:HeredityReplicatorProcess",
            "config": cfg,
            "interval": 1.0,
            "inputs": {"temperature": ["env", "temperature"]},
            "outputs": {"information_retention": ["herd", "information_retention"],
                        "functional_templates": ["herd", "functional_templates"],
                        "polymer_length": ["herd", "polymer_length"],
                        "lineage_fitness": ["herd", "lineage_fitness"]},
        },
        "env": {"temperature": temperature},
        "herd": {"information_retention": 0.0, "functional_templates": 0.0,
                 "polymer_length": 1, "lineage_fitness": 0.0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {"information_retention": "float", "functional_templates": "float",
                                "polymer_length": "integer", "lineage_fitness": "float",
                                "temperature": "float", "global_time": "float"}},
            "inputs": {"information_retention": ["herd", "information_retention"],
                       "functional_templates": ["herd", "functional_templates"],
                       "polymer_length": ["herd", "polymer_length"],
                       "lineage_fitness": ["herd", "lineage_fitness"],
                       "temperature": ["env", "temperature"],
                       "global_time": ["global_time"]},
        },
    }
