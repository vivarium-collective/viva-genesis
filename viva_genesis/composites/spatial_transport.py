"""Swappable spatial-transport composites (full modeling plan sections 4.1/4.2
+ 4.5): the SAME world, either solver behind one ``spatial_transport`` face,
selected by the study param ``model_spatial_transport ∈ {"fipy", "fenics"}``.

Each generator resolves the transport class through :func:`viva_genesis.models`
and calls ``assert_face`` at build time (``resolve_checked``), so a class that
does not honour the face fails loudly before the Composite is constructed.
``"fipy"`` is the LIVE, default solver — a pure-Python FiPy FVM solve that runs
anywhere and backs every canonical run. ``"fenics"`` names the swappable dolfinx
FEM alternative: that class only *registers* today (so ``models.resolve`` /
``assert_face`` and the dashboard see it), but is NOT yet active — the dolfinx
solver extension lives on a held branch and dolfinx is conda-only, so selecting
it raises a clear "run under pixi" error in the canonical ``.venv``. The face
exists so the FEM solver can be swapped in and compared once it lands.
"""

from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from .. import models

_TRAP_EMIT = [
    "trap/enrichment_factor", "trap/accumulation_peclet", "trap/residence_time",
    "trap/flux_divergence_residual", "global_time",
]


@composite_generator(
    name="spatial_transport_trap",
    description=(
        "og-03 thermophoretic trap behind the swappable spatial_transport face. "
        "The live, default solver is a genuine 1-D FiPy finite-volume accumulation "
        "column (model_spatial_transport='fipy', runs anywhere, backs every "
        "canonical run). The face also lets you swap in a dolfinx FEM solver with a "
        "Soret-drift weak-form term (model_spatial_transport='fenics') — that class "
        "only registers today and is not yet active (dolfinx is conda-only and its "
        "solver extension is on a held branch, so it raises a 'run under pixi' "
        "error in the canonical venv). assert_face is enforced at build. Same pore "
        "physics, one live solver plus a swappable FEM alternative (plan 4.5)."
    ),
    parameters={
        "model_spatial_transport": {"type": "string", "default": "fipy",
                                    "description": "Solver behind the face: 'fipy' | 'fenics'"},
        "flow_velocity": {"type": "float", "default": 1.0e-4,
                          "description": "Buoyant convective flow in the pore (m/s); 0 = no-convection control"},
        "porosity": {"type": "float", "default": 0.3,
                     "description": "Pore porosity/openness (0-1); ~1 = open-pore control"},
        "temperature": {"type": "float", "default": 333.15, "description": "Mean pore temperature (K)"},
        "pore_length": {"type": "float", "default": 5.0e-3, "description": "Pore length (m)"},
        "delta_T": {"type": "float", "default": 30.0, "description": "Cross-pore temperature difference (K)"},
    },
    default_n_steps=20,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _TRAP_EMIT}],
)
def spatial_transport_trap(core=None, *, model_spatial_transport="fipy",
                           flow_velocity=1.0e-4, porosity=0.3, temperature=333.15,
                           pore_length=5.0e-3, delta_T=30.0):
    if core is None:
        core = build_core()
    address = models.resolve_checked(core, "localization", model_spatial_transport)
    return {
        "pore": {
            "_type": "process",
            "address": address,
            "config": {"pore_length": pore_length, "delta_T": delta_T},
            "interval": 1.0,
            "inputs": {"temperature": ["env", "temperature"],
                       "flow_velocity": ["env", "flow_velocity"],
                       "porosity": ["env", "porosity"]},
            "outputs": {"enrichment_factor": ["trap", "enrichment_factor"],
                        "accumulation_peclet": ["trap", "accumulation_peclet"],
                        "residence_time": ["trap", "residence_time"],
                        "flux_divergence_residual": ["trap", "flux_divergence_residual"]},
        },
        "env": {"temperature": temperature, "flow_velocity": flow_velocity, "porosity": porosity},
        "trap": {"enrichment_factor": 1.0, "accumulation_peclet": 0.0,
                 "residence_time": 0.0, "flux_divergence_residual": 0.0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {"enrichment_factor": "float", "accumulation_peclet": "float",
                                "residence_time": "float", "flux_divergence_residual": "float",
                                "global_time": "float"}},
            "inputs": {"enrichment_factor": ["trap", "enrichment_factor"],
                       "accumulation_peclet": ["trap", "accumulation_peclet"],
                       "residence_time": ["trap", "residence_time"],
                       "flux_divergence_residual": ["trap", "flux_divergence_residual"],
                       "global_time": ["global_time"]},
        },
    }


_VENT_EMIT = [
    "vent/temperature", "vent/pH", "vent/porosity",
    "diagnostics/flux_divergence_residual", "global_time",
]


@composite_generator(
    name="spatial_transport_vent",
    description=(
        "og-00 vent reactor transport behind the swappable spatial_transport "
        "face. The live, default solver is a genuine 2-D FiPy finite-volume "
        "advection-diffusion FVM (model_spatial_transport='fipy', backs every "
        "canonical run); the face can swap in a dolfinx FEM advection-diffusion "
        "solver (model_spatial_transport='fenics'), which only registers today and "
        "is not yet active (solver extension on a held branch, dolfinx conda-only, "
        "raises 'run under pixi' in the canonical venv). Prescribed serpentinization "
        "drivers (H2/alkalinity/heat) isolate the transport solver; assert_face "
        "enforced at build. Same world, one live solver plus a swappable FEM "
        "alternative (plan 4.5)."
    ),
    parameters={
        "model_spatial_transport": {"type": "string", "default": "fipy",
                                    "description": "Solver behind the face: 'fipy' | 'fenics'"},
        "flow_velocity": {"type": "float", "default": 1.0e-3,
                          "description": "Boundary water flux through the reaction zone (m/s)"},
        "H2": {"type": "float", "default": 5.0e-3, "description": "Prescribed H2 source (molar)"},
        "alkalinity": {"type": "float", "default": 3.0e-3, "description": "Prescribed alkalinity source (molar)"},
        "heat": {"type": "float", "default": 12.0, "description": "Prescribed heat source (W)"},
        "pH_eq": {"type": "float", "default": 10.5, "description": "Serpentinized source equilibrium pH"},
    },
    default_n_steps=60,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _VENT_EMIT}],
)
def spatial_transport_vent(core=None, *, model_spatial_transport="fipy",
                           flow_velocity=1.0e-3, H2=5.0e-3, alkalinity=3.0e-3,
                           heat=12.0, pH_eq=10.5):
    if core is None:
        core = build_core()
    address = models.resolve_checked(core, "spatial_transport", model_spatial_transport)
    return {
        "reactor": {
            "_type": "process",
            "address": address,
            "config": {},
            "interval": 1.0,
            "inputs": {"temperature": ["vent", "temperature"], "pH": ["vent", "pH"],
                       "porosity": ["vent", "porosity"], "H2": ["vent", "H2"],
                       "alkalinity": ["vent", "alkalinity"], "heat": ["vent", "heat"],
                       "flow_velocity": ["boundary", "flow_velocity"],
                       "pH_eq": ["chem", "pH_eq"]},
            "outputs": {"temperature": ["vent", "temperature"], "pH": ["vent", "pH"],
                        "porosity": ["vent", "porosity"],
                        "flux_divergence_residual": ["diagnostics", "flux_divergence_residual"]},
        },
        "vent": {"temperature": 300.0, "pH": 7.0, "porosity": 0.35,
                 "H2": H2, "alkalinity": alkalinity, "heat": heat},
        "chem": {"pH_eq": pH_eq},
        "boundary": {"flow_velocity": flow_velocity},
        "diagnostics": {"flux_divergence_residual": 0.0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {"temperature": "float", "pH": "float", "porosity": "float",
                                "flux_divergence_residual": "float", "global_time": "float"}},
            "inputs": {"temperature": ["vent", "temperature"], "pH": ["vent", "pH"],
                       "porosity": ["vent", "porosity"],
                       "flux_divergence_residual": ["diagnostics", "flux_divergence_residual"],
                       "global_time": ["global_time"]},
        },
    }
