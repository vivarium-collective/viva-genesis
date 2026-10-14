"""Campaign II composite — reduced carbon to protometabolism (og-02).

A single real-tool module: ``network`` = the genuine libRoadRunner/Tellurium SBML
rTCA-fragment CSTR (``RoadRunnerNetworkProcess``), fed the reduced-carbon products
from og-01 (pyruvate + CO2) under continuous feed + washout. The emergent
observables — sustained net carbon throughput, autocatalytic gain, network
connectivity — test whether metabolism-like subnetworks arise under flow without
imposed product accumulation. Driven by a genuine libRoadRunner/Tellurium SBML
ODE integration (needs ``tellurium``) with a ``networkx`` connectivity check
(needs ``networkx``).
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

_EMIT_PATHS = [
    "net/OAA", "net/acetate", "net/succinate",
    "flux/net_carbon_flux", "flux/autocatalytic_gain", "flux/network_connected",
    "global_time",
]


@composite_generator(
    name="protometabolic_network",
    methods=["libRoadRunner/Tellurium SBML ODE", "networkx connectivity"],
    fidelity="real",
    description=(
        "A reusable protometabolic reaction-network module. A genuine libRoadRunner/"
        "Tellurium SBML ODE integration (needs tellurium) of an rTCA-fragment CSTR "
        "(pyruvate carboxylation + lumped autocatalytic rTCA turn + reductive branch) "
        "fed the og-01 reduced-carbon products under continuous feed+washout, with a "
        "networkx connectivity check on the species-reaction graph (needs networkx). "
        "Emergent: sustained carbon throughput, an autocatalytic motif (gain>1), and a "
        "connected reaction network."
    ),
    parameters={
        "feed_pyruvate": {"type": "float", "default": 1.0e-4,
                          "description": "Pyruvate feed set-point (M) from og-01 reduced carbon"},
        "feed_CO2": {"type": "float", "default": 2.0e-3,
                     "description": "CO2 feed set-point (M); ~0 = no-carbon control"},
        "k_rtca": {"type": "float", "default": 800.0,
                   "description": "Autocatalytic rTCA-turn rate constant (Fe-promoted)"},
        "k_wash": {"type": "float", "default": 0.05,
                   "description": "CSTR washout / dilution rate (1/s); the feed-vs-washout axis of the gain phase map"},
    },
    visualizations=[
        {"name": "protometabolic-network", "address": "local:ProtometabolicNetwork",
         "config": {"n_steps": 60, "title": "The protometabolic network igniting"}},
        {"name": "protometabolism-network", "address": "local:ProtometabolismViz",
         "config": {"n_steps": 120, "title": "Protometabolic network (libRoadRunner)"}},
    ],
    default_n_steps=120,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def protometabolic_network(core=None, *, feed_pyruvate=1.0e-4,
                                            feed_CO2=2.0e-3, k_rtca=800.0, k_wash=0.05):
    return {
        "network": {
            "_type": "process",
            "address": "local:RoadRunnerNetworkProcess",
            "config": {"k_rtca": k_rtca, "k_wash": k_wash},
            "interval": 1.0,
            "inputs": {"feed_pyruvate": ["feed", "pyruvate"], "feed_CO2": ["feed", "CO2"]},
            "outputs": {"OAA": ["net", "OAA"], "malate": ["net", "malate"],
                        "succinate": ["net", "succinate"], "acetate": ["net", "acetate"],
                        "net_carbon_flux": ["flux", "net_carbon_flux"],
                        "autocatalytic_gain": ["flux", "autocatalytic_gain"],
                        "network_connected": ["flux", "network_connected"]},
        },
        "feed": {"pyruvate": feed_pyruvate, "CO2": feed_CO2},
        "net": {"OAA": 0.0, "malate": 0.0, "succinate": 0.0, "acetate": 0.0},
        "flux": {"net_carbon_flux": 0.0, "autocatalytic_gain": 0.0, "network_connected": 0.0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {"OAA": "float", "acetate": "float", "succinate": "float",
                                "net_carbon_flux": "float", "autocatalytic_gain": "float",
                                "network_connected": "float", "global_time": "float"}},
            "inputs": {"OAA": ["net", "OAA"], "acetate": ["net", "acetate"],
                       "succinate": ["net", "succinate"],
                       "net_carbon_flux": ["flux", "net_carbon_flux"],
                       "autocatalytic_gain": ["flux", "autocatalytic_gain"],
                       "network_connected": ["flux", "network_connected"],
                       "global_time": ["global_time"]},
        },
    }
