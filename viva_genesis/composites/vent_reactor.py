"""Campaign 0 composites — the vent-reactor baseline.

``serpentinizing_vent_reactor`` is the **real coupled model**: Module A
(:class:`~viva_genesis.geochemistry.phreeqc_serpentinization.PhreeqcSerpentinizationProcess`
— genuine PHREEQC speciation + mineral equilibrium) feeds H2 / alkalinity / heat
source fluxes into Module B
(:class:`~viva_genesis.transport.fipy_reactor.FipyReactiveTransportProcess` —
a real FiPy finite-volume advection–diffusion–reaction column) through shared
``vent`` / ``rates`` / ``diagnostics`` stores. PHREEQC conserves elements + charge
and FiPy's FVM conserves flux by construction, so the composite satisfies the
og-00 contract invariants (``mass_balance``, ``charge_neutrality``,
``spatial_flux_conservation``). Requires ``phreeqpython`` + ``fipy`` installed.

``serpentinizing_vent_reactor_reduced`` is the original tuned-relaxation reproduction
(``SerpentinizationReproductionProcess`` → ``VentReactorReproductionProcess``),
kept as a runs-anywhere fallback / A-B comparison baseline.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

# Observables persisted by the real baseline (ParquetEmitter) — at minimum every
# store path a behavior_test's derived readout reduces over.
_REAL_EMIT_PATHS = [
    "vent/temperature", "vent/pH", "vent/porosity", "vent/H2", "vent/alkalinity",
    "rates/H2_flux", "rates/alkalinity_flux",
    "diagnostics/pe", "diagnostics/charge_imbalance", "diagnostics/flux_divergence_residual",
    "global_time",
]


@composite_generator(
    name="serpentinizing_vent_reactor",
    visualizations=[
        {"name": "vent-cross-section", "address": "local:VentCrossSection",
         "config": {"n_steps": 60, "title": "Campaign 0 — real 2-D vent cross-section (FiPy)"}},
        {"name": "vent-reactor-timeseries", "address": "local:VentReactorTimeseries",
         "config": {"n_steps": 120, "title": "Campaign 0 — real vent reactor (PHREEQC + FiPy)"}},
    ],
    description=(
        "A reusable alkaline-vent reactor module. Module A = genuine PHREEQC "
        "serpentinization (phreeqpython + vendored llnl.dat): olivine dissolution "
        "+ serpentine/brucite/magnetite equilibrium gives dissolved H2 (reducing "
        "power), alkalinity, heat, pe, and a charge-balanced fluid. Module B = "
        "genuine FiPy finite-volume advection-diffusion-reaction column transporting "
        "those sources across the vent-ocean interface and setting outlet T/pH/porosity. "
        "PHREEQC conserves mass+charge and FiPy's FVM conserves flux, satisfying the "
        "og-00 contract invariants. Requires phreeqpython + fipy."
    ),
    parameters={
        "flow_velocity": {"type": "float", "default": 1.0e-3,
                          "description": "Boundary water flux through the reaction zone (m/s)"},
        "olivine_rate": {"type": "float", "default": 0.15,
                         "description": "Olivine dissolution rate (mol per flow-saturated reaction step)"},
        "nx": {"type": "integer", "default": 40,
               "description": "FiPy finite-volume cells across the interface column"},
    },
    default_n_steps=120,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _REAL_EMIT_PATHS}],
)
def serpentinizing_vent_reactor(core=None, *, flow_velocity=1.0e-3, olivine_rate=0.15, nx=40):
    return {
        "serpentinization": {
            "_type": "process",
            "address": "local:PhreeqcSerpentinizationProcess",
            "config": {"olivine_rate": olivine_rate},
            "interval": 1.0,
            "inputs": {"temperature": ["vent", "temperature"],
                       "flow_velocity": ["boundary", "flow_velocity"],
                       "DIC": ["vent", "DIC"]},
            "outputs": {"H2": ["vent", "H2"], "alkalinity": ["vent", "alkalinity"],
                        "heat": ["vent", "heat"],
                        "H2_flux": ["rates", "H2_flux"],
                        "alkalinity_flux": ["rates", "alkalinity_flux"],
                        "heat_flux": ["rates", "heat_flux"],
                        "pe": ["diagnostics", "pe"],
                        "pH_eq": ["chem", "pH_eq"],
                        "charge_imbalance": ["diagnostics", "charge_imbalance"]},
        },
        "reactor": {
            "_type": "process",
            "address": "local:FipyReactiveTransportProcess",
            "config": {"nx": nx},
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
                 "H2": 0.0, "alkalinity": 0.0, "heat": 0.0, "DIC": 2.0e-3},
        "chem": {"pH_eq": 0.0},
        "boundary": {"flow_velocity": flow_velocity},
        "rates": {"H2_flux": 0.0, "alkalinity_flux": 0.0, "heat_flux": 0.0},
        "diagnostics": {"pe": 0.0, "charge_imbalance": 0.0, "flux_divergence_residual": 0.0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {"temperature": "float", "pH": "float", "porosity": "float",
                                "H2": "float", "alkalinity": "float",
                                "H2_flux": "float", "alkalinity_flux": "float",
                                "pe": "float", "charge_imbalance": "float",
                                "flux_divergence_residual": "float",
                                "global_time": "float"}},
            "inputs": {"temperature": ["vent", "temperature"], "pH": ["vent", "pH"],
                       "porosity": ["vent", "porosity"], "H2": ["vent", "H2"],
                       "alkalinity": ["vent", "alkalinity"],
                       "H2_flux": ["rates", "H2_flux"], "alkalinity_flux": ["rates", "alkalinity_flux"],
                       "pe": ["diagnostics", "pe"], "charge_imbalance": ["diagnostics", "charge_imbalance"],
                       "flux_divergence_residual": ["diagnostics", "flux_divergence_residual"],
                       "global_time": ["global_time"]},
        },
    }


@composite_generator(
    name="serpentinizing_vent_reactor_reduced",
    visualizations=[
        {"name": "vent-cross-section", "address": "local:VentCrossSection",
         "config": {"n_steps": 40, "title": "Campaign 0 — vent cross-section (reduced, FiPy)"}},
        {"name": "vent-reactor-timeseries", "address": "local:VentReactorTimeseries",
         "config": {"n_steps": 60, "title": "Campaign 0 — vent reactor (reduced)"}},
    ],
    description="Reduced tuned-relaxation vent reactor (fallback / A-B "
                "comparison): Gaussian serpentinization source feeding a first-order "
                "relaxation box. Runs anywhere (no phreeqpython/fipy). NOT real geochemistry.",
    parameters={
        "flow_velocity": {"type": "float", "default": 1.0e-3,
                          "description": "Boundary water flux through the reaction zone (m/s)"},
        "t_target": {"type": "float", "default": 340.0,
                     "description": "Mixing-target temperature (K); Lost City mid-window ~340 K"},
        "h2_rate_max": {"type": "float", "default": 1.0e-3,
                        "description": "Peak H2 source rate at reference flow (mol/s)"},
    },
    default_n_steps=120,
    core_extensions=[build_core],
    emitters=[{
        "address": "local:ParquetEmitter",
        "paths": [
            "vent/temperature", "vent/pH", "vent/porosity",
            "vent/H2", "vent/alkalinity",
            "rates/H2_flux", "rates/alkalinity_flux",
            "global_time",
        ],
    }],
)
def serpentinizing_vent_reactor_reduced(core=None, *, flow_velocity=1.0e-3, t_target=340.0, h2_rate_max=1.0e-3):
    return {
        "serpentinization": {
            "_type": "process",
            "address": "local:SerpentinizationReproductionProcess",
            "config": {"h2_rate_max": h2_rate_max},
            "interval": 1.0,
            "inputs": {"temperature": ["vent", "temperature"],
                       "flow_velocity": ["boundary", "flow_velocity"]},
            "outputs": {"H2": ["vent", "H2"], "alkalinity": ["vent", "alkalinity"],
                        "heat": ["vent", "heat"], "H2_flux": ["rates", "H2_flux"],
                        "alkalinity_flux": ["rates", "alkalinity_flux"],
                        "heat_flux": ["rates", "heat_flux"]},
        },
        "reactor": {
            "_type": "process",
            "address": "local:VentReactorReproductionProcess",
            "config": {"t_target": t_target},
            "interval": 1.0,
            "inputs": {"temperature": ["vent", "temperature"], "pH": ["vent", "pH"],
                       "porosity": ["vent", "porosity"], "H2": ["vent", "H2"],
                       "alkalinity": ["vent", "alkalinity"], "heat": ["vent", "heat"]},
            "outputs": {"temperature": ["vent", "temperature"], "pH": ["vent", "pH"],
                        "porosity": ["vent", "porosity"]},
        },
        "vent": {"temperature": 300.0, "pH": 7.2, "porosity": 0.35,
                 "H2": 0.0, "alkalinity": 0.0, "heat": 0.0},
        "boundary": {"flow_velocity": flow_velocity},
        "rates": {"H2_flux": 0.0, "alkalinity_flux": 0.0, "heat_flux": 0.0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {"temperature": "float", "pH": "float", "porosity": "float",
                                "H2": "float", "alkalinity": "float",
                                "H2_flux": "float", "alkalinity_flux": "float",
                                "global_time": "float"}},
            "inputs": {"temperature": ["vent", "temperature"], "pH": ["vent", "pH"],
                       "porosity": ["vent", "porosity"], "H2": ["vent", "H2"],
                       "alkalinity": ["vent", "alkalinity"],
                       "H2_flux": ["rates", "H2_flux"], "alkalinity_flux": ["rates", "alkalinity_flux"],
                       "global_time": ["global_time"]},
        },
    }
