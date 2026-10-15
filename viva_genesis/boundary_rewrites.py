"""Phase 5 — endogenous boundary + growth/division as structural rewrites.

The flagship chain's step after localization (Phase 4): continuous chemistry →
a growing, dividing **individual**. Where Phases 1–4 model fields and pools, this
module models *individuals* as entries in an ``agents: map[vg_individual]`` store
that are **born, divided and removed by genuine process-bigraph structural
rewrites** (``_add`` / ``_divide`` / ``_remove``), with every rewrite audited for
matter conservation (see :class:`RewriteLedgerProcess` in ``ledger.py``).

Contents:

* :class:`AmphiphileSynthesisProcess` — makes amphiphile from
  ``molecules.dissolved.{acetate, formate}`` (the carbon_fixation products), so the
  boundary is built from the campaign's own chemistry rather than an added pool.
* :class:`ThioesterAminothiolMembraneProcess` — the ``thioester_aminothiol`` class
  on the ``boundary`` face (a different viability window than the fatty-acid vesicle).
* :class:`BoundaryFormationStep` (``_add``), :class:`DivisionStep` (``_divide``),
  :class:`LysisStep` / :class:`ExtinctionStep` (``_remove``) — the structural
  rewrites on the agents map.

Partition semantics (FMP §9.1, the recorded Phase-5 decision): an individual's
matter is stored as **amounts** in ``vg_individual.internal_amounts`` (moles) with
``volume`` separate, so ``_divide`` splits amounts + volume by halving — the
daughters' amounts sum to the mother's (partition residual 0) and the per-species
concentration is preserved.
"""
from __future__ import annotations

import itertools

from process_bigraph import Process, Step

# A monotonic id source for newly-formed / divided individuals (per process
# instance; the composite keys agents by these ids).
_id_counter = itertools.count(1)


def _new_individual(amounts, volume, *, generation=0, division_state=0.0,
                    integrity=1.0, area=0.0):
    """Build a minimal ``vg_individual``-shaped dict for the agents map. Matter
    is carried as ``internal_amounts`` (moles) so ``_divide`` conserves it."""
    return {
        "id": f"ind-{next(_id_counter)}",
        "volume": float(volume),
        "internal_amounts": {k: float(v) for k, v in amounts.items()},
        "boundary": {"area": float(area), "integrity": float(integrity)},
        "division_state": float(division_state),
        "persistence": float(generation),  # generation counter (reuses the time field)
    }


# ---------------------------------------------------------------------------
# Amphiphile synthesis — boundary built from the campaign's own carbon
# ---------------------------------------------------------------------------
class AmphiphileSynthesisProcess(Process):
    """Endogenous amphiphile production from the dissolved carbon pool.

    A coarse condensation of acetate + formate into a fatty-acid amphiphile
    (second-order in the limiting substrate), returning the amphiphile produced
    this step and the acetate/formate consumed — the matter link that lets the
    boundary form from chemistry rather than from an injected amphiphile pool.
    """

    config_schema = {
        "k_synth": {"_type": "float", "_default": 5.0e-2},   # 1/(M·s) condensation rate
        "stoich_acetate": {"_type": "float", "_default": 1.0},
        "stoich_formate": {"_type": "float", "_default": 1.0},
    }

    def inputs(self):
        return {"acetate": "float", "formate": "float"}

    def outputs(self):
        # amphiphile produced + the substrates consumed (negative deltas), as a
        # map so it composes onto molecules.dissolved.
        return {"amphiphile": "float", "acetate": "float", "formate": "float"}

    def update(self, state, interval):
        ac = max(float(state.get("acetate", 0.0)), 0.0)
        fo = max(float(state.get("formate", 0.0)), 0.0)
        k = float(self.config["k_synth"])
        sa = float(self.config["stoich_acetate"])
        sf = float(self.config["stoich_formate"])
        # rate limited by the scarcer substrate; cannot consume more than present
        rate = k * ac * fo
        produced = rate * interval
        produced = min(produced, ac / sa, fo / sf) if (sa > 0 and sf > 0) else produced
        return {
            "amphiphile": +produced,
            "acetate": -produced * sa,
            "formate": -produced * sf,
        }


# ---------------------------------------------------------------------------
# Alternative membrane chemistry — the thioester_aminothiol boundary class
# ---------------------------------------------------------------------------
class ThioesterAminothiolMembraneProcess(Process):
    """A second boundary class on the ``boundary`` face: a thioester/aminothiol
    membrane with a DIFFERENT viability window than the fatty-acid vesicle
    (narrower pH band, higher ionic + divalent tolerance). Coarse-grained, same
    retention/access individuality readout so the face stays comparable; the
    point is model-structure variation, not a second calibrated model."""

    config_schema = {
        "pka_bilayer": {"_type": "float", "_default": 7.2},
        "ph_window": {"_type": "float", "_default": 0.6},
        "i_tolerance": {"_type": "float", "_default": 0.6},       # tolerant of salt
        "vesicle_radius": {"_type": "float", "_default": 2.0e-7},
        "perm_base": {"_type": "float", "_default": 8.0e-4},
    }

    def inputs(self):
        return {"pH": "float", "ionic_strength": "float", "temperature": "float",
                "amphiphile": "float"}

    def outputs(self):
        return {
            "membrane_area": "overwrite[float]",
            "viable_compartments": "overwrite[integer]",
            "permeability": "overwrite[float]",
            "compartment_volume": "overwrite[float]",
            "retention": "overwrite[float]",
            "access": "overwrite[float]",
            "individuality_access": "overwrite[float]",
        }

    def update(self, state, interval):
        import math
        pH = float(state.get("pH", 8.0))
        I = float(state.get("ionic_strength", 0.3))
        amph = max(float(state.get("amphiphile", 0.0)), 0.0)
        cfg = self.config
        # viability: a Gaussian pH window around the bilayer pKa, salted off by a
        # tolerant ionic-strength logistic; needs amphiphile above a floor.
        ph_via = math.exp(-((pH - cfg["pka_bilayer"]) ** 2) / (2 * cfg["ph_window"] ** 2))
        i_via = 1.0 / (1.0 + (I / cfg["i_tolerance"]) ** 2)
        amph_via = amph / (amph + 1.0e-3)
        viability = ph_via * i_via * amph_via
        n_vesicles = int(round(1e3 * viability))
        r = cfg["vesicle_radius"]
        area_each = 4 * math.pi * r * r
        vol_each = (4.0 / 3.0) * math.pi * r ** 3 * 1000.0  # m^3 -> liter
        retention = viability
        access = 1.0 - 0.5 * viability        # tighter membrane -> less access
        return {
            "membrane_area": n_vesicles * area_each,
            "viable_compartments": n_vesicles,
            "permeability": cfg["perm_base"] * (1.0 - 0.3 * viability),
            "compartment_volume": n_vesicles * vol_each,
            "retention": retention,
            "access": access,
            "individuality_access": retention * access,
        }


# ---------------------------------------------------------------------------
# Structural rewrites on agents: map[vg_individual]
# ---------------------------------------------------------------------------
class BoundaryFormationStep(Step):
    """``_add`` an individual to the agents map when the endogenous amphiphile
    clears the critical aggregation concentration AND a viable boundary forms,
    seeding the new individual's matter FROM the localized pool (so matter is
    conserved — the amount withdrawn is reported for the rewrite ledger). No
    individual forms when synthesis is ablated (amphiphile stays below cac)."""

    config_schema = {
        "cac": {"_type": "float", "_default": 1.0e-3},            # critical aggregation conc (M)
        "seed_volume": {"_type": "float", "_default": 1.0e-12},   # liter
        "max_agents": {"_type": "integer", "_default": 50},
    }

    def inputs(self):
        return {"amphiphile": "float", "viable_compartments": "integer",
                "localized": "map[vg_amount]", "agents": "map[vg_individual]"}

    def outputs(self):
        # localized is emitted as a DELTA (map stores ADD, so the withdrawal is a
        # negative increment): the parcel that becomes the new individual's matter.
        return {"agents": "map[vg_individual]", "boundary_formed": "overwrite[float]",
                "localized": "map[vg_amount]"}

    def update(self, state):
        amph = float(state.get("amphiphile", 0.0))
        viable = int(state.get("viable_compartments", 0))
        agents = state.get("agents", {}) or {}
        localized = dict(state.get("localized", {}) or {})
        # endogenous gate: amphiphile above cac + a viable boundary + headroom
        if amph < float(self.config["cac"]) or viable <= 0 or \
                len(agents) >= int(self.config["max_agents"]):
            return {"boundary_formed": 0.0}
        # seed the individual's matter FROM the localized pool (withdraw half of
        # each species) so total matter is conserved across the _add.
        seed, withdraw = {}, {}
        for sp, amt in localized.items():
            take = 0.5 * float(amt)
            if take > 0:
                seed[sp] = take
                withdraw[sp] = -take               # negative delta on the map store
        if not seed:
            return {"boundary_formed": 0.0}
        ind = _new_individual(seed, self.config["seed_volume"],
                              integrity=1.0, area=amph)
        return {
            "agents": {"_add": {ind["id"]: ind}},
            "localized": withdraw,
            "boundary_formed": 1.0,
        }


class DivisionStep(Step):
    """``_divide`` any individual whose division_state has reached 1.0. The split
    halves ``internal_amounts`` (moles) and ``volume`` — the daughters' amounts
    sum to the mother's (partition residual 0) and the concentration is preserved
    — and increments each daughter's generation."""

    config_schema = {"division_threshold": {"_type": "float", "_default": 1.0}}

    def inputs(self):
        return {"agents": "map[vg_individual]"}

    def outputs(self):
        return {"agents": "map[vg_individual]", "division_count": "overwrite[float]",
                "partition_residual": "overwrite[float]"}

    def update(self, state):
        agents = state.get("agents", {}) or {}
        thr = float(self.config["division_threshold"])
        # The _divide sentinel carries ONE {mother, daughters} spec per apply, so
        # divide the first ready individual this tick; over successive ticks every
        # ready individual divides (and a lineage grows generation by generation).
        for key, ind in agents.items():
            if float(ind.get("division_state", 0.0)) < thr:
                continue
            amounts = ind.get("internal_amounts", {}) or {}
            vol = float(ind.get("volume", 0.0))
            gen = float(ind.get("persistence", 0.0)) + 1.0
            integ = float(ind.get("boundary", {}).get("integrity", 1.0))
            # explicit conserving partition: each daughter gets exactly half the
            # mother's amounts + half the volume, so the daughters' amounts sum to
            # the mother's (partition residual 0, FMP §9.1).
            half = {k: 0.5 * float(v) for k, v in amounts.items()}
            d0 = _new_individual(half, 0.5 * vol, generation=gen, integrity=integ)
            d1 = _new_individual(dict(half), 0.5 * vol, generation=gen, integrity=integ)
            partition_residual = max(
                (abs(float(amt) - (d0["internal_amounts"].get(sp, 0.0)
                                   + d1["internal_amounts"].get(sp, 0.0)))
                 for sp, amt in amounts.items()), default=0.0)
            return {
                "agents": {"_divide": {"mother": key,
                                       "daughters": {d0["id"]: d0, d1["id"]: d1}}},
                "division_count": 1.0,
                "partition_residual": float(partition_residual),
            }
        return {"division_count": 0.0, "partition_residual": 0.0}


class LysisStep(Step):
    """``_remove`` individuals whose boundary integrity has collapsed (osmotic
    lysis): their matter returns to the environment (reported for the ledger)."""

    config_schema = {"lysis_integrity": {"_type": "float", "_default": 0.1}}

    def inputs(self):
        return {"agents": "map[vg_individual]"}

    def outputs(self):
        return {"agents": "map[vg_individual]", "lysed": "overwrite[float]",
                "removed_matter": "overwrite[float]"}

    def update(self, state):
        agents = state.get("agents", {}) or {}
        thr = float(self.config["lysis_integrity"])
        dead = [k for k, ind in agents.items()
                if float(ind.get("boundary", {}).get("integrity", 1.0)) < thr]
        if not dead:
            return {"lysed": 0.0, "removed_matter": 0.0}
        removed = sum(sum(float(v) for v in (agents[k].get("internal_amounts", {}) or {}).values())
                      for k in dead)
        return {"agents": {"_remove": dead}, "lysed": float(len(dead)),
                "removed_matter": float(removed)}


class ExtinctionStep(Step):
    """``_remove`` individuals that have starved below a viable matter floor (no
    chemistry left to maintain the boundary)."""

    config_schema = {"min_matter": {"_type": "float", "_default": 1.0e-18}}

    def inputs(self):
        return {"agents": "map[vg_individual]"}

    def outputs(self):
        return {"agents": "map[vg_individual]", "extinct": "overwrite[float]",
                "removed_matter": "overwrite[float]"}

    def update(self, state):
        agents = state.get("agents", {}) or {}
        floor = float(self.config["min_matter"])
        gone = [k for k, ind in agents.items()
                if sum(float(v) for v in (ind.get("internal_amounts", {}) or {}).values()) < floor]
        if not gone:
            return {"extinct": 0.0, "removed_matter": 0.0}
        removed = sum(sum(float(v) for v in (agents[k].get("internal_amounts", {}) or {}).values())
                      for k in gone)
        return {"agents": {"_remove": gone}, "extinct": float(len(gone)),
                "removed_matter": float(removed)}
