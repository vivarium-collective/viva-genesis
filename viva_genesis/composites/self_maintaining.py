"""NEW C — og-self-maintaining-individual: the reciprocal-maintenance loop.

The campaign's central OPEN target (§9): does the coupled chemistry-and-boundary
system MAINTAIN ITSELF - the chemistry producing the amphiphiles that form the
boundary that retains the chemistry that sustains production - under perturbation,
WITHOUT a built-in production or retention gain?

This composite is ONE coupled pass of the loop at a given membrane state: A's real
PrecursorPoolProcess (the C1-C3 reaction universe) feeds its acetate (C2) to the
real AmphiphileChainExtensionProcess (explicit fatty-acid elongation -> chain-length
distribution -> aggregation_competent = long-chain pool / CAC). A's effective washout
is the (runner-supplied) membrane-gated value. The full reciprocal fixed point, the
three ablations (chemistry->membrane, membrane->chemistry, external feed), the
with/without-built-in-gain comparison, and B's conditional corner all live in
sims/run.py, which drives these same real processes directly.

The honesty crux (C's equivalent of A's thermodynamic ceiling / B's Soret): the
membrane retention is NEVER pinned at og_32's assumed long-chain ~0.9 regardless of
whether the pool clears CAC - that assumed gain is exactly what would falsely close
the loop. ``gated_retention`` earns retention only on the chemistry's ACTUAL
aggregation_competent, surfaced as the explicit no-built-in-gain witness.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from .og_32_first_self_maintaining_protocell import composition_retention

# Earned retention IF the chemistry clears CAC (the aggregation-competent long-chain
# composition from og_32's MD-informed relation). Below CAC clearance -> 0 (no membrane).
_EARNED_RETENTION = composition_retention("long_di-C16")[2]
_K_WASH = 0.05


def gated_retention(aggregation_competent: float, *, earned: float = _EARNED_RETENTION) -> float:
    """Membrane retention GATED on the chemistry's actual aggregation competence.

    A membrane (retention > 0) exists only when the amphiphile pool the chemistry
    actually produces clears its critical aggregation concentration
    (aggregation_competent >= 1). Below that there is no boundary, so retention is 0.
    The earned value (when competent) is og_32's MD-informed long-chain retention -
    EARNED here, never assumed. This is the no-built-in-gain construction.
    """
    return float(earned) if float(aggregation_competent) >= 1.0 else 0.0


_EMIT = {"acetate": "float", "aggregation_competent": "float", "amphiphile_total": "float",
         "long_chain_fraction": "float", "functional_pool_carbon": "float", "global_time": "float"}


@composite_generator(
    name="og_self_maintaining_individual",
    methods=["libRoadRunner precursor-pool reactor", "explicit fatty-acid chain-extension synthesis",
             "aggregation-gated membrane retention (no built-in gain)"],
    fidelity="real",
    description=(
        "NEW C (one coupled pass): A's real precursor-pool reactor feeds its acetate to the real "
        "AmphiphileChainExtensionProcess (fatty-acid elongation -> aggregation_competent = long-chain / CAC) at a "
        "runner-supplied membrane-gated effective washout. The reciprocal fixed point, the 3 ablations and the "
        "with/without-built-in-gain comparison are in sims/run.py. Retention is earned on the actual "
        "aggregation_competent, never og_32's assumed ~0.9."
    ),
    parameters={
        "feed_CO2": {"type": "float", "default": 2.0e-3,
                     "description": "Inorganic-carbon feed (M), og-vent-interface DIC window"},
        "k_wash_eff": {"type": "float", "default": _K_WASH,
                       "description": "Effective CSTR washout (1/s); the runner sets it from the gated retention"},
    },
    default_n_steps=240,
    preferred_time="24 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter",
               "paths": ["chem/acetate", "mem/aggregation_competent", "mem/amphiphile_total",
                         "mem/long_chain_fraction", "global_time"]}],
)
def og_self_maintaining_individual(core=None, *, feed_CO2=2.0e-3, k_wash_eff=_K_WASH):
    if core is None:
        core = build_core()
    return {
        "reactor": {
            "_type": "process",
            "address": "local:PrecursorPoolProcess",
            "config": {"max_carbons": 3, "thermo_source": "package",
                       "ammonium_availability": 1.3e-4, "k_wash": float(k_wash_eff)},
            "interval": 1.0,
            "inputs": {k: ["feed", k] for k in
                       ("feed_CO2", "feed_H2", "feed_pyruvate", "feed_formaldehyde",
                        "feed_formate", "feed_acetate")},
            "outputs": {"acetate": ["chem", "acetate"],
                        "functional_pool_carbon": ["obs", "functional_pool_carbon"]},
        },
        "synth": {
            "_type": "process",
            "address": "local:AmphiphileChainExtensionProcess",
            "config": {},
            "interval": 1.0,
            "inputs": {"acetate": ["chem", "acetate"], "temperature": ["env", "temperature"]},
            "outputs": {"aggregation_competent": ["mem", "aggregation_competent"],
                        "amphiphile_total": ["mem", "amphiphile_total"],
                        "long_chain_fraction": ["mem", "long_chain_fraction"],
                        "mean_chain_length": ["mem", "mean_chain_length"],
                        "degradation_loss": ["mem", "degradation_loss"]},
        },
        "feed": {"feed_CO2": float(feed_CO2), "feed_H2": 1.08e-2, "feed_pyruvate": 0.0,
                 "feed_formaldehyde": 0.0, "feed_formate": 0.0, "feed_acetate": 0.0},
        "chem": {"acetate": 0.0},
        "mem": {"aggregation_competent": 0.0, "amphiphile_total": 0.0, "long_chain_fraction": 0.0,
                "mean_chain_length": 0.0, "degradation_loss": 0.0},
        "obs": {"functional_pool_carbon": 0.0},
        "env": {"temperature": 330.0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": _EMIT},
            "inputs": {
                "acetate": ["chem", "acetate"],
                "aggregation_competent": ["mem", "aggregation_competent"],
                "amphiphile_total": ["mem", "amphiphile_total"],
                "long_chain_fraction": ["mem", "long_chain_fraction"],
                "functional_pool_carbon": ["obs", "functional_pool_carbon"],
                "global_time": ["global_time"],
            },
        },
    }
