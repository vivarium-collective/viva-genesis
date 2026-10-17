"""Reduced-nitrogen reactor — FeS-mediated reduction of oxidised/inert nitrogen to
ammonium and its assimilation toward amino-acid precursors (Campaign I, Module I).

One parameterized generator drives every study condition:
  - favourable baseline : defaults (fes_activity=1.0, H2 5 mM, nitrate fed)
  - nitrogen-limited arm : low no3_supply / low fes_activity (C:N blows up)
  - controls            : fes_activity=0 (no mineral) / h2=0 (no reductant) -> no NH4+

It wraps the real :class:`ReducedNitrogenProductionProcess`: NO3- -> NO2- -> NH4+
on FeS gated by H2 availability, a temperature window and catalyst activity, with
a minor abiotic N2-fixation source and reductive amination pulled by the carbon-
fixation demand ``c_demand``. The decision observable is the C:N supply ratio
(carbon demand / reduced-N production) — does reduced nitrogen keep pace with
reduced carbon, or become limiting first?

This is a general-purpose module (reusable wherever a stage needs a reduced-N
supply), not an og-specific composite.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

_EMIT_PATHS = [
    "pools/NO3", "pools/NO2", "pools/NH4", "pools/amino_precursor", "pools/N2",
    "flux/nh4_production_rate", "flux/n_supply_rate", "flux/cn_supply_ratio",
    "flux/reduced_n", "flux/total_n", "flux/n_mass_residual",
    "global_time",
]


@composite_generator(
    name="reduced_nitrogen_reactor",
    methods=["coarse-grained FeS nitrate->ammonium reduction kinetics",
             "reductive-amination N-assimilation"],
    fidelity="reproduction",
    description=(
        "A reusable FeS-mediated reduced-nitrogen module. The real "
        "ReducedNitrogenProductionProcess reduces NO3-/NO2- to NH4+ on an Fe/Ni/S "
        "catalyst (H2-dependent, temperature-windowed), adds a minor abiotic N2-fixation "
        "source, and draws ammonium into amino-acid precursors by reductive amination at a "
        "rate set by the carbon-fixation demand. Tracks the C:N supply ratio "
        "(carbon demand / reduced-N production) to test whether reduced nitrogen keeps pace "
        "with reduced carbon. fes_activity=0 / h2=0 are the no-mineral / no-reductant controls."
    ),
    parameters={
        "no3_supply": {"type": "float", "default": 2.0e-5,
                       "description": "Open-flow nitrate feed (M/s); sets the ceiling on sustained reduced-N production"},
        "fes_activity": {"type": "float", "default": 1.0,
                         "description": "Active Fe/Ni/S catalyst in [0,1] (0 = no-mineral control)"},
        "h2": {"type": "float", "default": 5.0e-3,
               "description": "Dissolved H2 reductant (M); ~0 = no-reductant control"},
        "temperature": {"type": "float", "default": 353.15,
                        "description": "Temperature (K); FeS nitrate-reduction optimum ~80 C"},
        "c_demand": {"type": "float", "default": 1.0e-4,
                     "description": "Carbon-fixation demand pulling reduced N into precursors (mol/s)"},
        "no3_init": {"type": "float", "default": 1.0e-3, "description": "Initial nitrate pool (M)"},
        "n2": {"type": "float", "default": 5.0e-4, "description": "Dissolved N2 available for minor fixation (M)"},
        "loss_rate": {"type": "float", "default": 1.0e-2,
                      "description": "Open-flow washout of NH4+/precursor (1/s); 0 = closed batch (conservation control)"},
    },
    visualizations=[
        {"name": "nitrogen-assimilation-timeseries", "address": "local:NitrogenAssimilationViz",
         "config": {"n_steps": 120, "title": "Reduced-nitrogen assimilation (FeS)"}},
        {"name": "c-to-n-supply-balance", "address": "local:NitrogenCarbonBalanceViz",
         "config": {"n_steps": 120, "title": "Does reduced N keep pace with carbon?"}},
    ],
    default_n_steps=120,
    preferred_time="24 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def reduced_nitrogen_reactor(core=None, *, no3_supply=2.0e-5, fes_activity=1.0, h2=5.0e-3,
                             temperature=353.15, c_demand=1.0e-4, no3_init=1.0e-3,
                             n2=5.0e-4, loss_rate=1.0e-2):
    return {
        "nitrogen": {
            "_type": "process",
            "address": "local:ReducedNitrogenProductionProcess",
            "config": {"no3_supply": no3_supply, "loss_rate": loss_rate},
            "interval": 1.0,
            "inputs": {"NO3": ["pools", "NO3"], "NO2": ["pools", "NO2"], "NH4": ["pools", "NH4"],
                       "amino_precursor": ["pools", "amino_precursor"], "N2": ["pools", "N2"],
                       "H2": ["env", "H2"], "temperature": ["env", "temperature"],
                       "fes_activity": ["catalyst", "fes_activity"], "c_demand": ["env", "c_demand"]},
            "outputs": {"NO3": ["pools", "NO3"], "NO2": ["pools", "NO2"], "NH4": ["pools", "NH4"],
                        "amino_precursor": ["pools", "amino_precursor"], "N2": ["pools", "N2"],
                        "nh4_production_rate": ["flux", "nh4_production_rate"],
                        "n_supply_rate": ["flux", "n_supply_rate"],
                        "cn_supply_ratio": ["flux", "cn_supply_ratio"],
                        "reduced_n": ["flux", "reduced_n"], "total_n": ["flux", "total_n"],
                        "n_mass_residual": ["flux", "n_mass_residual"]},
        },
        "env": {"H2": h2, "temperature": temperature, "c_demand": c_demand},
        "pools": {"NO3": no3_init, "NO2": 0.0, "NH4": 0.0, "amino_precursor": 0.0, "N2": n2},
        "flux": {"nh4_production_rate": 0.0, "n_supply_rate": 0.0, "cn_supply_ratio": 0.0,
                 "reduced_n": 0.0, "total_n": 0.0, "n_mass_residual": 0.0},
        "catalyst": {"fes_activity": fes_activity},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {"NO3": "float", "NO2": "float", "NH4": "float",
                                "amino_precursor": "float", "N2": "float",
                                "nh4_production_rate": "float", "n_supply_rate": "float",
                                "cn_supply_ratio": "float", "reduced_n": "float",
                                "total_n": "float", "n_mass_residual": "float",
                                "global_time": "float"}},
            "inputs": {"NO3": ["pools", "NO3"], "NO2": ["pools", "NO2"], "NH4": ["pools", "NH4"],
                       "amino_precursor": ["pools", "amino_precursor"], "N2": ["pools", "N2"],
                       "nh4_production_rate": ["flux", "nh4_production_rate"],
                       "n_supply_rate": ["flux", "n_supply_rate"],
                       "cn_supply_ratio": ["flux", "cn_supply_ratio"],
                       "reduced_n": ["flux", "reduced_n"], "total_n": ["flux", "total_n"],
                       "n_mass_residual": ["flux", "n_mass_residual"],
                       "global_time": ["global_time"]},
        },
    }
