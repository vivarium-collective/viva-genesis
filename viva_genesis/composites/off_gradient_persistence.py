"""Campaign VIII composite — escape from the vent (og-08).

A reusable off-gradient-persistence module: a lineage's co-limited free-energy +
resource budget (``OffGradientPersistenceProcess``) under relaxing geological support
(``EnvironmentalRelaxationProcess``). As the external gradient, mineral access and
feed are withdrawn over the run, the lineage persists only if its innovation set keeps
the budget above the survival floor. One parameterized generator drives every study
arm:

  - full set (pump + importer + heredity) : persists as support -> 0 (autonomous)
  - knockout (-pump / -importer / -heredity) : collapses when support is withdrawn
                                               (obligately vent-tied)

``has_pump`` / ``has_importer`` / ``has_heredity`` select the arm. Emits survivors,
lineage fitness, free-energy flux, machinery integrity and the external/internal power
provenance. Coarse-grained, deterministic (reproducible).
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

_EMIT_PATHS = [
    "pop/survivors", "pop/lineage_fitness", "pop/free_energy_flux",
    "pop/machinery_integrity", "pop/external_power", "pop/internal_power",
    "env/gradient_support", "env/mineral_access", "env/feed",
    "global_time",
]


@composite_generator(
    name="off_gradient_persistence",
    description=(
        "A reusable off-gradient-persistence module (Module M). A lineage's co-limited "
        "(Liebig-minimum) free-energy + resource budget under relaxing geological support "
        "(external gradient, mineral access, feed all declining over the run), with three "
        "toggleable innovations: internal energy conversion (has_pump), active resource "
        "import (has_importer) and information maintenance (has_heredity). Because the "
        "budget is co-limited the innovation set is irreducible — as support -> 0 only the "
        "full set keeps net budget above the survival floor, so a knockout sweep identifies "
        "{pump, importer, heredity} as the minimum robust set for autonomy. Coarse-grained, "
        "deterministic reproduction (not a wrapped ALife engine)."
    ),
    parameters={
        "gradient_support": {"type": "float", "default": 1.0,
                             "description": "Starting external-gradient support, relaxed to 0 over the run (dimensionless, 0-1)"},
        "mineral_access": {"type": "float", "default": 1.0,
                           "description": "Starting mineral / FeS-catalyst access, relaxed to 0 (dimensionless, 0-1)"},
        "feed": {"type": "float", "default": 1.0,
                 "description": "Starting geochemical feed, relaxed to 0 (dimensionless, 0-1)"},
        "has_pump": {"type": "float", "default": 1.0,
                     "description": "Internal energy conversion innovation (1 present; 0 knockout)"},
        "has_importer": {"type": "float", "default": 1.0,
                         "description": "Active resource-import innovation (1 present; 0 knockout)"},
        "has_heredity": {"type": "float", "default": 1.0,
                         "description": "Information-maintenance innovation; without it the machinery degrades (1 present; 0 knockout)"},
        "catalyst_efficiency": {"type": "float", "default": 1.0,
                                "description": "Internal-pump catalytic efficiency (dimensionless)"},
        "decline_rate": {"type": "float", "default": 0.02,
                         "description": "Support relaxation per step (1/s); support reaches 0 partway through the run"},
    },
    visualizations=[
        {"name": "off-gradient-survival-frontier", "address": "local:OffGradientPhaseMap",
         "config": {"title": "Campaign VIII — the survival frontier off the gradient"}},
    ],
    default_n_steps=60,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def off_gradient_persistence(core=None, *, gradient_support=1.0, mineral_access=1.0,
                             feed=1.0, has_pump=1.0, has_importer=1.0, has_heredity=1.0,
                             catalyst_efficiency=1.0, decline_rate=0.02):
    # Translate the numeric 0/1 toggles to "on"/"off" strings: a process-bigraph
    # config schema replaces a falsy (0.0) value with its default, so numeric
    # knockouts would silently read back as present. Strings are preserved.
    def _tog(v):
        return "on" if float(v) >= 0.5 else "off"

    return {
        "relax": {
            "_type": "process",
            "address": "local:EnvironmentalRelaxationProcess",
            "config": {"g_start": gradient_support, "m_start": mineral_access,
                       "f_start": feed, "decline_rate": decline_rate},
            "interval": 1.0,
            "inputs": {},
            "outputs": {"gradient_support": ["env", "gradient_support"],
                        "mineral_access": ["env", "mineral_access"],
                        "feed": ["env", "feed"]},
        },
        "lineage": {
            "_type": "process",
            "address": "local:OffGradientPersistenceProcess",
            "config": {"pump": _tog(has_pump), "importer": _tog(has_importer),
                       "heredity": _tog(has_heredity),
                       "catalyst_efficiency": catalyst_efficiency},
            "interval": 1.0,
            "inputs": {"gradient_support": ["env", "gradient_support"],
                       "mineral_access": ["env", "mineral_access"],
                       "feed": ["env", "feed"]},
            "outputs": {"survivors": ["pop", "survivors"],
                        "lineage_fitness": ["pop", "lineage_fitness"],
                        "free_energy_flux": ["pop", "free_energy_flux"],
                        "machinery_integrity": ["pop", "machinery_integrity"],
                        "external_power": ["pop", "external_power"],
                        "internal_power": ["pop", "internal_power"]},
        },
        "env": {"gradient_support": gradient_support, "mineral_access": mineral_access,
                "feed": feed},
        "pop": {"survivors": 1.0, "lineage_fitness": 0.0, "free_energy_flux": 0.0,
                "machinery_integrity": 1.0, "external_power": 0.0, "internal_power": 0.0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {"survivors": "float", "lineage_fitness": "float",
                                "free_energy_flux": "float", "machinery_integrity": "float",
                                "external_power": "float", "internal_power": "float",
                                "gradient_support": "float", "mineral_access": "float",
                                "feed": "float", "global_time": "float"}},
            "inputs": {"survivors": ["pop", "survivors"],
                       "lineage_fitness": ["pop", "lineage_fitness"],
                       "free_energy_flux": ["pop", "free_energy_flux"],
                       "machinery_integrity": ["pop", "machinery_integrity"],
                       "external_power": ["pop", "external_power"],
                       "internal_power": ["pop", "internal_power"],
                       "gradient_support": ["env", "gradient_support"],
                       "mineral_access": ["env", "mineral_access"],
                       "feed": ["env", "feed"],
                       "global_time": ["global_time"]},
        },
    }
