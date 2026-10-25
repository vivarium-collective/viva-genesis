"""og-self-maintaining-individual UNDER heated gas-bubble interface accumulation.

The reciprocal-maintenance loop (``self_maintaining.og_self_maintaining_individual``)
was REFUTED: the chemistry's amphiphile pool sits ~4 orders below its CAC at the
favorable corner and ~7 orders below at the canonical point, so no membrane forms
endogenously. ``self_maintaining_concentrated`` closed that gap SPATIALLY with the
vent pore's thermophoretic (Baaske) trap — but only near the trap's exponential
maximum and on an hours-to-days residence time.

This composite swaps in the ALTERNATIVE concentrating mechanism from Morasch, Liu,
Mast, Braun et al. (Nature Chemistry 11, 779-788, 2019; arXiv:2104.05537): a HEATED
GAS-WATER INTERFACE (gas bubble under a thermal gradient) that concentrates solutes
at its warm-side meniscus via a continuous evaporation-recondensation cycle, FASTER
than a thermophoretic trap (minutes, not hours) and — once lipids are present —
continuously encapsulating the accumulated pool into vesicle aggregates.

Structure parallels ``self_maintaining_concentrated`` so the two mechanisms compare
directly: A's real precursor-pool reactor feeds acetate to the real
``AmphiphileChainExtensionProcess`` (base, well-mixed aggregation competence), and
the ``GasBubbleAccumulationProcess`` re-judges the pool at the bubble meniscus
(``aggregation_competent`` * interface enrichment). There is NO separate FiPy solver:
the interface enrichment is derived inside the process from Morasch's MEASURED
delta_T scaling (~700-fold at delta_T 20 K, ~4000-fold at delta_T 40 K). The matched
``concentrating=False`` control (enrichment 1) is the no-built-in-gain witness.

Enrichment is applied once to the synthesised pool (conservative). ``delta_T`` is the
single swept geometry knob (the bubble's warm/cold difference); ``diffusion_derate``
exposes Morasch's diffusion-coefficient dependence. The test: does the gas-bubble
interface clear CAC (aggregation_competent_concentrated >= 1), at what delta_T, and
how does that compare to the thermophoretic trap's near-maximal requirement?
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

_EMIT = {
    "acetate": "float",
    "aggregation_competent_base": "float",
    "aggregation_competent_concentrated": "float",
    "amphiphile_total_base": "float",
    "effective_enrichment": "float",
    "steady_enrichment": "float",
    "equilibration_fraction": "float",
    "global_time": "float",
}


@composite_generator(
    name="og_self_maintaining_bubble",
    methods=["libRoadRunner precursor-pool reactor", "explicit fatty-acid chain-extension synthesis",
             "heated gas-water interface accumulation (Morasch 2019 measured delta_T scaling)",
             "interface-concentrated aggregation competence (no built-in gain)"],
    fidelity="real",
    description=(
        "Connects the narrative's self-maintenance step to the ALTERNATIVE concentrating mechanism — a heated "
        "gas-water interface (Morasch 2019): A's real precursor-pool reactor feeds acetate to the real "
        "AmphiphileChainExtensionProcess (base, well-mixed aggregation competence = long-chain/CAC); the "
        "GasBubbleAccumulationProcess applies the bubble meniscus's measured evaporation-recondensation enrichment "
        "(~700x at delta_T 20 K, ~4000x at delta_T 40 K) to re-judge the pool at the interface "
        "(aggregation_competent * enrichment). The matched concentrating=False control (enrichment 1) is the "
        "no-built-in-gain witness. Tests whether the gas-bubble interface closes the 4-7 order amphiphile/CAC gap "
        "that refuted og-self-maintaining-individual, and how it compares to the thermophoretic trap."
    ),
    parameters={
        "feed_CO2": {"type": "float", "default": 2.0e-3,
                     "description": "Inorganic-carbon feed (M), og-vent-interface DIC window"},
        "delta_T": {"type": "float", "default": 20.0,
                    "description": "Cross-bubble temperature difference (K); Morasch anchors 700x@20K, 4000x@40K"},
        "diffusion_derate": {"type": "float", "default": 1.0,
                             "description": "Diffusion-coefficient derating (0-1]; 1.0 = strong self-associating accumulator, <1 = fast monomer"},
        "concentrating": {"type": "boolean", "default": True,
                          "description": "Interface accumulation on; False is the matched non-concentrating control (enrichment 1)"},
    },
    default_n_steps=240,
    preferred_time="24 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter",
               "paths": ["chem/acetate", "mem/aggregation_competent", "mem/aggregation_competent_concentrated",
                         "mem/amphiphile_total", "mem/effective_enrichment", "mem/steady_enrichment",
                         "mem/equilibration_fraction", "global_time"]}],
)
def og_self_maintaining_bubble(core=None, *, feed_CO2=2.0e-3, delta_T=20.0,
                               diffusion_derate=1.0, concentrating=True):
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
        # concentration: heated gas-water interface -> re-judged pool at the meniscus
        "bubble": {
            "_type": "process",
            "address": "local:GasBubbleAccumulationProcess",
            "config": {"concentrating": bool(concentrating),
                       "diffusion_derate": float(diffusion_derate)},
            "interval": 1.0,
            "inputs": {"aggregation_competent": ["mem", "aggregation_competent"],
                       "amphiphile_total": ["mem", "amphiphile_total"],
                       "delta_T": ["interface", "delta_T"]},
            "outputs": {"aggregation_competent_concentrated": ["mem", "aggregation_competent_concentrated"],
                        "amphiphile_total_concentrated": ["mem", "amphiphile_total_concentrated"],
                        "effective_enrichment": ["mem", "effective_enrichment"],
                        "steady_enrichment": ["mem", "steady_enrichment"],
                        "equilibration_fraction": ["mem", "equilibration_fraction"]},
        },
        "feed": {"feed_CO2": float(feed_CO2), "feed_H2": 1.08e-2, "feed_pyruvate": 0.0,
                 "feed_formaldehyde": 0.0, "feed_formate": 0.0, "feed_acetate": 0.0},
        "chem": {"acetate": 0.0},
        "mem": {"aggregation_competent": 0.0, "amphiphile_total": 0.0, "long_chain_fraction": 0.0,
                "mean_chain_length": 0.0, "degradation_loss": 0.0,
                "aggregation_competent_concentrated": 0.0, "amphiphile_total_concentrated": 0.0,
                "effective_enrichment": 1.0, "steady_enrichment": 1.0, "equilibration_fraction": 0.0},
        "interface": {"delta_T": float(delta_T)},
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
                "effective_enrichment": ["mem", "effective_enrichment"],
                "steady_enrichment": ["mem", "steady_enrichment"],
                "equilibration_fraction": ["mem", "equilibration_fraction"],
                "global_time": ["global_time"],
            },
        },
    }
