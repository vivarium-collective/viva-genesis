"""A bigraphical reactive system for metabolite exchange (Phase 8).

In bigraph theory a *reactive system* is a set of reaction rules — a redex
pattern that is matched against the bigraph and a reactum that replaces it —
applied to a bigraph (here: the ``agents`` map of protocells pointed at cells
of the pore field). :class:`BigraphicalReactiveSystem` is the minimal, honest
version of that idea for Phase 8: every rule is a **matter-conserving
transfer** between two places of the bigraph (an agent's interior and its
field cell, or two neighbouring field cells, or a field cell and the pore's
feed), it is matched against the current state (a rule fires only where its
precondition holds — a concentration gradient in the right direction, a
permeant species, a neighbouring cell), and every firing is **counted** and
its moles **integrated** so the roadmap's "exchange-rule firing counts" are a
witness the study can grade, not a diagnostic afterthought.

No rule here moves a *capability*. og-07's capability vectors spread a
function symbolically (a neighbour "supplies the byproduct"); these rules move
molecules, and whether a function appears in a lineage that cannot make it is
then a consequence of the chemistry inside the agents and the flux between
them (the gate ``community-function-precedes-cell-completeness``).

Rules shipped:

* :class:`UptakeRule` / :class:`SecretionRule` — membrane permeation between
  an agent and the cell it sits in, species by species, as the *exact*
  pairwise relaxation of the two-compartment linear exchange over the tick
  (``k = P A / V_agent``; the equilibrium concentration is the volume-weighted
  mean; the same float leaves one place and enters the other). Uptake fires
  where the outside exceeds the inside, secretion where the inside exceeds
  the outside.
* :class:`PoreDiffusionRule` — exchange between neighbouring field cells
  (exact pairwise relaxation at ``k_diffusion``).
* :class:`PoreExchangeRule` — the pore's feed / washout: every cell relaxes
  toward its Phase-4 background (the feed scaled by the localization class's
  per-species enrichment at that cell) at ``k_wash``; the moles fed in and
  washed out are reported per element for the cross-system element ledger.

All rules operate on a plain working context (``RuleContext``) so they are
testable without process-bigraph; :class:`~viva_genesis.ecology.proto_ecology.SpatialCouplingStep`
builds the context from the bigraph state and writes the resulting deltas
back.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class Firing:
    rule: str
    subject: str          # agent id or cell key
    species: str
    moles: float          # moles moved INTO the subject (negative = out)


@dataclass
class RuleContext:
    """The working state the rules match against and mutate.

    ``agents``: ``{id: {"volume": L, "cell": cell_key, "internal": {species: M},
    "k": {species: 1/s}, "lineage": str}}``; ``cells``: ``{cell_key: {species: M}}``
    with one ``cell_volume`` (L); ``background``: ``{cell_key: {species: M}}``;
    ``elements``: ``{species: {"C": n, "N": n, "P": n}}``; ``dt`` in seconds.
    ``private`` = each agent exchanges with its own copy of the background
    (the isolated counterfactual — nothing an agent secretes reaches another).
    """

    agents: dict
    cells: dict
    cell_volume: float
    background: dict
    elements: dict
    dt: float = 1.0
    k_diffusion: float = 0.0
    k_wash: float = 0.0
    private: bool = False
    neighbours: dict = field(default_factory=dict)   # cell_key -> [cell_key]
    # accounting written by the rules
    firings: list = field(default_factory=list)
    inflow: dict = field(default_factory=lambda: {"C": 0.0, "N": 0.0, "P": 0.0})
    outflow: dict = field(default_factory=lambda: {"C": 0.0, "N": 0.0, "P": 0.0})

    def element_moles(self, species: str, moles: float) -> dict:
        e = self.elements.get(species) or {}
        return {k: moles * float(e.get(k, 0)) for k in ("C", "N", "P")}


def _relax_pair(c_a: float, v_a: float, c_b: float, v_b: float, k_a: float, dt: float) -> float:
    """Exact linear two-compartment exchange over ``dt``.

    ``dc_a/dt = k_a (c_b - c_a)``, ``dc_b/dt = k_a (v_a / v_b) (c_a - c_b)``;
    returns the moles moved into compartment ``a`` (negative = out of ``a``).
    """
    if k_a <= 0.0 or dt <= 0.0 or c_a == c_b:
        return 0.0
    k_tot = k_a * (1.0 + v_a / v_b)
    c_eq = (v_a * c_a + v_b * c_b) / (v_a + v_b)
    c_a_new = c_eq + (c_a - c_eq) * math.exp(-k_tot * dt)
    return (c_a_new - c_a) * v_a


class ExchangeRule:
    """Base class: ``matches`` yields the places the redex matches; ``apply``
    performs one conserving transfer and returns the moles moved into the
    rule's subject (0.0 = the rule did not fire there)."""

    name = "rule"

    def matches(self, ctx: RuleContext) -> Iterable[tuple]:
        raise NotImplementedError

    def apply(self, match: tuple, ctx: RuleContext) -> float:
        raise NotImplementedError


class _MembraneRule(ExchangeRule):
    direction = +1   # +1 uptake (outside -> inside), -1 secretion

    def matches(self, ctx: RuleContext):
        for aid, a in ctx.agents.items():
            outside = ctx.background[a["cell"]] if ctx.private else ctx.cells[a["cell"]]
            for s, k in a["k"].items():
                if k <= 0.0:
                    continue
                c_in = a["internal"].get(s, 0.0)
                c_out = outside.get(s, 0.0)
                if self.direction * (c_out - c_in) > 0.0:
                    yield (aid, s)

    def apply(self, match, ctx: RuleContext) -> float:
        aid, s = match
        a = ctx.agents[aid]
        c_in = a["internal"].get(s, 0.0)
        if ctx.private:
            # the agent sees the background at its cell; what it secretes is
            # washed away (an outflow the ledger counts) and nothing it takes up
            # depletes a shared pool (the feed replaces it: an inflow).
            c_out = ctx.background[a["cell"]].get(s, 0.0)
            moles = _relax_pair(c_in, a["volume"], c_out, 1.0e300, a["k"][s], ctx.dt)
            if moles == 0.0:
                return 0.0
            a["internal"][s] = c_in + moles / a["volume"]
            em = ctx.element_moles(s, abs(moles))
            tgt = ctx.inflow if moles > 0 else ctx.outflow
            for el, v in em.items():
                tgt[el] += v
        else:
            cell = ctx.cells[a["cell"]]
            c_out = cell.get(s, 0.0)
            moles = _relax_pair(c_in, a["volume"], c_out, ctx.cell_volume, a["k"][s], ctx.dt)
            if moles == 0.0:
                return 0.0
            a["internal"][s] = c_in + moles / a["volume"]
            cell[s] = c_out - moles / ctx.cell_volume
        ctx.firings.append(Firing(self.name, aid, s, moles))
        return moles


class UptakeRule(_MembraneRule):
    """outside > inside for a permeant species -> matter enters the agent."""
    name = "uptake"
    direction = +1


class SecretionRule(_MembraneRule):
    """inside > outside for a permeant species -> matter leaves the agent."""
    name = "secretion"
    direction = -1


class PoreDiffusionRule(ExchangeRule):
    """Neighbouring field cells exchange matter (exact pairwise relaxation)."""
    name = "diffusion"

    def matches(self, ctx: RuleContext):
        if ctx.k_diffusion <= 0.0 or ctx.private:
            return
        seen = set()
        for ck, nbrs in ctx.neighbours.items():
            for nk in nbrs:
                pair = tuple(sorted((ck, nk)))
                if pair in seen:
                    continue
                seen.add(pair)
                a, b = ctx.cells[pair[0]], ctx.cells[pair[1]]
                for s in set(a) | set(b):
                    if a.get(s, 0.0) != b.get(s, 0.0):
                        yield (pair[0], pair[1], s)

    def apply(self, match, ctx: RuleContext) -> float:
        ca_key, cb_key, s = match
        a, b = ctx.cells[ca_key], ctx.cells[cb_key]
        moles = _relax_pair(a.get(s, 0.0), ctx.cell_volume, b.get(s, 0.0), ctx.cell_volume, ctx.k_diffusion, ctx.dt)
        if moles == 0.0:
            return 0.0
        a[s] = a.get(s, 0.0) + moles / ctx.cell_volume
        b[s] = b.get(s, 0.0) - moles / ctx.cell_volume
        ctx.firings.append(Firing(self.name, ca_key, s, moles))
        return moles


class PoreExchangeRule(ExchangeRule):
    """Every cell relaxes toward its Phase-4 background at the pore exchange
    rate (feed in, washout out); the element moles crossing the pore boundary
    are integrated for the ledger."""
    name = "pore_exchange"

    def matches(self, ctx: RuleContext):
        if ctx.k_wash <= 0.0 or ctx.private:
            return
        for ck, cell in ctx.cells.items():
            bg = ctx.background.get(ck, {})
            for s in set(cell) | set(bg):
                if cell.get(s, 0.0) != bg.get(s, 0.0):
                    yield (ck, s)

    def apply(self, match, ctx: RuleContext) -> float:
        ck, s = match
        cell = ctx.cells[ck]
        c, b = cell.get(s, 0.0), ctx.background[ck].get(s, 0.0)
        c_new = b + (c - b) * math.exp(-ctx.k_wash * ctx.dt)
        moles = (c_new - c) * ctx.cell_volume
        if moles == 0.0:
            return 0.0
        cell[s] = c_new
        tgt = ctx.inflow if moles > 0 else ctx.outflow
        for el, v in ctx.element_moles(s, abs(moles)).items():
            tgt[el] += v
        ctx.firings.append(Firing(self.name, ck, s, moles))
        return moles


class ActiveUptakeRule(ExchangeRule):
    """Phase 9 — the *importer* innovation as an exchange rule: a saturable,
    powered transporter moves a substrate from the agent's field cell INTO the
    agent **against its gradient**. Fires for every agent carrying importer
    capacity (``ctx.agents[aid]["importer"] = {species: v_max}``, mol/s, already
    scaled by the lineage's machinery) wherever the cell holds the substrate;
    the moles moved are ``v_max * c_out / (K_m + c_out) * dt`` capped at what
    the cell holds and regulated so the inside never exceeds ``max_ratio`` x
    the outside (a transporter does not pump into a pool it has already
    filled). The transfer conserves matter (the same moles leave the cell
    and enter the agent); the free energy it costs — the thermodynamic minimum
    ``RT ln(c_in / c_out)`` per mole when uphill, 0 when downhill, divided by the
    transporter's coupling efficiency — is accumulated in ``ctx.import_energy``
    (joule) for the lineage's work budget. Nothing moves a capability."""

    name = "active_uptake"

    def __init__(self, k_m: float = 1.0e-5, efficiency: float = 0.5, rt_j: float = 2.68e3, max_ratio: float = 100.0,
                 targets: dict | None = None):
        self.k_m = float(k_m)              # molar half-saturation of the transporter
        self.efficiency = min(max(float(efficiency), 1e-6), 1.0)
        self.rt_j = float(rt_j)            # R T in J/mol
        self.max_ratio = float(max_ratio)  # regulation: no import once inside / outside reaches this
        self.targets = dict(targets or {})  # regulation: no import once the inside holds the set-point (molar)

    def matches(self, ctx: RuleContext):
        for aid, a in ctx.agents.items():
            cap = a.get("importer") or {}
            outside = ctx.background[a["cell"]] if ctx.private else ctx.cells[a["cell"]]
            for s, vmax in cap.items():
                c_out = outside.get(s, 0.0)
                c_in = a["internal"].get(s, 0.0)
                if vmax <= 0.0 or c_out <= 0.0 or c_in >= self.max_ratio * c_out:
                    continue
                if s in self.targets and c_in >= float(self.targets[s]):
                    continue
                if getattr(ctx, "import_budget", None) is not None and ctx.import_budget <= 0.0:
                    continue
                yield (aid, s)

    def apply(self, match, ctx: RuleContext) -> float:
        aid, s = match
        a = ctx.agents[aid]
        vmax = float(a["importer"][s])
        if ctx.private:
            outside = ctx.background[a["cell"]]
            c_out = outside.get(s, 0.0)
            moles = vmax * c_out / (self.k_m + c_out) * ctx.dt
        else:
            cell = ctx.cells[a["cell"]]
            c_out = cell.get(s, 0.0)
            moles = min(vmax * c_out / (self.k_m + c_out) * ctx.dt, c_out * ctx.cell_volume)
        c_in = a["internal"].get(s, 0.0)
        # regulation within the tick: the transporter stops at its set-point and at the ratio cap
        room = min(float(self.targets[s]) if s in self.targets else float("inf"), self.max_ratio * c_out) - c_in
        moles = min(moles, max(room, 0.0) * a["volume"])
        if moles <= 0.0:
            return 0.0
        if not ctx.private:
            cell[s] = c_out - moles / ctx.cell_volume
        # thermodynamic cost of concentrating (uphill only), per mole, over efficiency;
        # a finite work budget (ctx.import_budget, J) caps what can be moved this tick
        ratio = max(c_in, 1e-30) / max(c_out, 1e-30)
        cost = (self.rt_j * math.log(ratio) if ratio > 1.0 else 0.0) / self.efficiency
        budget = getattr(ctx, "import_budget", None)
        if budget is not None and cost > 0.0:
            allowed = budget / cost
            if allowed < moles:
                if not ctx.private:
                    cell[s] = c_out - allowed / ctx.cell_volume      # give back what the budget cannot pay for
                moles = allowed
            if moles <= 0.0:
                return 0.0
            ctx.import_budget = budget - moles * cost
        if ctx.private:
            for el, v in ctx.element_moles(s, moles).items():
                ctx.inflow[el] += v
        a["internal"][s] = c_in + moles / a["volume"]
        if not hasattr(ctx, "import_energy"):
            ctx.import_energy = 0.0
        ctx.import_energy += moles * cost
        ctx.firings.append(Firing(self.name, aid, s, moles))
        return moles


class BigraphicalReactiveSystem:
    """An ordered set of exchange rules with firing counters.

    ``fire(ctx)`` applies every rule wherever its redex matches (membrane
    rules first, then pore diffusion, then the pore's feed/washout), appends
    each firing to ``ctx.firings`` and accumulates per-rule counts and absolute
    moles in ``self.counts`` / ``self.moles`` across calls.
    """

    def __init__(self, rules: list[ExchangeRule] | None = None):
        self.rules = list(rules) if rules is not None else [UptakeRule(), SecretionRule(),
                                                              PoreDiffusionRule(), PoreExchangeRule()]
        self.counts = {r.name: 0 for r in self.rules}
        self.moles = {r.name: 0.0 for r in self.rules}

    def rule_names(self) -> list[str]:
        return [r.name for r in self.rules]

    def fire(self, ctx: RuleContext) -> dict:
        """Apply all rules once; return ``{"counts": per-rule firings this call,
        "moles": per-rule |moles| this call}``."""
        counts = {r.name: 0 for r in self.rules}
        moles = {r.name: 0.0 for r in self.rules}
        for rule in self.rules:
            for m in list(rule.matches(ctx)):
                moved = rule.apply(m, ctx)
                if moved != 0.0:
                    counts[rule.name] += 1
                    moles[rule.name] += abs(moved)
        for k in counts:
            self.counts[k] += counts[k]
            self.moles[k] += moles[k]
        return {"counts": counts, "moles": moles}


__all__ = ["Firing", "RuleContext", "ExchangeRule", "UptakeRule", "SecretionRule", "PoreDiffusionRule",
           "PoreExchangeRule", "ActiveUptakeRule", "BigraphicalReactiveSystem"]
