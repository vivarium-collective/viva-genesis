"""Study 17 — Endogenous Boundary (REBUILD chemistry): explicit amphiphile chain extension.

Replaces the lumped acetate+formate→one-amphiphile condensation with the explicit
AmphiphileChainExtensionProcess: iterative 2-carbon fatty-acid elongation across
multiple chain lengths, degradation, and a length-dependent CAC. The vent-carbon
product (acetate) is the ONLY carbon source — no exogenous amphiphile feed. The
composite reports the chain-length distribution + whether the composition clears the
critical aggregation concentration (aggregation_competent ≥ 1), which is the input
og-31's real Martini membrane engine would assemble.

Decision test (plan): vent-fed chemistry reaches an experimentally-grounded
aggregation-competent composition using only amphiphiles produced by the explicit
reactions, with all degradation/hydrolysis losses tracked.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

_EMIT = ("mean_chain_length", "amphiphile_total", "long_chain_fraction",
         "aggregation_competent", "degradation_loss")
_EMIT_PATHS = ["membrane/" + p for p in _EMIT]


@composite_generator(
    name="og_17_amphiphile_chain_extension",
    methods=["explicit 2-carbon fatty-acid elongation (named chain lengths)",
             "length-dependent CAC", "degradation-tracked; no exogenous amphiphile"],
    fidelity="real",
    description=(
        "Study 17: endogenous amphiphiles by explicit chemistry. AmphiphileChainExtension"
        "Process elongates fatty acids 2 carbons at a time from the vent-carbon feed (acetate), "
        "with degradation and a length-dependent critical aggregation concentration — replacing "
        "the lumped acetate+formate condensation. Reports the chain-length distribution + whether "
        "the composition clears the CAC (aggregation_competent >= 1), the input og-31's Martini "
        "membrane run would assemble. No exogenous amphiphile feed; losses tracked."
    ),
    parameters={
        "acetate_feed": {"type": "float", "default": 2.0e-2,
                         "description": "Vent-carbon (acetate, C2) feed concentration (molar)"},
        "k_extend": {"type": "float", "default": 0.4,
                     "description": "Chain-elongation rate (1/s)"},
        "k_degrade": {"type": "float", "default": 0.02,
                      "description": "Degradation/hydrolysis rate (1/s)"},
        "cac_molar": {"type": "float", "default": 5.0e-3,
                      "description": "Long-chain critical aggregation concentration (molar)"},
    },
    default_n_steps=120,
    preferred_time="6 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def og_17_amphiphile_chain_extension(core=None, *, acetate_feed=2.0e-2, k_extend=0.4,
                                     k_degrade=0.02, cac_molar=5.0e-3):
    if core is None:
        core = build_core()
    return {
        "chem": {
            "_type": "process",
            "address": "local:AmphiphileChainExtensionProcess",
            "config": {"k_extend": float(k_extend), "k_degrade": float(k_degrade),
                       "cac_molar": float(cac_molar)},
            "interval": 1.0,
            "inputs": {"acetate": ["feed", "acetate"], "temperature": ["env", "temperature"]},
            "outputs": {p: ["membrane", p] for p in _EMIT},
        },
        "feed": {"acetate": float(acetate_feed)},
        "env": {"temperature": 330.0},
        "membrane": {p: 0.0 for p in _EMIT},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {p: "float" for p in _EMIT}},
            "inputs": {p: ["membrane", p] for p in _EMIT},
        },
    }
