"""og-self-maintaining-individual UNDER thermophoretic pore concentration.

The reciprocal-maintenance loop (``self_maintaining.og_self_maintaining_individual``)
was REFUTED: the chemistry's amphiphile pool sits ~4 orders below its CAC at
og-operating-window's favorable corner and ~7 orders below at the canonical point,
so no membrane forms endogenously and the chemistry<->boundary loop cannot close
without a built-in gain. But that loop omitted the one SUPPORTED mechanism that
could supply the missing orders: the vent pore's thermophoretic (Baaske) thermal
trap that og-spatial-concentration establishes (enrichment exponential in pore
length; >10^8-fold in favorable geometry).

This composite CONNECTS those two steps of the narrative into one multiscale model.
A's real precursor-pool reactor feeds acetate to the real fatty-acid chain-extension
(base, well-mixed aggregation competence); the real FiPy ``ThermophoreticTrapProcess``
solves the pore's accumulation column from its genuine Soret+convection physics; and
the amphiphile pool is re-judged at the trap base (``aggregation_competent`` *
``enrichment_factor``). The loop thus closes SPATIALLY — using the pore's
concentration — rather than assuming a membrane. The matched non-concentrating
control (``concentrating=False`` -> enrichment 1) is the no-built-in-gain witness:
if the pore closes the loop but the control does not, concentration is the
discriminating mechanism; if even a favorable trap cannot, the refutation sharpens.

Enrichment is applied once to the synthesised pool (conservative — not compounded
through the nonlinear synthesis). The pore geometry (delta_T, pore_length, flow,
porosity) and the amphiphile Soret coefficient are swept to find the regime, if any,
in which spatial concentration clears CAC at defensible vent conditions.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

_EMIT = {
    "acetate": "float",
    "aggregation_competent_base": "float",
    "aggregation_competent_concentrated": "float",
    "amphiphile_total_base": "float",
    "enrichment_factor": "float",
    "effective_enrichment": "float",
    "residence_time": "float",
    "global_time": "float",
}


@composite_generator(
    name="og_self_maintaining_concentrated",
    methods=["libRoadRunner precursor-pool reactor", "explicit fatty-acid chain-extension synthesis",
             "real FiPy Baaske thermophoretic trap (enrichment read from the solved column)",
             "pore-concentrated aggregation competence (no built-in gain)"],
    fidelity="real",
    description=(
        "Connects the narrative's spatial-concentration step to its self-maintenance step: A's real "
        "precursor-pool reactor feeds acetate to the real AmphiphileChainExtensionProcess (base, well-mixed "
        "aggregation competence = long-chain/CAC); the real FiPy ThermophoreticTrapProcess solves the vent pore's "
        "Baaske accumulation column (enrichment read from the solved base/top ratio); and the amphiphile pool is "
        "re-judged at the trap base (aggregation_competent * enrichment_factor). The matched concentrating=False "
        "control (enrichment 1) is the no-built-in-gain witness. Tests whether spatial concentration closes the "
        "4-7 order amphiphile/CAC gap that refuted og-self-maintaining-individual, and at what pore geometry."
    ),
    parameters={
        "feed_CO2": {"type": "float", "default": 2.0e-3,
                     "description": "Inorganic-carbon feed (M), og-vent-interface DIC window"},
        "delta_T": {"type": "float", "default": 30.0,
                    "description": "Cross-pore temperature difference (K); Lost City-ish, Baaske-favorable ~30"},
        "pore_length": {"type": "float", "default": 5.0e-3,
                        "description": "Accumulation-column length (m); enrichment is exponential in this"},
        "pore_flow": {"type": "float", "default": 1.0e-4,
                      "description": "Buoyant convective flow in the pore (m/s)"},
        "porosity": {"type": "float", "default": 0.3,
                     "description": "Pore porosity/openness (0-1; lower = more confinement = more trapping)"},
        "soret_coeff": {"type": "float", "default": 0.05,
                        "description": "Amphiphile Soret coefficient (1/K): ~0.01 small-molecule, ~0.10 large self-associating; swept"},
        "concentrating": {"type": "boolean", "default": True,
                          "description": "Pore concentration on; False is the matched non-concentrating control (enrichment 1)"},
    },
    default_n_steps=240,
    preferred_time="24 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter",
               "paths": ["chem/acetate", "mem/aggregation_competent", "mem/aggregation_competent_concentrated",
                         "mem/amphiphile_total", "pore/enrichment_factor", "mem/effective_enrichment",
                         "pore/residence_time", "global_time"]}],
)
def og_self_maintaining_concentrated(core=None, *, feed_CO2=2.0e-3, delta_T=30.0, pore_length=5.0e-3,
                                     pore_flow=1.0e-4, porosity=0.3, soret_coeff=0.05, concentrating=True):
    if core is None:
        core = build_core()
    return {
        # chemistry: real precursor-pool reactor -> acetate (C2)
        "reactor": {
            "_type": "process",
            "address": "local:PrecursorPoolProcess",
            "config": {"max_carbons": 3, "thermo_source": "package",
                       "ammonium_availability": 1.3e-4, "k_wash": 0.05},
            "interval": 1.0,
            "inputs": {k: ["feed", k] for k in
                       ("feed_CO2", "feed_H2", "feed_pyruvate", "feed_formaldehyde",
                        "feed_formate", "feed_acetate")},
            "outputs": {"acetate": ["chem", "acetate"],
                        "functional_pool_carbon": ["obs", "functional_pool_carbon"]},
        },
        # synthesis: explicit fatty-acid chain extension -> base aggregation competence
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
        # spatial concentration: real FiPy Baaske thermophoretic trap -> enrichment factor
        "trap": {
            "_type": "process",
            "address": "local:ThermophoreticTrapProcess",
            "config": {"pore_length": float(pore_length), "delta_T": float(delta_T),
                       "soret_coeff": float(soret_coeff)},
            "interval": 1.0,
            "inputs": {"temperature": ["pore", "temperature"], "flow_velocity": ["pore", "flow_velocity"],
                       "porosity": ["pore", "porosity"]},
            "outputs": {"enrichment_factor": ["pore", "enrichment_factor"],
                        "residence_time": ["pore", "residence_time"],
                        "accumulation_peclet": ["pore", "accumulation_peclet"],
                        "flux_divergence_residual": ["pore", "flux_divergence_residual"]},
        },
        # couple: re-judge the amphiphile pool at the trap base (base * enrichment)
        "concentrate": {
            "_type": "process",
            "address": "local:AmphiphileTrapConcentrationProcess",
            "config": {"concentrating": bool(concentrating)},
            "interval": 1.0,
            "inputs": {"aggregation_competent": ["mem", "aggregation_competent"],
                       "amphiphile_total": ["mem", "amphiphile_total"],
                       "enrichment_factor": ["pore", "enrichment_factor"]},
            "outputs": {"aggregation_competent_concentrated": ["mem", "aggregation_competent_concentrated"],
                        "amphiphile_total_concentrated": ["mem", "amphiphile_total_concentrated"],
                        "effective_enrichment": ["mem", "effective_enrichment"]},
        },
        "feed": {"feed_CO2": float(feed_CO2), "feed_H2": 1.08e-2, "feed_pyruvate": 0.0,
                 "feed_formaldehyde": 0.0, "feed_formate": 0.0, "feed_acetate": 0.0},
        "chem": {"acetate": 0.0},
        "mem": {"aggregation_competent": 0.0, "amphiphile_total": 0.0, "long_chain_fraction": 0.0,
                "mean_chain_length": 0.0, "degradation_loss": 0.0,
                "aggregation_competent_concentrated": 0.0, "amphiphile_total_concentrated": 0.0,
                "effective_enrichment": 1.0},
        "pore": {"temperature": 333.15, "flow_velocity": float(pore_flow), "porosity": float(porosity),
                 "enrichment_factor": 1.0, "residence_time": 0.0, "accumulation_peclet": 0.0,
                 "flux_divergence_residual": 0.0},
        "obs": {"functional_pool_carbon": 0.0},
        "env": {"temperature": 330.0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": _EMIT},
            "inputs": {
                "acetate": ["chem", "acetate"],
                "aggregation_competent_base": ["mem", "aggregation_competent"],
                "aggregation_competent_concentrated": ["mem", "aggregation_competent_concentrated"],
                "amphiphile_total_base": ["mem", "amphiphile_total"],
                "enrichment_factor": ["pore", "enrichment_factor"],
                "effective_enrichment": ["mem", "effective_enrichment"],
                "residence_time": ["pore", "residence_time"],
                "global_time": ["global_time"],
            },
        },
    }
