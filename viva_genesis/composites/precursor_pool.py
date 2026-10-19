"""NEW A — og-precursor-pool composites: geochemical carbon to a functional
precursor pool.

Dashboard-visible entry points wrapping the REAL C1-C3 reaction-universe engine
(``local:PrecursorPoolProcess``, a subclass of the genuine libRoadRunner
``ReactionUniverseProcess``). One canonical composite under the upstream-calibrated
vent feed, plus the three ablation controls that must collapse the functional pool:

- ``precursor_pool`` — canonical: CO2 in the og-vent-interface bounded DIC window
  (2-20 mM), H2 in og-carbon-fixation's dissolved-H2 region, reduced-nitrogen
  (ammonium) availability from og-nutrient-bottlenecks for the C:N readout.
- ``precursor_pool_no_h2`` — reductant removed (feed_H2 = 0).
- ``precursor_pool_no_catalyst`` — mineral + base catalyst sites = 0.
- ``precursor_pool_no_gradient`` — no sustained vent resupply (k_feed = 0): the
  disequilibrium the pH/redox gradient maintains is switched off.

Feed activities are upstream-calibrated values, never new literature numbers.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

# Upstream-calibrated canonical feed (molar). og-vent-interface DIC window 2-20 mM
# (lower-bound 2 mM = conservative), og-carbon-fixation dissolved-H2 ~10.8 mM.
_CO2 = 2.0e-3
_H2 = 1.08e-2
# "Off" value for control ablations. process-bigraph treats a Float store/config
# value of 0.0 as empty and backfills it from the schema/initial_state default, so
# a control that zeroes a knob must use a tiny epsilon, not literal 0.0.
_EPS = 1.0e-12
# og-nutrient-bottlenecks reduced-nitrogen (ammonium) availability; set so the
# fixed-carbon : nitrogen ratio lands in the viable 1-8 band (~5, the og-nutrient
# settled value).
_NH4 = 1.3e-4

_EMIT_PATHS = [
    "pool/formate", "pool/acetate", "pool/pyruvate", "pool/glycolaldehyde",
    "obs/functional_pool_carbon", "obs/pool_cofixed_fraction",
    "obs/electron_budget_residual", "obs/electrons_supplied_rate",
    "obs/electrons_fixed_rate", "obs/cn_ratio", "obs/total_organic_carbon",
    "obs/element_residual", "obs/carbon_residual", "obs/net_carbon_flux",
    "global_time",
]

# The observable keys the RAM/Parquet emitter records (name -> type).
_EMIT = {
    "formate": "float", "acetate": "float", "pyruvate": "float", "glycolaldehyde": "float",
    "functional_pool_carbon": "float", "pool_cofixed_fraction": "float",
    "electron_budget_residual": "float", "electrons_supplied_rate": "float",
    "electrons_fixed_rate": "float", "cn_ratio": "float", "total_organic_carbon": "float",
    "element_residual": "float", "carbon_residual": "float", "net_carbon_flux": "float",
    "global_time": "float",
}

_FEED_PORTS = ("feed_CO2", "feed_H2", "feed_pyruvate", "feed_formaldehyde",
               "feed_formate", "feed_acetate")
_POOL_PORTS = ("formate", "acetate", "pyruvate", "glycolaldehyde")
_OBS_PORTS = ("functional_pool_carbon", "pool_cofixed_fraction", "electron_budget_residual",
              "electrons_supplied_rate", "electrons_fixed_rate", "cn_ratio",
              "total_organic_carbon", "element_residual", "carbon_residual", "net_carbon_flux")


def _pool_composite(*, feed_CO2, feed_H2, nh4, kin_overrides=None):
    """Assemble the precursor-pool composite from the real engine + a RAM emitter."""
    config = {"max_carbons": 3, "thermo_source": "package", "ammonium_availability": nh4}
    config.update(kin_overrides or {})
    feed = {"feed_CO2": feed_CO2, "feed_H2": feed_H2, "feed_pyruvate": 0.0,
            "feed_formaldehyde": 0.0, "feed_formate": 0.0, "feed_acetate": 0.0}
    return {
        "reactor": {
            "_type": "process",
            "address": "local:PrecursorPoolProcess",
            "config": config,
            "interval": 1.0,
            "inputs": {k: ["feed", k] for k in _FEED_PORTS},
            "outputs": {
                **{p: ["pool", p] for p in _POOL_PORTS},
                **{p: ["obs", p] for p in _OBS_PORTS},
            },
        },
        "feed": feed,
        "pool": {p: 0.0 for p in _POOL_PORTS},
        "obs": {p: 0.0 for p in _OBS_PORTS},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": _EMIT},
            "inputs": {
                **{p: ["pool", p] for p in _POOL_PORTS},
                **{p: ["obs", p] for p in _OBS_PORTS},
                "global_time": ["global_time"],
            },
        },
    }


_VIZ = [{"name": "precursor-pool-yield-vectors", "address": "local:PrecursorPoolProcess",
         "config": {"n_steps": 240, "title": "Functional precursor pool (C1-C3 reaction universe)"}}]


@composite_generator(
    name="precursor_pool",
    methods=["libRoadRunner/Tellurium SBML ODE", "eQuilibrator dG'", "carbon-source attribution"],
    fidelity="real",
    description=(
        "NEW A canonical: the real C1-C3 rule-generated reaction-universe CSTR "
        "(libRoadRunner, atom-resolved, eQuilibrator dG') under the upstream-calibrated "
        "vent feed (DIC window 2-20 mM CO2, dissolved H2), read out as functional "
        "precursor yield vectors with de-novo carbon-source attribution (NOT isotope "
        "13C) and a degree-of-reduction electron budget. Delivers the precursor state "
        "the downstream network + amphiphile studies consume."
    ),
    parameters={
        "feed_CO2": {"type": "float", "default": _CO2,
                     "description": "Inorganic-carbon feed (M) in the og-vent-interface DIC window 2-20 mM"},
        "feed_H2": {"type": "float", "default": _H2,
                    "description": "Dissolved-H2 feed (M) from og-carbon-fixation's bounded region"},
        "ammonium_availability": {"type": "float", "default": _NH4,
                                  "description": "Reduced-N (ammonium) availability (M) from og-nutrient-bottlenecks, for C:N"},
    },
    visualizations=_VIZ,
    default_n_steps=240,
    preferred_time="24 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def precursor_pool(core=None, *, feed_CO2=_CO2, feed_H2=_H2, ammonium_availability=_NH4):
    return _pool_composite(feed_CO2=feed_CO2, feed_H2=feed_H2, nh4=ammonium_availability)


@composite_generator(
    name="precursor_pool_no_h2",
    methods=["libRoadRunner/Tellurium SBML ODE"],
    fidelity="real",
    description="NEW A control: reductant removed (feed_H2 = 0). The functional pool must collapse.",
    parameters={"feed_CO2": {"type": "float", "default": _CO2, "description": "Inorganic-carbon feed (M)"}},
    default_n_steps=240,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def precursor_pool_no_h2(core=None, *, feed_CO2=_CO2):
    return _pool_composite(feed_CO2=feed_CO2, feed_H2=_EPS, nh4=_NH4)


@composite_generator(
    name="precursor_pool_no_catalyst",
    methods=["libRoadRunner/Tellurium SBML ODE"],
    fidelity="real",
    description="NEW A control: mineral + base catalyst sites = 0. The functional pool must collapse.",
    parameters={"feed_CO2": {"type": "float", "default": _CO2, "description": "Inorganic-carbon feed (M)"}},
    default_n_steps=240,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def precursor_pool_no_catalyst(core=None, *, feed_CO2=_CO2):
    return _pool_composite(feed_CO2=feed_CO2, feed_H2=_H2, nh4=_NH4,
                           kin_overrides={"sites_mineral": _EPS, "sites_base": _EPS})


@composite_generator(
    name="precursor_pool_no_gradient",
    methods=["libRoadRunner/Tellurium SBML ODE"],
    fidelity="real",
    description=("NEW A control: no sustained vent resupply (k_feed = 0) - the "
                 "disequilibrium the pH/redox gradient maintains is off. The pool must collapse."),
    parameters={"feed_CO2": {"type": "float", "default": _CO2, "description": "Inorganic-carbon feed (M)"}},
    default_n_steps=240,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def precursor_pool_no_gradient(core=None, *, feed_CO2=_CO2):
    return _pool_composite(feed_CO2=feed_CO2, feed_H2=_H2, nh4=_NH4,
                           kin_overrides={"k_feed": _EPS})
