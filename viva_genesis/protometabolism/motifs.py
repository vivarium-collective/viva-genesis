"""Post-hoc network analysis for the proto_metabolism classes (Phase 3).

Everything here reads a *running* libRoadRunner model (any class: the curated
rTCA SBML, a generated universe or a matched null) through its SBML and its
live reaction rates, so the same detector grades every class identically —
no class gets to declare its own motifs.

* :func:`network_from_roadrunner` — species / reactions (reactants, products,
  stoichiometries) via libsbml from ``rr.getSBML()``; exchange reactions are
  recognised by their one-sided stoichiometry.
* :func:`element_residual` — ``max |E S|`` over internal reactions given a
  formula per species: **exact 0** for a rule-generated universe (by
  construction); non-zero exposes a lumped or rewired reaction that creates or
  destroys atoms. This is the element ledger.
* :func:`autocatalytic_cycles` — the operational motif definition used by the
  gate ``motifs-emerge-not-imposed``: a simple cycle ``s0 -r0-> s1 -r1-> ... -> s0``
  in the directed species graph whose edges are reactions carrying net flux in
  the direction used (reactant ``s_i`` -> product ``s_{i+1}``), with
  stoichiometric gain ``Π (ν_product / ν_reactant) > 1`` — one turn of the
  cycle returns more than one copy of the seed. This is the "autocatalytic
  core" notion of Blokhuis, Lacoste & Nghe (2020) restricted to simple
  cycles (their type-I cores), enumerated by bounded DFS from the *doubling*
  edges (a product coefficient > 1 is the only way the gain can exceed 1), so
  the search is tractable on a ~400-reaction network.
* :func:`motif_gain` — og-02's ``autocatalytic_gain`` generalised: the
  autocatalytic net production of the seed through the cycle's rate-limiting
  step divided by the seed's first-order loss (washout + degradation).
  For the curated rTCA turn this reduces exactly to ``k_rtca [CO2] / k_wash``.
* :func:`enrichment` — universe count vs the matched-null distribution:
  empirical one-sided p, z-score, null mean / sd / max.
* :func:`flux_control_analysis` — scaled flux-control coefficients from
  libRoadRunner's elasticities and stoichiometry at the settled state, with the
  MCA summation theorem (``Σ_j C^J_j = 1`` for every flux; Kacser & Burns 1973)
  as the residual.
* :func:`stiffness_check` — Jacobian eigenvalue stiffness ratio at the
  reached state and the solution's sensitivity to tightening the CVODE
  tolerances (relative deviation of every species) — the integrator-tolerance
  witness the roadmap asks for.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


# --------------------------------------------------------------------------- #
# Network extraction
# --------------------------------------------------------------------------- #
@dataclass
class Rxn:
    id: str
    reactants: dict[str, float]
    products: dict[str, float]
    kind: str = "internal"     # internal | exchange


@dataclass
class Network:
    species: list[str]
    reactions: list[Rxn]
    boundary: set[str] = field(default_factory=set)

    def internal(self) -> list[Rxn]:
        return [r for r in self.reactions if r.kind == "internal"]


def network_from_roadrunner(rr, *, boundary_ok: bool = True) -> Network:
    """Read the stoichiometric network of a live roadrunner model via libsbml."""
    import libsbml
    doc = libsbml.readSBMLFromString(rr.getSBML())
    model = doc.getModel()
    boundary = {sp.getId() for sp in model.getListOfSpecies() if sp.getBoundaryCondition()}
    species = [sp.getId() for sp in model.getListOfSpecies() if sp.getId() not in boundary]
    rxns = []
    for r in model.getListOfReactions():
        re_ = {s.getSpecies(): float(s.getStoichiometry()) for s in r.getListOfReactants()}
        pr = {s.getSpecies(): float(s.getStoichiometry()) for s in r.getListOfProducts()}
        core_re = {k: v for k, v in re_.items() if k not in boundary}
        core_pr = {k: v for k, v in pr.items() if k not in boundary}
        kind = "internal" if (core_re and core_pr) else "exchange"
        rxns.append(Rxn(id=r.getId(), reactants=re_, products=pr, kind=kind))
    return Network(species=species, reactions=rxns, boundary=boundary)


def stoich_matrix(net: Network, reactions: list[Rxn] | None = None) -> tuple[np.ndarray, list[str]]:
    reactions = reactions if reactions is not None else net.reactions
    allsp = list(net.species) + sorted(net.boundary)
    idx = {s: i for i, s in enumerate(allsp)}
    S = np.zeros((len(allsp), len(reactions)))
    for j, r in enumerate(reactions):
        for s, n in r.reactants.items():
            S[idx[s], j] -= n
        for s, n in r.products.items():
            S[idx[s], j] += n
    return S, allsp


def element_residual(net: Network, formulas: dict[str, dict[str, int]],
                     *, elements=("C", "H", "O"), skip: set[str] | None = None) -> dict:
    """``max |E S|`` over internal reactions (species in ``skip`` — e.g. a tar
    sink — are ignored). Returns the worst residual per element and offenders."""
    skip = set(skip or ())
    internal = [r for r in net.internal() if not (set(r.reactants) | set(r.products)) & skip]
    S, allsp = stoich_matrix(net, internal)
    E = np.array([[float((formulas.get(s) or {}).get(el, 0)) for s in allsp] for el in elements])
    res = E @ S if internal else np.zeros((len(elements), 0))
    worst = np.abs(res).max(axis=0) if res.size else np.zeros(0)
    order = np.argsort(-worst) if worst.size else []
    return {
        "max_abs": float(np.abs(res).max()) if res.size else 0.0,
        "per_element": {el: (float(np.abs(res[i]).max()) if res.size else 0.0) for i, el in enumerate(elements)},
        "n_internal": len(internal),
        "n_unbalanced": int((worst > 1e-9).sum()) if worst.size else 0,
        "offenders": [{"reaction": internal[j].id,
                       "residual": {el: float(res[i, j]) for i, el in enumerate(elements)}}
                      for j in order[:5] if worst[j] > 1e-9],
    }


# --------------------------------------------------------------------------- #
# Autocatalytic cycles
# --------------------------------------------------------------------------- #
@dataclass
class Motif:
    species: list[str]          # s0, s1, ..., s_{n-1} (cycle order; s0 is the seed)
    reactions: list[str]        # r_i takes s_i -> s_{i+1 mod n}
    gain: float                 # stoichiometric gain per turn (> 1)
    min_flux: float             # rate-limiting net flux along the cycle (M/s)
    seed: str                   # the species the gain is referred to
    dynamic_gain: float = float("nan")

    def key(self) -> tuple:
        # rotation-invariant identity
        n = len(self.species)
        rots = [tuple(zip(self.species[i:] + self.species[:i], self.reactions[i:] + self.reactions[:i]))
                for i in range(n)]
        return min(rots)

    def to_dict(self) -> dict:
        return {"species": list(self.species), "reactions": list(self.reactions), "gain": self.gain,
                "min_flux": self.min_flux, "seed": self.seed, "dynamic_gain": self.dynamic_gain,
                "length": len(self.species)}


def oriented_edges(net: Network, rates: dict[str, float], *, flux_floor: float,
                   exclude: set[str] | None = None):
    """Directed species edges (a -> b, reaction, ν_b/ν_a, |rate|) for every internal
    reaction carrying net flux above ``flux_floor``, oriented by the sign of its
    rate. ``exclude`` removes food/currency species (CO2, H2, water) as cycle
    members — they may feed a cycle but cannot be the thing that is multiplied."""
    exclude = set(exclude or ()) | set(net.boundary)
    edges: dict[str, list[tuple[str, str, float, float]]] = {}
    for r in net.internal():
        v = float(rates.get(r.id, 0.0))
        if abs(v) <= flux_floor:
            continue
        src, dst = (r.reactants, r.products) if v > 0 else (r.products, r.reactants)
        for a, na in src.items():
            if a in exclude:
                continue
            for b, nb in dst.items():
                if b in exclude:
                    continue
                edges.setdefault(a, []).append((b, r.id, nb / na, abs(v)))
    return edges


def autocatalytic_cycles(net: Network, rates: dict[str, float], conc: dict[str, float], *,
                         max_len: int = 6, flux_floor: float = 1e-12, conc_floor: float = 1e-9,
                         exclude: set[str] | None = None, max_cycles: int = 2000) -> list[Motif]:
    """Enumerate flux-carrying simple cycles with stoichiometric gain > 1.

    DFS starts at every *doubling* edge (ν_product/ν_reactant > 1) and looks
    for a path from its product back to its reactant through species above
    ``conc_floor``; each closed path is one motif. Rotations are de-duplicated.
    """
    edges = oriented_edges(net, rates, flux_floor=flux_floor, exclude=exclude)
    alive = {s for s, c in conc.items() if float(c) > conc_floor}
    found: dict[tuple, Motif] = {}
    truncated = False

    def dfs(start: str, node: str, path_sp: list[str], path_rx: list[str], gain: float, minflux: float):
        nonlocal truncated
        if len(found) >= max_cycles:
            truncated = True
            return
        if len(path_sp) > max_len:
            return
        for (b, rid, g, v) in edges.get(node, []):
            if b == start:
                total = gain * g
                if total > 1.0 + 1e-9:
                    m = Motif(species=list(path_sp), reactions=path_rx + [rid], gain=float(total),
                              min_flux=float(min(minflux, v)), seed=start)
                    found.setdefault(m.key(), m)
            elif b in alive and b not in path_sp and len(path_sp) < max_len:
                dfs(start, b, path_sp + [b], path_rx + [rid], gain * g, min(minflux, v))

    for a, outs in edges.items():
        if a not in alive:
            continue
        for (b, rid, g, v) in outs:
            if g <= 1.0 + 1e-9:
                continue
            if b == a:                     # self-loop with gain > 1 (the lumped rTCA turn)
                m = Motif(species=[a], reactions=[rid], gain=float(g), min_flux=float(v), seed=a)
                found.setdefault(m.key(), m)
            elif b in alive:
                dfs(a, b, [a, b], [rid], g, v)
    motifs = list(found.values())
    for m in motifs:
        m.dynamic_gain = float("nan")
    if truncated:
        motifs.append(Motif(species=[], reactions=[], gain=float("nan"), min_flux=float("nan"),
                            seed="__truncated__"))
    return motifs


def motif_gain(m: Motif, conc: dict[str, float], loss_rate: float) -> float:
    """Autocatalytic gain of a motif: net seed production through the cycle's
    rate-limiting step, ``v_min (gain - 1)``, over the seed's first-order loss
    ``loss_rate [seed]``. For og-02's lumped turn (v = k_rtca [OAA][CO2],
    gain 2, loss k_wash) this is ``k_rtca [CO2] / k_wash`` — the same number."""
    seed = float(conc.get(m.seed, 0.0))
    if seed <= 0.0 or loss_rate <= 0.0 or not np.isfinite(m.gain):
        return 0.0
    return float(m.min_flux * (m.gain - 1.0) / (loss_rate * seed))


def summarize_motifs(motifs: list[Motif], conc: dict[str, float], loss_rate: float) -> dict:
    real = [m for m in motifs if m.seed != "__truncated__"]
    for m in real:
        m.dynamic_gain = motif_gain(m, conc, loss_rate)
    core = sorted({s for m in real for s in m.species})
    best = max(real, key=lambda m: m.dynamic_gain) if real else None
    return {
        "n_motifs": len(real),
        "truncated": any(m.seed == "__truncated__" for m in motifs),
        "core_species": core,
        "core_size": len(core),
        "max_dynamic_gain": float(best.dynamic_gain) if best else 0.0,
        "n_self_amplifying": int(sum(1 for m in real if m.dynamic_gain > 1.0)),
        "motifs": [m.to_dict() for m in sorted(real, key=lambda m: -m.dynamic_gain)[:25]],
    }


# --------------------------------------------------------------------------- #
# Enrichment vs matched nulls
# --------------------------------------------------------------------------- #
def enrichment(observed: float, null_values: list[float]) -> dict:
    """One-sided empirical enrichment of ``observed`` against ``null_values``."""
    nv = np.asarray([v for v in null_values if np.isfinite(v)], dtype=float)
    if nv.size == 0:
        return {"observed": float(observed), "n_null": 0, "p_empirical": float("nan"), "z": float("nan"),
                "null_mean": float("nan"), "null_sd": float("nan"), "null_max": float("nan")}
    p = float((1 + int((nv >= observed).sum())) / (1 + nv.size))
    sd = float(nv.std(ddof=1)) if nv.size > 1 else 0.0
    z = float((observed - nv.mean()) / sd) if sd > 0 else (math.inf if observed > nv.mean() else 0.0)
    return {"observed": float(observed), "n_null": int(nv.size), "p_empirical": p, "z": z,
            "null_mean": float(nv.mean()), "null_sd": sd, "null_max": float(nv.max()),
            "null_values": [float(v) for v in nv]}


# --------------------------------------------------------------------------- #
# Verification: flux control + stiffness
# --------------------------------------------------------------------------- #
def finite_difference_elasticities(rr, *, rel: float = 1e-6, abs_floor: float = 1e-12):
    """``(species_ids, N, eps)`` with ``eps[r, s] = dv_r / dx_s`` by central finite
    differences on the live model (libRoadRunner's own Jacobian / elasticity
    routines re-initialise the model per element and take minutes on a
    600-reaction network). ``N`` is the full stoichiometry (floating species x
    reactions) in the same species order. The state is restored afterwards."""
    ids = list(rr.getFloatingSpeciesIds())
    x0 = np.asarray(rr.getFloatingSpeciesConcentrations(), dtype=float)
    N = np.asarray(rr.getFullStoichiometryMatrix(), dtype=float)
    n_r = N.shape[1]
    eps = np.zeros((n_r, len(ids)))
    for k, sid in enumerate(ids):
        h = max(abs(x0[k]) * rel, abs_floor)
        rr[sid] = x0[k] + h
        vp = np.asarray(rr.getReactionRates(), dtype=float)
        rr[sid] = max(x0[k] - h, 0.0)
        vm = np.asarray(rr.getReactionRates(), dtype=float)
        rr[sid] = x0[k]
        eps[:, k] = (vp - vm) / (x0[k] + h - max(x0[k] - h, 0.0))
    rr.getReactionRates()
    return ids, N[:len(ids), :], eps


def flux_control_analysis(rr, *, top_n: int = 12, flux_floor: float = 1e-15) -> dict:
    """Scaled flux-control coefficients at the model's current (settled) state.

    Computed from the unscaled elasticities ``eps = dv/dx`` and the stoichiometric
    matrix ``N`` without calling the steady-state solver (NLEQ does not converge
    on a 400-reaction stiff network): ``C^S = -(N eps)^+ N`` (pseudo-inverse
    handles conserved moieties / sinks) and ``C^J = I + eps C^S``, scaled by
    ``v_j / v_i``. Reports the summation-theorem residual ``|sum_j C^J_ij - 1|``
    per carried flux and the relative time-derivative norm at the state used
    (how close to steady state the settled run is).
    """
    out: dict = {"ok": False}
    try:
        ids = list(rr.getReactionIds())
        rates = np.asarray(rr.getReactionRates(), dtype=float)
        _ids, N, eps = finite_difference_elasticities(rr)
        x = np.asarray(rr.getFloatingSpeciesConcentrations(), dtype=float)
        dx = N @ rates
        J = N @ eps
        CS = -np.linalg.pinv(J) @ N
        CJ = np.eye(len(ids)) + eps @ CS
        with np.errstate(divide="ignore", invalid="ignore"):
            scaled = CJ * (rates[None, :] / rates[:, None])
        # the summation theorem is graded on fluxes that carry >= 1e-6 of the
        # largest flux (scaled coefficients of near-zero fluxes are 0/0 noise)
        floor = max(flux_floor, 1e-6 * float(np.abs(rates).max()) if rates.size else flux_floor)
        carrying = [i for i in range(len(ids)) if abs(rates[i]) > floor]
        sums = np.array([np.nansum(scaled[i]) for i in range(len(ids))])
        resid = np.abs(sums - 1.0)
        top = sorted(carrying, key=lambda i: -abs(rates[i]))[:top_n]
        table = []
        for i in top:
            row = scaled[i]
            ctrl = sorted(((float(row[j]), ids[j]) for j in range(len(ids)) if np.isfinite(row[j]) and abs(row[j]) > 1e-3),
                          key=lambda t: -abs(t[0]))[:5]
            table.append({"flux": ids[i], "rate": float(rates[i]), "summation_residual": float(resid[i]),
                          "top_controllers": [{"reaction": n, "C": c} for c, n in ctrl]})
        dominant = [i for i in carrying if abs(rates[i]) >= 1e-2 * float(np.abs(rates).max())]
        out.update(ok=True, n_fluxes=len(ids), n_carrying=len(carrying), flux_floor=float(floor),
                   n_dominant=len(dominant),
                   steady_state_residual=float(np.linalg.norm(dx[:len(x)]) / max(np.linalg.norm(x), 1e-30)),
                   max_summation_residual=float(resid[carrying].max()) if carrying else 0.0,
                   # the theorem is exact only at steady state and the pseudo-inverse is
                   # ill-conditioned along sink / integrator directions, so the graded
                   # number is the residual on the DOMINANT fluxes (>= 1% of the largest)
                   dominant_summation_residual=float(resid[dominant].max()) if dominant else 0.0,
                   median_summation_residual=float(np.median(resid[carrying])) if carrying else 0.0,
                   table=table)
    except Exception as exc:  # noqa: BLE001 — report, never hide
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def stiffness_check(rr_factory, *, t_end: float = 120.0, n_points: int = 121,
                    tolerances=((1e-6, 1e-12), (1e-9, 1e-15), (1e-3, 1e-9))) -> dict:
    """Integrate the same model under several (rtol, atol) settings and report
    the worst relative deviation of every species from the tightest run, plus the
    Jacobian stiffness ratio at the end state. ``rr_factory()`` returns a fresh
    roadrunner instance (the model must be re-created per tolerance setting)."""
    runs = {}
    for rtol, atol in tolerances:
        rr = rr_factory()
        integ = rr.getIntegrator()
        integ.setValue("relative_tolerance", float(rtol))
        integ.setValue("absolute_tolerance", float(atol))
        rr.simulate(0.0, float(t_end), int(n_points))
        ids = list(rr.getFloatingSpeciesIds())
        runs[(rtol, atol)] = (ids, np.asarray(rr.getFloatingSpeciesConcentrations(), dtype=float), rr)
    tight = min(runs, key=lambda k: k[0])
    ids, ref, rr_tight = runs[tight]
    scale = np.maximum(np.abs(ref), 1e-12)
    deviations = {}
    for key, (_, vals, _) in runs.items():
        if key == tight:
            continue
        dev = np.abs(vals - ref) / scale
        mask = np.abs(ref) > 1e-9
        deviations[f"rtol={key[0]:g},atol={key[1]:g}"] = {
            "max_rel_dev": float(dev[mask].max()) if mask.any() else 0.0,
            "worst_species": ids[int(np.argmax(np.where(mask, dev, -1)))] if mask.any() else None,
        }
    try:
        _ids, N, eps = finite_difference_elasticities(rr_tight)
        J = N @ eps
        ev = np.linalg.eigvals(J)
        re_ = np.abs(ev.real)
        re_ = re_[re_ > 1e-14]
        ratio = float(re_.max() / re_.min()) if re_.size else float("nan")
        jac = {"n": int(J.shape[0]), "max_abs_re": float(re_.max()) if re_.size else 0.0,
               "min_abs_re": float(re_.min()) if re_.size else 0.0, "stiffness_ratio": ratio,
               "max_re": float(ev.real.max())}
    except Exception as exc:  # noqa: BLE001
        jac = {"error": f"{type(exc).__name__}: {exc}"}
    return {"reference": f"rtol={tight[0]:g},atol={tight[1]:g}", "deviations": deviations, "jacobian": jac}


__all__ = [
    "Rxn", "Network", "Motif", "network_from_roadrunner", "stoich_matrix", "element_residual",
    "oriented_edges", "autocatalytic_cycles", "motif_gain", "summarize_motifs", "enrichment",
    "finite_difference_elasticities", "flux_control_analysis", "stiffness_check",
]
