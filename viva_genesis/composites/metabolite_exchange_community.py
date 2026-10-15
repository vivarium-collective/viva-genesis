"""Metabolite-exchange community — og-07 rebuilt on real chemistry (Phase 8).

One layer generator behind two faces: every agent in the ``agents`` map
carries a model class of the ``proto_ecology`` face (``model_proto_ecology``:
reaction_universe | null_network — the Phase-3 network inside the protocell,
masked to the agent's **lineage repertoire**), and the pore they sit in is
shaped by a class of the ``localization`` face (``model_localization``: the
Phase-4 per-species enrichment along the pore). ``SpatialCouplingStep`` fires
the exchange rules of the ``BigraphicalReactiveSystem`` every tick (uptake /
secretion through species-specific permeabilities, pore diffusion, feed /
washout), ``EcologyReducerStep`` recomputes og-07's gate readouts from the
agents map, and ``EcologyElementLedgerProcess`` audits C / N / P over agents
+ field.

Arms (the og-07-alt study):

* ``lineages="fixer:4,reducer:4"`` (canonical) — two incomplete lineages, the
  carboxylating one and the hydrogenating one, interleaved along the pore.
* ``lineages="fixer:8"`` / ``"reducer:8"`` — the monocultures (same cell
  count, one repertoire): what each lineage can do alone.
* ``coupling="private"`` — the isolated counterfactual: the same assignment,
  every agent exchanging only with its own copy of the background, so nothing
  one agent secretes reaches another.
* ``lineages="generalist:8"`` — complete cells (every rule in one agent).
* ``model_proto_ecology="null_network"`` — the rewired-chemistry control.

Positions are fixed (the recorded Phase-8 decision: point agents on the
fields first; a motion model is deferred).
"""

from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from .. import models
from ..ecology.proto_ecology import (DEFAULT_PERMEABILITY, PERMEABILITY_CLASSES, REPERTOIRES, CANONICAL_TO_UNIVERSE,
                                     field_species, function_names)
from ..protometabolism import universe as U
from ..multisolute_localization import _default_species_params

_COMMUNITY = ("metacommunity_robustness", "isolated_robustness", "robustness_gain", "capability_diversity",
              "mean_capability", "luca_capability_overlap", "n_functions_union", "n_functions_produced_union",
              "n_functions_acquired", "max_cell_completeness")
_LEDGER = ("C_total", "N_total", "P_total", "C_residual", "N_residual", "P_residual", "C_residual_max",
           "N_residual_max", "P_residual_max", "carbon_degraded", "exchange_firings_total", "element_ledger_ok")
_AGENT_SCALARS = ("net_carbon_flux", "h2_consumption", "co2_fixation", "dissipation", "element_residual",
                  "carbon_degraded", "total_organic_carbon", "n_persistent_species", "catalyst_saturation")
_EMIT_SCALARS = {**{k: ["community", k] for k in _COMMUNITY}, **{k: ["ledger", k] for k in _LEDGER},
                 "cross_lineage_flux_total": ["exchange", "cross_lineage_flux_total"], "global_time": ["global_time"]}
_EMIT_TREES = {"functions_union": ["community", "functions_union"], "functions_by_lineage": ["community", "functions_by_lineage"],
               "firings": ["exchange", "firings"], "firing_moles": ["exchange", "firing_moles"],
               "cross_lineage_flux": ["exchange", "cross_lineage_flux"],
               "metabolism": ["metabolism"], "rates": ["rates"], "field": ["field", "cells"]}
_EMIT_PATHS = ["/".join(v) for v in {**_EMIT_SCALARS, **_EMIT_TREES}.values()]


def parse_lineages(spec: str) -> list[str]:
    """``"fixer:4,reducer:4"`` -> ``["fixer", "fixer", ..., "reducer", ...]``."""
    out = []
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        name, _, n = part.partition(":")
        name = name.strip()
        if name not in REPERTOIRES:
            raise KeyError(f"unknown lineage {name!r}; have {sorted(REPERTOIRES)}")
        out.extend([name] * (int(n) if n else 1))
    if not out:
        raise ValueError("lineages must name at least one agent")
    return out


def place_agents(names: list[str], n_cells: int, placement: str, seed: int) -> list[float]:
    """Fractional position along the pore (0 = inlet, 1 = trap end) per agent."""
    import numpy as np
    n = len(names)
    if placement == "segregated":
        # each lineage in its own block along the pore, in the order given
        order = list(range(n))
    elif placement == "mixed":
        # interleave the lineages so every cell holds a mix
        by = {}
        for i, nm in enumerate(names):
            by.setdefault(nm, []).append(i)
        order = []
        while any(by.values()):
            for nm in list(by):
                if by[nm]:
                    order.append(by[nm].pop(0))
    elif placement == "random":
        order = list(np.random.default_rng(int(seed)).permutation(n))
    else:
        raise ValueError(f"placement must be mixed | segregated | random, got {placement!r}")
    pos = [0.0] * n
    for slot, idx in enumerate(order):
        pos[idx] = (slot + 0.5) / n
    return pos


@composite_generator(
    name="metabolite_exchange_community",
    methods=["real reaction network per protocell (libRoadRunner, Phase-3 universe)", "lineage rule repertoires",
             "bigraphical reactive system of matter-exchange rules", "Phase-4 enrichment-shaped pore field",
             "cross-system C/N/P element ledger"],
    fidelity="real",
    description=(
        "og-07's metacommunity rebuilt on real chemistry (Phase 8): N protocells in the agents map, each running "
        "the Phase-3 rule-generated reaction universe (libRoadRunner, eQuilibrator dG') masked to its lineage's "
        "catalyst repertoire (fixer: CO2 reduction + carboxylations; reducer: hydrogenations; condenser: aldol / "
        "formose; generalist: all), pointed at fixed cells of a pore whose background the Phase-4 localization "
        "class shapes species by species. A SpatialCouplingStep fires the exchange rules of a bigraphical reactive "
        "system every tick (uptake / secretion through size- and charge-dependent permeabilities, pore diffusion, "
        "feed / washout) and counts the firings; an EcologyReducerStep recomputes og-07's gate readouts from the "
        "agents (present vs produced functions); an EcologyElementLedgerProcess audits C / N / P over agents + "
        "field. coupling=private is the isolated counterfactual; model_proto_ecology=null_network the rewired control."
    ),
    parameters={
        **models.model_parameters("proto_ecology", "localization",
                                  defaults={"proto_ecology": "reaction_universe", "localization": "multisolute_surrogate"}),
        "lineages": {"type": "string", "default": "fixer:4,reducer:4",
                     "description": "Agents per lineage repertoire, e.g. fixer:4,reducer:4 | fixer:8 | generalist:8"},
        "placement": {"type": "string", "default": "mixed", "description": "mixed | segregated | random positions along the pore (fixed; no motion)"},
        "coupling": {"type": "string", "default": "shared", "description": "shared = agents exchange with a common pore field; private = each agent sees only the background (isolated counterfactual)"},
        "n_cells": {"type": "integer", "default": 4, "description": "Pore field cells along the flow axis [vg-data: hypothetical]"},
        "pool_volume_multiplier": {"type": "float", "default": 10.0, "description": "Pore volume per agent volume [vg-data: hypothetical]"},
        "k_wash": {"type": "float", "default": 0.05, "description": "Pore feed / washout rate (1/s); 1/residence time [vg-data: inferred, swept]"},
        "k_diffusion": {"type": "float", "default": 0.1, "description": "Exchange rate between neighbouring cells (1/s) [vg-data: hypothetical]"},
        **{p: {"type": "float", "default": DEFAULT_PERMEABILITY[p],
               "description": f"Membrane permeability class {p} (m/s) [vg-data: {'hypothetical, swept' if p == 'p_diacid' else 'extrapolated'}]"}
           for p in PERMEABILITY_CLASSES},
        "feed_CO2": {"type": "float", "default": 1.4e-3, "description": "Inlet CO2 (M) [vg-data: calibrated, Phase-1 posterior]"},
        "feed_H2": {"type": "float", "default": 1.08e-2, "description": "Inlet H2 (M) [vg-data: calibrated, Phase-1 posterior]"},
        "feed_pyruvate": {"type": "float", "default": 1.0e-4, "description": "Inlet pyruvate (M) [vg-data: inferred]"},
        "feed_formate": {"type": "float", "default": 0.0, "description": "Inlet formate (M) [vg-data: hypothetical]"},
        "feed_ammonium": {"type": "float", "default": 5.0e-5, "description": "Inlet ammonium (M) [vg-data: extrapolated]"},
        "feed_phosphate": {"type": "float", "default": 1.0e-5, "description": "Inlet phosphate (M) [vg-data: extrapolated]"},
        "peclet": {"type": "float", "default": 8.0, "description": "Pore advective Peclet for the localization class"},
        "soret_scale": {"type": "float", "default": 1.0, "description": "Scale on the per-species Soret coefficients"},
        "null_seed": {"type": "integer", "default": 0, "description": "Rewiring seed for the null_network class"},
        "function_floor": {"type": "float", "default": 1.0e-9, "description": "Concentration floor for holding a function (M) [vg-data: inferred]"},
        "seed": {"type": "integer", "default": 1, "description": "Placement seed (random placement only)"},
    },
    default_n_steps=200,
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def metabolite_exchange_community(core=None, *, model_proto_ecology="reaction_universe",
                                  model_localization="multisolute_surrogate", lineages="fixer:4,reducer:4",
                                  placement="mixed", coupling="shared", n_cells=4, pool_volume_multiplier=10.0,
                                  k_wash=0.05, k_diffusion=0.1, p_gas=DEFAULT_PERMEABILITY["p_gas"],
                                  p_small_neutral=DEFAULT_PERMEABILITY["p_small_neutral"],
                                  p_large_neutral=DEFAULT_PERMEABILITY["p_large_neutral"],
                                  p_monoacid=DEFAULT_PERMEABILITY["p_monoacid"], p_diacid=DEFAULT_PERMEABILITY["p_diacid"],
                                  p_ion=DEFAULT_PERMEABILITY["p_ion"], feed_CO2=1.4e-3, feed_H2=1.08e-2,
                                  feed_pyruvate=1.0e-4, feed_formate=0.0, feed_ammonium=5.0e-5, feed_phosphate=1.0e-5,
                                  peclet=8.0, soret_scale=1.0, null_seed=0, function_floor=1.0e-9, seed=1):
    if core is None:
        core = build_core()
    net_addr = models.resolve_checked(core, "proto_ecology", model_proto_ecology)
    loc_addr = models.resolve_checked(core, "localization", model_localization)
    if coupling not in ("shared", "private"):
        raise ValueError(f"coupling must be shared | private, got {coupling!r}")
    names = parse_lineages(lineages)
    n_cells = max(int(n_cells), 1)
    positions = place_agents(names, n_cells, str(placement), int(seed))
    v_agent = 1.0e-18
    cell_volume = float(pool_volume_multiplier) * v_agent * len(names) / n_cells
    feed = {CANONICAL_TO_UNIVERSE["CO2"]: float(feed_CO2), CANONICAL_TO_UNIVERSE["H2"]: float(feed_H2),
            CANONICAL_TO_UNIVERSE["pyruvate"]: float(feed_pyruvate), CANONICAL_TO_UNIVERSE["formate"]: float(feed_formate),
            "ammonium": float(feed_ammonium), "phosphate": float(feed_phosphate)}
    feed = {s: v for s, v in feed.items() if v > 0.0}
    perm = {"p_gas": float(p_gas), "p_small_neutral": float(p_small_neutral), "p_large_neutral": float(p_large_neutral),
            "p_monoacid": float(p_monoacid), "p_diacid": float(p_diacid), "p_ion": float(p_ion)}
    sp = _default_species_params()
    for p in sp.values():
        p["soret"] = float(p["soret"]) * float(soret_scale)

    species = field_species(4)
    zero = {s: 0.0 for s in species}
    agents, lineage_store, metab, rates, doc = {}, {}, {}, {}, {}
    for i, (name, x) in enumerate(zip(names, positions)):
        aid = f"{name}-{i}"
        agents[aid] = {"id": aid, "volume": v_agent, "internal": {"dissolved": dict(zero)}}
        lineage_store[aid] = {"lineage_id": name, "parent_id": "", "generation": 0, "position": (float(x), 0.0),
                              "population": 1}
        metab[aid] = {"functions_produced": {f: 0.0 for f in function_names(4)}, "rule_flux": {r: 0.0 for r in U.RULES}}
        rates[aid] = {k: 0.0 for k in _AGENT_SCALARS}
        doc[f"network_{aid}"] = {
            "_type": "process", "address": net_addr, "interval": 1.0,
            "config": {"lineage": name, "volume": v_agent, "null_seed": int(null_seed), "conc_floor": float(function_floor)},
            "inputs": {"internal": ["agents", aid, "internal", "dissolved"]},
            "outputs": {"internal": ["agents", aid, "internal", "dissolved"],
                        "functions_produced": ["metabolism", aid, "functions_produced"],
                        "rule_flux": ["metabolism", aid, "rule_flux"],
                        **{k: ["rates", aid, k] for k in _AGENT_SCALARS}},
        }
    cells = {f"c{i}": dict(zero) for i in range(n_cells)}
    doc.update({
        "localization": {
            "_type": "process", "address": loc_addr, "interval": 1.0,
            "config": {"peclet": float(peclet), "species_params": sp},
            "inputs": {"temperature": ["env", "temperature"], "porosity": ["env", "porosity"],
                       "flow_velocity": ["env", "flow_velocity"], "species_params": ["env", "species_params"]},
            "outputs": {"enrichment": ["field", "enrichment"], "flux_divergence_residual": ["field", "flux_residual"]},
        },
        "coupling": {
            "_type": "step", "address": "local:SpatialCouplingStep",
            "config": {"n_cells": n_cells, "cell_volume": cell_volume, "k_wash": float(k_wash), "k_diffusion": float(k_diffusion),
                       "coupling": str(coupling), "feed": feed, **perm},
            "inputs": {"agents": ["agents"], "lineages": ["lineages"], "field": ["field", "cells"],
                       "enrichment": ["field", "enrichment"], "global_time": ["global_time"]},
            "outputs": {"agents": ["agents"], "field": ["field", "cells"], "firings": ["exchange", "firings"],
                        "firing_moles": ["exchange", "firing_moles"], "cross_lineage_flux": ["exchange", "cross_lineage_flux"],
                        "cross_lineage_flux_total": ["exchange", "cross_lineage_flux_total"],
                        "inflow": ["exchange", "inflow"], "outflow": ["exchange", "outflow"], "exchange": ["exchange", "exchange"]},
        },
        "reducer": {
            "_type": "step", "address": "local:EcologyReducerStep",
            "config": {"function_floor": float(function_floor)},
            "inputs": {"agents": ["agents"], "lineages": ["lineages"], "metabolism": ["metabolism"], "rates": ["rates"],
                       "global_time": ["global_time"]},
            "outputs": {**{k: ["community", k] for k in _COMMUNITY}, "functions_union": ["community", "functions_union"],
                        "functions_by_lineage": ["community", "functions_by_lineage"]},
        },
        "element_ledger": {
            "_type": "process", "address": "local:EcologyElementLedgerProcess", "interval": 1.0,
            "config": {"cell_volume": cell_volume},
            "inputs": {"agents": ["agents"], "field": ["field", "cells"], "inflow": ["exchange", "inflow"],
                       "outflow": ["exchange", "outflow"], "rates": ["rates"], "firings": ["exchange", "firings"]},
            "outputs": {k: ["ledger", k] for k in _LEDGER},
        },
        "env": {"temperature": 333.15, "porosity": 0.3, "flow_velocity": 1.0e-4, "species_params": sp},
        "agents": agents, "lineages": lineage_store, "metabolism": metab, "rates": rates,
        "field": {"cells": cells, "enrichment": {}, "flux_residual": 0.0},
        "exchange": {"firings": {}, "firing_moles": {}, "cross_lineage_flux": {}, "cross_lineage_flux_total": 0.0,
                     "inflow": {}, "outflow": {}, "exchange": {}},
        "community": {**{k: 0.0 for k in _COMMUNITY}, "functions_union": {}, "functions_by_lineage": {}},
        "ledger": {k: 0.0 for k in _LEDGER},
        "emitter": {
            "_type": "step", "address": "local:RAMEmitter",
            "config": {"emit": {**{k: "float" for k in _EMIT_SCALARS},
                                **{k: ("map[map[vg_concentration]]" if k == "field" else "map[map[float]]" if k == "rates" else "tree")
                                   for k in _EMIT_TREES}}},
            "inputs": {k: list(v) for k, v in {**_EMIT_SCALARS, **_EMIT_TREES}.items()},
        },
    })
    return doc


# --------------------------------------------------------------------------- #
# Reducers (module-level, picklable)
# --------------------------------------------------------------------------- #
def _last(rows, key):
    return float(rows[-1].get(key, float("nan"))) if rows else float("nan")


def _settled(rows, key, frac=0.25):
    n = max(1, int(round(len(rows) * frac)))
    t = [float(r.get(key, float("nan"))) for r in rows[-n:]]
    return sum(t) / len(t) if t else float("nan")


def settled_functions(rows, frac=0.25) -> dict:
    """Per function: the settled (last-quartile mean) max concentration across agents."""
    n = max(1, int(round(len(rows) * frac)))
    acc: dict[str, list] = {}
    for r in rows[-n:]:
        for f, d in (r.get("functions_union") or {}).items():
            acc.setdefault(f, []).append(float(d.get("max_conc", 0.0)))
    return {f: sum(v) / n for f, v in acc.items()}


def settled_robustness(rows) -> float:
    return _settled(rows, "metacommunity_robustness")


def settled_isolated_robustness(rows) -> float:
    return _settled(rows, "isolated_robustness")


def settled_robustness_gain(rows) -> float:
    return _settled(rows, "robustness_gain")


def settled_luca_overlap(rows) -> float:
    return _settled(rows, "luca_capability_overlap")


def settled_mean_capability(rows) -> float:
    return _settled(rows, "mean_capability")


def final_max_cell_completeness(rows) -> float:
    return _last(rows, "max_cell_completeness")


def final_n_functions_union(rows) -> float:
    return _last(rows, "n_functions_union")


def element_residual_max(rows) -> float:
    return max(max(float(r.get("C_residual_max", 0.0)), float(r.get("N_residual_max", 0.0)),
                   float(r.get("P_residual_max", 0.0))) for r in rows) if rows else float("nan")


def element_ledger_ok_final(rows) -> float:
    return _last(rows, "element_ledger_ok")


def cross_lineage_flux_total(rows) -> float:
    return _last(rows, "cross_lineage_flux_total")


def exchange_firings_total(rows) -> float:
    return _last(rows, "exchange_firings_total")


PHASE8_REDUCERS = {
    "metacommunity_robustness": settled_robustness, "isolated_robustness": settled_isolated_robustness,
    "robustness_gain": settled_robustness_gain, "luca_capability_overlap": settled_luca_overlap,
    "mean_cell_completeness": settled_mean_capability, "max_cell_completeness": final_max_cell_completeness,
    "n_functions_union": final_n_functions_union, "element_residual_max": element_residual_max,
    "element_ledger_ok": element_ledger_ok_final, "cross_lineage_flux_total": cross_lineage_flux_total,
    "exchange_firings_total": exchange_firings_total,
}

__all__ = ["metabolite_exchange_community", "parse_lineages", "place_agents", "settled_functions", "PHASE8_REDUCERS"]
