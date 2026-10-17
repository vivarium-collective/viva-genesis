"""Campaign stage composite — metabolism → osmotic growth & division (og-growth-division).

A reusable osmotic-growth-and-division module: the ``OsmoticGrowthDivisionProcess``
couples an internal autocatalytic/metabolic osmolyte source to compartment physics
— product accumulation → osmotic pressure → solvent influx → volume growth →
division at a size threshold (or lysis if the pressure bursts the membrane, or
starvation if the product leaks away before it can build). One parameterized
generator drives every study condition:

  - favorable (matched)   : moderate throughput + moderate permeability → the
                            compartment grows and divides repeatedly;
  - lysis arm             : high throughput + near-impermeable → osmotic pressure
                            spikes past the burst tension → lysis;
  - starvation arm        : very permeable → product leaks, no osmotic build-up →
                            no growth;
  - ablation              : ~zero throughput → no source → no growth.

Emits volume, internal concentration, osmotic pressure, product amount, division
count / event, lysis flag, net growth, the mass-balance residual, and an outcome
code (0 starve · 1 grow-no-division · 2 divide · 3 lysis). Pure physico-chemical
model — no heavy dependencies.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

_EMIT_PATHS = [
    "cell/volume", "cell/internal_concentration", "cell/osmotic_pressure",
    "cell/product_amount", "cell/division_count", "cell/division_event",
    "cell/lysed", "cell/net_growth", "cell/osmolyte_balance_residual",
    "cell/outcome_code", "global_time",
]


@composite_generator(
    name="osmotic_growth_division",
    methods=["coarse-grained osmotic growth-division model"],
    fidelity="reproduction",
    description=(
        "A reusable osmotic growth-and-division module (metabolism → growth & "
        "division). An internal autocatalytic osmolyte source coupled to compartment "
        "osmotic physics: product accumulation → osmotic pressure (van 't Hoff) → "
        "solvent influx → volume growth → division at a size threshold. Membrane "
        "permeability sets the fate: too permeable starves (product leaks, no osmotic "
        "build-up), too impermeable lyses (pressure bursts the membrane), matched gives "
        "sustained growth → division. Units-typed, mass-conserving coarse-grained "
        "reproduction (not wrapped membrane MD)."
    ),
    parameters={
        "network_throughput": {"type": "float", "default": 1.0e-19,
                               "description": "Internal autocatalytic/metabolic osmolyte source rate (mole/second); ~0 = ablation control"},
        "autocatalytic_rate": {"type": "float", "default": 0.5,
                               "description": "Self-amplification gain of the source (dimensionless)"},
        "membrane_permeability": {"type": "float", "default": 1.0e-9,
                                  "description": "Membrane solute permeability (meter/second); the fate knob (leaky→starve, tight→lyse)"},
        "division_threshold": {"type": "float", "default": 6.4e-17,
                               "description": "Volume at which the compartment divides (liter); default 1.6× initial volume"},
        "leak_rate": {"type": "float", "default": 1.0,
                      "description": "Multiplier on the solute permeability for the outward leak (dimensionless)"},
    },
    visualizations=[
        {"name": "osmotic-growth-world", "address": "local:OsmoticGrowthWorld",
         "config": {"title": "Growth & division — volume, concentration, division events"}},
        {"name": "osmotic-coupling-mechanism", "address": "local:OsmoticCouplingMechanism",
         "config": {"title": "The osmotic coupling — why too permeable starves, too impermeable lyses"}},
        {"name": "growth-division-map", "address": "local:GrowthDivisionMap",
         "config": {"title": "Decision — the viable growth→division band"}},
    ],
    default_n_steps=100,
    preferred_time="48 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def osmotic_growth_division(core=None, *, network_throughput=1.0e-19,
                            autocatalytic_rate=0.5, membrane_permeability=1.0e-9,
                            division_threshold=6.4e-17, leak_rate=1.0):
    return {
        "cell_process": {
            "_type": "process",
            "address": "local:OsmoticGrowthDivisionProcess",
            "config": {
                "network_throughput": network_throughput,
                "autocatalytic_rate": autocatalytic_rate,
                "membrane_permeability": membrane_permeability,
                "division_threshold": division_threshold,
                "leak_rate": leak_rate,
            },
            "interval": 1.0,
            "inputs": {"external_osmolyte": ["env", "external_osmolyte"]},
            "outputs": {
                "volume": ["cell", "volume"],
                "internal_concentration": ["cell", "internal_concentration"],
                "osmotic_pressure": ["cell", "osmotic_pressure"],
                "product_amount": ["cell", "product_amount"],
                "division_count": ["cell", "division_count"],
                "division_event": ["cell", "division_event"],
                "lysed": ["cell", "lysed"],
                "net_growth": ["cell", "net_growth"],
                "osmolyte_balance_residual": ["cell", "osmolyte_balance_residual"],
                "outcome_code": ["cell", "outcome_code"],
            },
        },
        "env": {"external_osmolyte": 0.0},
        "cell": {"volume": 4.0e-17, "internal_concentration": 0.0, "osmotic_pressure": 0.0,
                 "product_amount": 0.0, "division_count": 0, "division_event": 0,
                 "lysed": 0, "net_growth": 1.0, "osmolyte_balance_residual": 0.0,
                 "outcome_code": 0},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": {"volume": "float", "internal_concentration": "float",
                                "osmotic_pressure": "float", "product_amount": "float",
                                "division_count": "integer", "division_event": "integer",
                                "lysed": "integer", "net_growth": "float",
                                "osmolyte_balance_residual": "float",
                                "outcome_code": "integer", "global_time": "float"}},
            "inputs": {"volume": ["cell", "volume"],
                       "internal_concentration": ["cell", "internal_concentration"],
                       "osmotic_pressure": ["cell", "osmotic_pressure"],
                       "product_amount": ["cell", "product_amount"],
                       "division_count": ["cell", "division_count"],
                       "division_event": ["cell", "division_event"],
                       "lysed": ["cell", "lysed"],
                       "net_growth": ["cell", "net_growth"],
                       "osmolyte_balance_residual": ["cell", "osmolyte_balance_residual"],
                       "outcome_code": ["cell", "outcome_code"],
                       "global_time": ["global_time"]},
        },
    }
