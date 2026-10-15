"""Swappable spatial-transport composites (full modeling plan sections 4.1/4.2
+ 4.5): the SAME world, either solver behind one ``spatial_transport`` face,
selected by the study param ``model_spatial_transport ∈ {"fipy", "fenics"}``.

Each generator resolves the transport class through :func:`viva_genesis.models`
and calls ``assert_face`` at build time (``resolve_checked``), so a class that
does not honour the face fails loudly before the Composite is constructed.
``"fipy"`` is the LIVE, default solver — a pure-Python FiPy FVM solve that runs
anywhere in the canonical ``.venv`` and backs every graded gate and sweep.
``"fenics"`` is the MERGED dolfinx FEM alternative (viva-fenics
``advection_diffusion_step`` — backward-Euler advection-diffusion with a
Soret-drift weak-form term + SUPG): a real high-fidelity solver used as a
structural cross-check, not a placeholder. It runs on demand under viva-fenics's
pixi env; dolfinx is conda-only, so it is not importable in the uv ``.venv`` —
selecting ``'fenics'`` there raises a clear "run under pixi" error, and the
FiPy↔FEniCS head-to-head (``scripts/compare_spatial_transport.py``, raw numbers in
``references/spatial-transport-solver-comparison.{md,json}``) is executed that way.
FEniCS is not wired into the live graded gates — FiPy grades, FEniCS cross-checks:
the two agree on smooth gates (og-00 outlet T within 0.30%) and the FEM exposes
where FiPy's reduced column over-extrapolates (og-03 above Pe ≈ 13).
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
    methods=["FiPy FVM (live default)", "dolfinx FEM (swappable)"],
    fidelity="real",
    description=(
        "og-03 thermophoretic trap behind the swappable spatial_transport face. "
        "The live, default solver is a genuine 1-D FiPy finite-volume accumulation "
        "column (model_spatial_transport='fipy', runs anywhere, backs every "
        "canonical run). The face also swaps in the MERGED dolfinx FEM solver with a "
        "Soret-drift weak-form term (model_spatial_transport='fenics') — a real "
        "high-fidelity cross-check, run on demand under viva-fenics's pixi env "
        "(dolfinx is conda-only, so in the uv venv 'fenics' raises a clear 'run under "
        "pixi' error). The FiPy↔FEniCS head-to-head on this trap was run that way and "
        "shows the two agree up to Pe_acc≈4 and diverge to ~5.6 decades by Pe_acc≈18, "
        "so the >1e6-fold column is a reduced-model extrapolation the resolved FEM does "
        "not confirm. assert_face is enforced at build. Same pore physics, FiPy grades "
        "and FEniCS cross-checks (plan 4.5)."
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
    methods=["FiPy FVM (live default)", "dolfinx FEM (swappable)"],
    fidelity="real",
    description=(
        "og-00 vent reactor transport behind the swappable spatial_transport "
        "face. The live, default solver is a genuine 2-D FiPy finite-volume "
        "advection-diffusion FVM (model_spatial_transport='fipy', backs every "
        "canonical run); the face swaps in the MERGED dolfinx FEM advection-diffusion "
        "solver (model_spatial_transport='fenics') — a real high-fidelity cross-check "
        "run on demand under viva-fenics's pixi env (dolfinx conda-only, so 'fenics' "
        "raises 'run under pixi' in the uv venv). The FiPy↔FEniCS head-to-head on this "
        "vent agrees to within 0.30% outlet T (identical pH, flux conserved ~1e-15), so "
        "the habitability result is solver-robust. Prescribed serpentinization drivers "
        "(H2/alkalinity/heat) isolate the transport solver; assert_face enforced at "
        "build. Same world, FiPy grades and FEniCS cross-checks (plan 4.5)."
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
