"""Study 27 — Coupled Geochemical Reaction Interface (the evolving mineral-water wall).

Extends the Phase-1 ``geochemical_world`` (real PHREEQC speciation feeding a real
FiPy finite-volume transport solve) with ``MineralSurfaceDynamicsProcess`` so the
interface EVOLVES: the reacted alkaline fluid's carbonate saturation index (a real
``PHREEQC`` output) drives precipitation/dissolution, which (a) changes porosity —
a delta that composes additively with FiPy's own transport-driven porosity change —
and (b) passivates the catalytic surface over time.

This is the upgrade plan's study-27 question: *can an evolving mineral-water
interface sustainably supply carbon, H2, chemical gradients and catalysis, and over
what timescale before mineral evolution chokes the supply?* The composite is built
by REUSING ``geochemical_world`` and augmenting its document — no duplication of the
PHREEQC/FiPy/ledger wiring — so the coupling stays in one place and the mineral
layer is a clean add-on reusable by study 30.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from .geochemical_world import geochemical_world, _EMIT_TYPES, _EMIT_WIRES, _EMIT_PATHS

# Extra observables the evolving interface adds on top of geochemical_world.
_MINERAL_EMIT_TYPES = {
    "catalytic_accessibility": "float", "reactive_surface_area": "float",
    "mineral_precipitation": "float", "saturation_index": "float",
    "mineral_mass_residual": "float",
}
_MINERAL_EMIT_WIRES = {
    "catalytic_accessibility": ["surface", "catalytic_accessibility"],
    "reactive_surface_area": ["surface", "reactive_surface_area"],
    "mineral_precipitation": ["surface", "mineral_precipitation"],
    "saturation_index": ["diagnostics", "saturation_index"],
    "mineral_mass_residual": ["diagnostics", "mineral_mass_residual"],
}
_MINERAL_EMIT_PATHS = [
    "surface/catalytic_accessibility", "surface/reactive_surface_area",
    "surface/mineral_precipitation",
    "diagnostics/saturation_index", "diagnostics/mineral_mass_residual",
]


@composite_generator(
    name="og_27_coupled_geochemical_reaction_interface",
    methods=["PHREEQC speciation (IPhreeqc)", "FiPy FVM advection-diffusion-reaction",
             "mineral surface dynamics (precipitation/dissolution/passivation)",
             "conservation ledger"],
    fidelity="real",
    description=(
        "Study 27: og-00's real serpentinizing vent made into an EVOLVING interface. "
        "geochemical_world (genuine PHREEQC speciation -> genuine FiPy transport) is "
        "augmented with MineralSurfaceDynamicsProcess: the reacted fluid's real carbonate "
        "saturation index drives precipitation/dissolution (a porosity delta that composes "
        "with FiPy's) and passivates the catalytic surface over time. Reports time- and "
        "space-resolved supply of H2/carbon/gradients/catalysis and the crossover time at "
        "which mineral evolution throttles it, with closed mass/charge/energy ledgers."
    ),
    parameters={
        "flow_velocity": {"type": "float", "default": 1.0e-3,
                          "description": "Boundary water flux through the reaction zone (m/s)"},
        "olivine_rate": {"type": "float", "default": 0.15,
                         "description": "Olivine reaction extent per flow-saturated step"},
        "fluid_dic": {"type": "float", "default": 2.0e-3,
                      "description": "Inflowing-fluid DIC, Hadean-ocean proxy (molar)"},
        "nx": {"type": "integer", "default": 40,
               "description": "FiPy finite-volume cells across the interface column"},
        "k_precip": {"type": "float", "default": 0.05,
                     "description": "Precipitation rate coefficient (pore clogging, 1/s)"},
        "k_dissolve": {"type": "float", "default": 0.02,
                       "description": "Dissolution rate coefficient (pore opening, 1/s)"},
        "k_passivate": {"type": "float", "default": 0.5,
                        "description": "Catalytic passivation coefficient under precipitation"},
    },
    default_n_steps=120,
    preferred_time="6 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS + _MINERAL_EMIT_PATHS}],
)
def og_27_coupled_geochemical_reaction_interface(
        core=None, *, flow_velocity=1.0e-3, olivine_rate=0.15, fluid_dic=2.0e-3,
        nx=40, k_precip=0.05, k_dissolve=0.02, k_passivate=0.5):
    if core is None:
        core = build_core()

    # Reuse the real PHREEQC->FiPy coupling verbatim (phreeqc arm — the evolving
    # interface needs genuine speciation to produce the saturation index).
    doc = geochemical_world(
        core, model_serpentinization="phreeqc", model_spatial_transport="fipy",
        flow_velocity=flow_velocity, olivine_rate=olivine_rate, fluid_dic=fluid_dic, nx=nx)

    # 1. Route the PHREEQC carbonate saturation index into a diagnostics store.
    doc["serpentinization"]["outputs"]["saturation_index"] = ["diagnostics", "saturation_index"]
    doc["diagnostics"]["saturation_index"] = 0.0
    doc["diagnostics"]["mineral_mass_residual"] = 0.0

    # 2. The evolving-surface state store.
    doc["surface"] = {
        "catalytic_accessibility": 1.0,
        "reactive_surface_area": 0.0,
        "mineral_precipitation": 0.0,
    }

    # 3. The mineral dynamics process — its porosity delta composes with the
    #    transport's porosity (same store), so the two contributions sum.
    doc["mineral_surface"] = {
        "_type": "process",
        "address": "local:MineralSurfaceDynamicsProcess",
        "config": {"k_precip": float(k_precip), "k_dissolve": float(k_dissolve),
                   "k_passivate": float(k_passivate)},
        "interval": 1.0,
        "inputs": {
            "saturation_index": ["diagnostics", "saturation_index"],
            "temperature": ["vent", "temperature"],
            "flow_velocity": ["boundary", "flow_velocity"],
            "porosity": ["vent", "porosity"],
            "catalytic_accessibility": ["surface", "catalytic_accessibility"],
        },
        "outputs": {
            "porosity": ["vent", "porosity"],                         # DELTA (composes with FiPy)
            "catalytic_accessibility": ["surface", "catalytic_accessibility"],
            "reactive_surface_area": ["surface", "reactive_surface_area"],
            "mineral_precipitation": ["surface", "mineral_precipitation"],
            "mineral_mass_residual": ["diagnostics", "mineral_mass_residual"],
        },
    }

    # 4. Extend both emitters to record the evolving-interface observables.
    doc["emitter"]["config"]["emit"] = {**_EMIT_TYPES, **_MINERAL_EMIT_TYPES}
    doc["emitter"]["inputs"] = {**_EMIT_WIRES, **_MINERAL_EMIT_WIRES}

    return doc
