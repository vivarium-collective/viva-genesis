"""Campaign V composite — environmental to internal bioenergetics (og-05).

A reusable bioenergetic-internalization module: an evolutionary control loop
(``BioenergeticSelectionProcess``, replicator dynamics with Sojo-2014 leaky-membrane
fitness) under a declining external gradient (``EnvironmentalDeclineProcess``). As
the geochemical gradient collapses over the run, the population either INTERNALIZES
gradient generation (efficient pump → tight membrane) and persists, or — with a
weak pump — collapses (the Sojo constraint). One parameterized generator drives
every study condition:

  - favorable (efficient pump) : catalyst_efficiency=1.0 → internalizes + survives
  - weak-pump control          : catalyst_efficiency≈0.3 → collapses when the
                                 external gradient drops (cannot internalize)

Emits internalization, survivors, lineage fitness, free-energy flux and the
declining external potential. Coarse-grained, deterministic (reproducible).
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

_EMIT_PATHS = [
    "pop/internalization", "pop/survivors", "pop/lineage_fitness",
    "pop/free_energy_flux", "pop/mean_permeability",
    "env/electric_potential",
    "global_time",
]


@composite_generator(
    name="bioenergetic_internalization",
    description=(
        "A reusable bioenergetic-internalization module (Module H). An evolutionary "
        "control loop (replicator dynamics, Sojo-2014 leaky-membrane fitness) under a "
        "declining external gradient: as the geochemical pmf collapses, an efficient-pump "
        "population internalizes gradient generation and persists, while a weak-pump "
        "control collapses (the Sojo constraint). catalyst_efficiency sets the arm. "
        "Coarse-grained, deterministic reproduction (not wrapped ALife)."
    ),
    parameters={
        "catalyst_efficiency": {"type": "float", "default": 1.0,
                                "description": "Active-pump (Na+/H+) efficiency (1.0 efficient; ~0.3 weak-pump control)"},
        "v_start": {"type": "float", "default": 0.40, "description": "Initial external gradient (V)"},
        "decline_rate": {"type": "float", "default": 0.01, "description": "External-gradient decline per step (V/s)"},
        "gradient_floor": {"type": "float", "default": 0.02,
                           "description": "Floor the external gradient decays to (V); low floor forces internalization-or-die"},
    },
    visualizations=[
        {"name": "bioenergetic-internalization", "address": "local:BioenergeticInternalizationViz",
         "config": {"title": "Campaign V — selection internalizes the gradient"}},
    ],
    default_n_steps=40,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def bioenergetic_internalization(core=None, *, catalyst_efficiency=1.0,
                                 v_start=0.40, decline_rate=0.01, gradient_floor=0.02):
    return {
        "decline": {
            "_type": "process",
            "address": "local:EnvironmentalDeclineProcess",
            "config": {"v_start": v_start, "decline_rate": decline_rate,
                       "v_floor": gradient_floor},
            "interval": 1.0,
            "inputs": {},
            "outputs": {"electric_potential": ["env", "electric_potential"]},
        },
        "selection": {
            "_type": "process",
            "address": "local:BioenergeticSelectionProcess",
            "config": {},
            "interval": 1.0,
            "inputs": {"electric_potential": ["env", "electric_potential"],
                       "catalyst_efficiency": ["env", "catalyst_efficiency"]},
            "outputs": {"lineage_fitness": ["pop", "lineage_fitness"],
                        "free_energy_flux": ["pop", "free_energy_flux"],
                        "internalization": ["pop", "internalization"],
                        "mean_permeability": ["pop", "mean_permeability"],
                        "survivors": ["pop", "survivors"],
                        "external_power": ["pop", "external_power"],
                        "internal_power": ["pop", "internal_power"],
                        "maintenance_power": ["pop", "maintenance_power"]},
        },
        "env": {"electric_potential": v_start, "catalyst_efficiency": catalyst_efficiency},
        "pop": {"lineage_fitness": 0.0, "free_energy_flux": 0.0, "internalization": 0.0,
                "mean_permeability": 0.0, "survivors": 1.0,
                "external_power": 0.0, "internal_power": 0.0, "maintenance_power": 0.0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {"internalization": "float", "survivors": "float",
                                "lineage_fitness": "float", "free_energy_flux": "float",
                                "mean_permeability": "float", "electric_potential": "float",
                                "external_power": "float", "internal_power": "float",
                                "maintenance_power": "float", "global_time": "float"}},
            "inputs": {"internalization": ["pop", "internalization"],
                       "survivors": ["pop", "survivors"],
                       "lineage_fitness": ["pop", "lineage_fitness"],
                       "free_energy_flux": ["pop", "free_energy_flux"],
                       "mean_permeability": ["pop", "mean_permeability"],
                       "electric_potential": ["env", "electric_potential"],
                       "external_power": ["pop", "external_power"],
                       "internal_power": ["pop", "internal_power"],
                       "maintenance_power": ["pop", "maintenance_power"],
                       "global_time": ["global_time"]},
        },
    }
