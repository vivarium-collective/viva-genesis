"""The open chemical network — og-02's reactor behind the proto_metabolism face (Phase 3).

One layer generator, three model classes selected through the typed face
``viva_genesis.models.INTERFACES["proto_metabolism"]``:

* ``curated_rtca`` — og-02's hand-curated rTCA-fragment SBML
  (``RoadRunnerNetworkProcess``; the existing passing result, now one class
  among three).
* ``reaction_universe`` — the rule-generated C/H/O universe
  (``ReactionUniverseProcess``): Wołos-2020-style rules, eQuilibrator ΔG',
  catalyst limits, degradation; motifs detected post hoc.
* ``null_network`` — the matched degree-preserving null
  (``NullNetworkProcess``; ``null_seed`` picks the draw).

All three run on the real libRoadRunner engine under the same feed, and a
:class:`~viva_genesis.ledger.NetworkLedgerProcess` audits the element /
carbon / free-energy witnesses (the curated class publishes none, so its
ledger inputs stay at their zero defaults — its element balance is checked
post hoc in the study's enrichment script from its SBML).

The feed is the **Phase-1 posterior**: ``feed_CO2`` / ``feed_H2`` default to
the og-cal-vent-environment example point recorded in the vg-data package
``reaction_universe`` (DIC 1.4 mM, dissolved H2 10.8 mmol/kg), so
``package.to_config(values=draw)`` on a posterior draw re-parameterises the
universe — the flagship chain "Phase 1 posterior → Phase 3 universe".
"""

from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from .. import models

_NET_PORTS = ("net_carbon_flux", "autocatalytic_gain", "network_connected", "total_organic_carbon",
              "n_persistent_species", "n_autocatalytic_motifs", "autocatalytic_core_size",
              "dissipation", "element_residual", "carbon_residual", "catalyst_saturation")
_SPECIES_PORTS = ("formate", "formaldehyde", "acetate", "glycolaldehyde", "pyruvate", "OAA", "malate", "succinate")
_LEDGER_PORTS = ("element_residual_max", "carbon_residual_max", "dissipation_min", "dissipated_energy",
                 "free_energy_directionality", "ledger_ok")

_EMIT_PATHS = ([f"flux/{p}" for p in ("net_carbon_flux", "autocatalytic_gain", "network_connected")]
               + [f"net/{p}" for p in _SPECIES_PORTS + ("total_organic_carbon",)]
               + [f"stats/{p}" for p in ("n_persistent_species", "n_autocatalytic_motifs",
                                         "autocatalytic_core_size", "catalyst_saturation")]
               + [f"witness/{p}" for p in ("dissipation", "element_residual", "carbon_residual")]
               + [f"ledger/{p}" for p in _LEDGER_PORTS] + ["global_time"])

_WIRES = {
    **{p: ["flux", p] for p in ("net_carbon_flux", "autocatalytic_gain", "network_connected")},
    **{p: ["net", p] for p in _SPECIES_PORTS + ("total_organic_carbon",)},
    **{p: ["stats", p] for p in ("n_persistent_species", "n_autocatalytic_motifs",
                                 "autocatalytic_core_size", "catalyst_saturation")},
    **{p: ["witness", p] for p in ("dissipation", "element_residual", "carbon_residual")},
    **{p: ["ledger", p] for p in _LEDGER_PORTS},
    "global_time": ["global_time"],
}

# Nominal feed = the Phase-1 posterior example point (vg-data reaction_universe).
_FEED_CO2, _FEED_H2, _FEED_PYR = 1.4e-3, 1.08e-2, 1.0e-4


@composite_generator(
    name="open_chemical_network",
    methods=["libRoadRunner/Tellurium SBML ODE", "rule-based network generation",
             "eQuilibrator component-contribution dG'", "post-hoc autocatalytic-motif detection",
             "element + free-energy ledger"],
    fidelity="real",
    description=(
        "og-02's continuous-feed reactor rebuilt as the Phase-3 open chemical network: the reaction "
        "network is a model CLASS on the proto_metabolism face (model_proto_metabolism: curated_rtca | "
        "reaction_universe | null_network), all three integrated by the genuine libRoadRunner engine "
        "under the same Phase-1-posterior feed (CO2, H2, pyruvate), graded by one class-agnostic "
        "post-hoc detector (flux-carrying simple cycles with stoichiometric gain > 1) and audited by a "
        "NetworkLedgerProcess (exact element residual, integrated carbon balance, dissipation >= 0). "
        "The universe class is generated from Wolos-2020-style rules over linear C/H/O skeletons with "
        "eQuilibrator dG' (vg-data package reaction_universe); the null class is its degree-preserving, "
        "carbon-matched rewiring."
    ),
    parameters={
        **models.model_parameters("proto_metabolism", defaults={"proto_metabolism": "reaction_universe"}),
        "feed_CO2": {"type": "float", "default": _FEED_CO2,
                     "description": "Vent-buffered CO2 set-point (M) [vg-data: calibrated, Phase-1 posterior]"},
        "feed_H2": {"type": "float", "default": _FEED_H2,
                    "description": "Vent-buffered H2 set-point (M) [vg-data: calibrated, Phase-1 posterior]"},
        "feed_pyruvate": {"type": "float", "default": _FEED_PYR,
                          "description": "Pyruvate CSTR inflow (M) from og-01 reduced carbon [vg-data: inferred]"},
        "feed_formaldehyde": {"type": "float", "default": 0.0,
                              "description": "Formaldehyde CSTR inflow (M); 0 canonical, 1e-3 in the formose arm [vg-data: hypothetical]"},
        "k_wash": {"type": "float", "default": 0.05,
                   "description": "CSTR washout / dilution rate (1/s) [vg-data: inferred]"},
        "null_seed": {"type": "integer", "default": 0,
                      "description": "Null-network draw (null_network class only)"},
        "max_carbons": {"type": "integer", "default": 4,
                        "description": "Carbon cap of the generated universe (reaction_universe / null_network) [vg-data: hypothetical]"},
    },
    default_n_steps=120,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def open_chemical_network(core=None, *, model_proto_metabolism="reaction_universe",
                          feed_CO2=_FEED_CO2, feed_H2=_FEED_H2, feed_pyruvate=_FEED_PYR,
                          feed_formaldehyde=0.0, k_wash=0.05, null_seed=0, max_carbons=4):
    if core is None:
        core = build_core()
    address = models.resolve_checked(core, "proto_metabolism", model_proto_metabolism)

    if model_proto_metabolism == "curated_rtca":
        config = {"k_wash": float(k_wash)}
        inputs = {"feed_pyruvate": ["feed", "pyruvate"], "feed_CO2": ["feed", "CO2"]}
        outputs = {"OAA": ["net", "OAA"], "malate": ["net", "malate"], "succinate": ["net", "succinate"],
                   "acetate": ["net", "acetate"],
                   "net_carbon_flux": ["flux", "net_carbon_flux"],
                   "autocatalytic_gain": ["flux", "autocatalytic_gain"],
                   "network_connected": ["flux", "network_connected"]}
    else:
        config = {"k_wash": float(k_wash), "max_carbons": int(max_carbons)}
        if model_proto_metabolism == "null_network":
            config["null_seed"] = int(null_seed)
        inputs = {"feed_CO2": ["feed", "CO2"], "feed_H2": ["feed", "H2"], "feed_pyruvate": ["feed", "pyruvate"],
                  "feed_formaldehyde": ["feed", "formaldehyde"], "feed_formate": ["feed", "formate"],
                  "feed_acetate": ["feed", "acetate"]}
        outputs = {**{p: ["flux", p] for p in ("net_carbon_flux", "autocatalytic_gain", "network_connected")},
                   **{p: ["net", p] for p in _SPECIES_PORTS + ("total_organic_carbon",)},
                   **{p: ["stats", p] for p in ("n_persistent_species", "n_autocatalytic_motifs",
                                                "autocatalytic_core_size", "catalyst_saturation")},
                   **{p: ["witness", p] for p in ("dissipation", "element_residual", "carbon_residual")}}

    return {
        "network": {
            "_type": "process", "address": address, "config": config, "interval": 1.0,
            "inputs": inputs, "outputs": outputs,
        },
        "network_ledger": {
            "_type": "process", "address": "local:NetworkLedgerProcess", "config": {}, "interval": 1.0,
            "inputs": {"element_residual": ["witness", "element_residual"],
                       "carbon_residual": ["witness", "carbon_residual"],
                       "dissipation": ["witness", "dissipation"],
                       "total_organic_carbon": ["net", "total_organic_carbon"]},
            "outputs": {p: ["ledger", p] for p in _LEDGER_PORTS},
        },
        "feed": {"CO2": float(feed_CO2), "H2": float(feed_H2), "pyruvate": float(feed_pyruvate),
                 "formaldehyde": float(feed_formaldehyde), "formate": 0.0, "acetate": 0.0},
        "flux": {"net_carbon_flux": 0.0, "autocatalytic_gain": 0.0, "network_connected": 0.0},
        "net": {**{p: 0.0 for p in _SPECIES_PORTS}, "total_organic_carbon": 0.0},
        "stats": {"n_persistent_species": 0.0, "n_autocatalytic_motifs": 0.0,
                  "autocatalytic_core_size": 0.0, "catalyst_saturation": 0.0},
        "witness": {"dissipation": 0.0, "element_residual": 0.0, "carbon_residual": 0.0},
        "ledger": {"element_residual_max": 0.0, "carbon_residual_max": 0.0, "dissipation_min": 0.0,
                   "dissipated_energy": 0.0, "free_energy_directionality": 1.0, "ledger_ok": 1.0},
        "emitter": {
            "_type": "step", "address": "local:RAMEmitter",
            "config": {"emit": {k: "float" for k in _WIRES}},
            "inputs": {k: list(v) for k, v in _WIRES.items()},
        },
    }


# --------------------------------------------------------------------------- #
# Reducers (module-level, picklable)
# --------------------------------------------------------------------------- #
def _tail(rows, key, frac=0.25):
    n = max(1, int(round(len(rows) * frac)))
    return [float(r.get(key, float("nan"))) for r in rows[-n:]]


def settled_net_carbon_flux(rows) -> float:
    t = _tail(rows, "net_carbon_flux")
    return sum(t) / len(t) if t else float("nan")


def final_n_motifs(rows) -> float:
    return float(rows[-1].get("n_autocatalytic_motifs", 0.0)) if rows else float("nan")


def final_core_size(rows) -> float:
    return float(rows[-1].get("autocatalytic_core_size", 0.0)) if rows else float("nan")


def final_n_persistent_species(rows) -> float:
    return float(rows[-1].get("n_persistent_species", 0.0)) if rows else float("nan")


def peak_autocatalytic_gain(rows) -> float:
    return max((float(r.get("autocatalytic_gain", 0.0)) for r in rows), default=float("nan"))


def settled_total_organic_carbon(rows) -> float:
    t = _tail(rows, "total_organic_carbon")
    return sum(t) / len(t) if t else float("nan")


def ledger_ok_final(rows) -> float:
    return float(rows[-1].get("ledger_ok", 0.0)) if rows else float("nan")


PHASE3_REDUCERS = {
    "settled_net_carbon_flux": settled_net_carbon_flux,
    "final_n_motifs": final_n_motifs,
    "final_core_size": final_core_size,
    "final_n_persistent_species": final_n_persistent_species,
    "peak_autocatalytic_gain": peak_autocatalytic_gain,
    "settled_total_organic_carbon": settled_total_organic_carbon,
    "ledger_ok": ledger_ok_final,
}
