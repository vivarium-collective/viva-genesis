"""Functional (coefficient-independent) autocatalysis discriminator.

The post-hoc motif detector in :mod:`viva_genesis.protometabolism.motifs`
(``autocatalytic_cycles`` → ``autocatalytic_gain``) is **coefficient-gated**:
its DFS starts only from *doubling edges* (ν_product/ν_reactant > 1 in the flux
direction). That is the right test for formose-type autocatalysis, whose
autocatalytic step IS a coefficient-2 reaction (the symmetric retro-aldol
``C4 → 2 C2``, e.g. r409 ``2 glycolaldehyde ⇌ threose``) — so the detector is
not blind to it. But it is **structurally blind to *topological* autocatalysis**
— a cycle that returns two copies of its carrier through a branch-and-remerge of
all-1:1 elementary steps, with no single coefficient-2 reaction. The reductive
TCA cycle is exactly this: citrate → OAA + acetyl (the lyase branch), and the
acetyl is re-carboxylated back to a second OAA, so one turn makes 1 OAA → 2 OAA
with every elementary step 1:1. The coefficient detector returns gain 0 for such
a network *by construction* — a guaranteed false negative.

This module measures what autocatalysis **is** — self-amplification — directly,
independent of per-reaction coefficients, so formose and rTCA are judged on the
same footing. Three witnesses, each run on the candidate network AND on its
degree-preserving matched null, across the feed (ignition) sweep:

1. :func:`seed_dependence` — the *dynamical / bistability* test. Run two
   trajectories at identical feeds: one with a small seed pulse of the carrier
   species, one without. A self-amplifying (bistable) network reaches a
   different, higher-flux attractor when seeded; a feed-driven network reaches
   the same steady state regardless of the seed (a unique fixed point). Reported
   as the seeded/unseeded ratio of the settled carrier pool and net carbon flux.

2. :func:`growth_signature` — the *kinetic* signature. During the seeded
   transient the per-capita growth rate ``μ = d ln(C_carrier)/dt`` is measured.
   Autocatalysis has an exponential-growth phase (ln C linear in t, μ > 0 and
   roughly constant); mere feed-driven accumulation grows sub-exponentially
   (μ decays as the pool fills). Reported as the max sustained μ and the R² of a
   log-linear fit over the growth window.

3. :func:`production_order` — the *static* order. At the settled operating
   point the whole organic pool is scaled by a common factor s and the net
   internal organic-carbon production rate P(s) is read from the live engine; the
   exponent ``p`` of ``P ∝ pool^p`` is the self-amplification order: p ≈ 0
   feed-driven (production set by the feed, not the existing pool), p ≈ 1 linear
   autocatalysis (``dX/dt ∝ X`` — exponential), p > 1 super-linear. Scaling the
   whole pool coherently is what lets this see topological (whole-cycle)
   autocatalysis that a single-species perturbation would miss.

:func:`functional_discriminator` runs all three across the sweep on both arms and
returns MET / refuted / inconclusive with every number, so the result is read,
never declared. Nothing here decides a verdict by fiat — the thresholds are
explicit and the raw witnesses travel with the verdict.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import universe as U


# --------------------------------------------------------------------------- #
# Trajectory driving (generated universe / null, or any ReactionUniverseProcess)
# --------------------------------------------------------------------------- #
def _n_carbons(sid: str) -> int:
    try:
        return int(U.n_carbons(sid))
    except Exception:  # noqa: BLE001 — a non-skeleton id (currency) has 0 skeleton carbons
        return 0


def run_trajectory(proc_cls, feeds: dict, n_steps: int, config: dict | None = None, *,
                   carrier: str | None = None, seed: dict | None = None, interval: float = 1.0) -> dict:
    """Run ``proc_cls`` for ``n_steps`` and return per-tick series.

    ``seed`` (``{species_id: molar}``) is injected into the engine BEFORE the
    first step (via :meth:`ReactionUniverseProcess._engine`, which builds the
    roadrunner model without advancing it), so the trajectory starts from the
    seeded state. ``carrier`` is the species whose pool is tracked tick-by-tick
    for the growth / bistability witnesses.
    """
    from process_bigraph import allocate_core
    cfg = {"motif_every": max(1, n_steps), **(config or {})}  # detector is costly; once is enough here
    p = proc_cls(config=cfg, core=allocate_core())
    rr = p._engine({k: float(feeds.get(k, 0.0)) for k in p.inputs()})
    if seed:
        for sid, val in seed.items():
            try:
                rr[sid] = float(val)
            except Exception:  # noqa: BLE001 — species absent in this network → no seed to place
                pass
    u = p.universe()
    organics = list(u.organics())
    carrier_series, toc_series, flux_series, t_series = [], [], [], []
    out = None
    for i in range(n_steps):
        out = p.update(feeds, interval)
        conc = p._conc
        toc = float(sum(_n_carbons(s) * conc.get(s, 0.0) for s in organics))
        carrier_series.append(float(conc.get(carrier, 0.0)) if carrier else float("nan"))
        toc_series.append(toc)
        flux_series.append(float(out.get("net_carbon_flux", 0.0)))
        t_series.append((i + 1) * interval)
    return {
        "t": t_series, "carrier": carrier_series, "toc": toc_series, "net_carbon_flux": flux_series,
        "final": out, "organics": organics,
        "detector_gain_final": float(out.get("autocatalytic_gain", 0.0)) if out else 0.0,
        "detector_motifs_final": float(out.get("n_autocatalytic_motifs", 0.0)) if out else 0.0,
        "rr": rr, "net": p._net, "process": p,
    }


# --------------------------------------------------------------------------- #
# 1. seed-dependence (bistability)
# --------------------------------------------------------------------------- #
@dataclass
class SeedDependence:
    seeded_carrier: float
    unseeded_carrier: float
    seeded_flux: float
    unseeded_flux: float
    carrier_ratio: float          # seeded / unseeded settled carrier pool
    flux_ratio: float
    seed_level: float
    self_maintained: bool         # seeded state held up by net-positive carbon fixation (not a decaying/washing seed)
    bistable: bool                # self_maintained AND seeding enables carrier + fixation the feed alone does not

    def to_dict(self) -> dict:
        return {k: (float(v) if isinstance(v, (int, float)) and not isinstance(v, bool)
                    else bool(v) if isinstance(v, bool) else v)
                for k, v in self.__dict__.items()}


def seed_dependence(proc_cls, feeds: dict, n_steps: int, config: dict, carrier: str, *,
                    seed_level: float = 1.0e-4, tol: float = 0.25, tail_frac: float = 0.2,
                    flux_floor: float = 1.0e-8) -> SeedDependence:
    """Settled carrier pool & net carbon flux with vs without a seed pulse of
    ``carrier``. Functional autocatalysis = seeding bootstraps a SELF-MAINTAINED,
    carbon-fixing state the feed alone does not reach. ``bistable`` requires BOTH:

    * ``self_maintained`` — the seeded settled state carries net-positive carbon
      fixation (``seeded_flux > flux_floor``). This is the physical correction
      that distinguishes a genuinely held state from (a) a seed that merely
      washes out slowly over a finite run — its carrier is still > the unseeded 0
      but it carries no fixation flux — and (b) a stalled cycle that collapses.
    * ``seed-dependent`` — seeding settles the carrier AND the fixation flux more
      than ``tol`` above the unseeded (feed-only) run. A feed-driven network fixes
      the same carbon with or without the seed (seeded ≈ unseeded), so it fails
      here even when its flux is large (as formose does).
    """
    def _settled(series_key, tr):
        xs = tr[series_key]
        k = max(1, int(round(len(xs) * tail_frac)))
        tail = [v for v in xs[-k:] if math.isfinite(v)]
        return sum(tail) / len(tail) if tail else 0.0

    seeded = run_trajectory(proc_cls, feeds, n_steps, config, carrier=carrier, seed={carrier: seed_level})
    unseeded = run_trajectory(proc_cls, feeds, n_steps, config, carrier=carrier, seed=None)
    sc, uc = _settled("carrier", seeded), _settled("carrier", unseeded)
    sf, uf = _settled("net_carbon_flux", seeded), _settled("net_carbon_flux", unseeded)
    denom_c = max(abs(uc), 1e-30)
    self_maintained = bool(sf > flux_floor)
    seed_dependent = bool(sc > uc * (1.0 + tol) and sf > max(uf, 0.0) * (1.0 + tol) + flux_floor)
    return SeedDependence(
        seeded_carrier=sc, unseeded_carrier=uc, seeded_flux=sf, unseeded_flux=uf,
        carrier_ratio=(sc / denom_c), flux_ratio=(sf / max(abs(uf), 1e-30)),
        seed_level=seed_level, self_maintained=self_maintained,
        bistable=bool(self_maintained and seed_dependent),
    )


# --------------------------------------------------------------------------- #
# 2. growth signature (exponential-phase per-capita rate)
# --------------------------------------------------------------------------- #
def growth_signature(t: list[float], carrier: list[float], *, floor: float = 1e-12,
                     min_window: int = 4) -> dict:
    """Max sustained per-capita growth rate μ = d ln(carrier)/dt and the R² of a
    log-linear fit over the best growth window.

    Autocatalysis shows an exponential phase: ln(carrier) linear in t with μ > 0.
    Feed-driven accumulation is sub-exponential (μ decays as the pool fills), so
    the best log-linear window is short / poorly fit and μ is small."""
    t = np.asarray(t, dtype=float)
    x = np.asarray(carrier, dtype=float)
    alive = x > floor
    if alive.sum() < min_window:
        return {"mu_max": 0.0, "r2": 0.0, "exponential_phase": False, "window": [0, 0], "n_alive": int(alive.sum())}
    lx = np.where(alive, np.log(np.maximum(x, floor)), np.nan)
    best = {"mu_max": 0.0, "r2": 0.0, "window": [0, 0]}
    idx = np.where(alive)[0]
    i0, i1 = int(idx[0]), int(idx[-1]) + 1
    # slide windows over the alive region; pick the one with the steepest positive
    # well-fit log-linear slope (the exponential-growth phase)
    for a in range(i0, i1 - min_window + 1):
        for b in range(a + min_window, i1 + 1):
            tt, ll = t[a:b], lx[a:b]
            if not np.all(np.isfinite(ll)):
                continue
            A = np.vstack([tt, np.ones_like(tt)]).T
            (slope, _), res, *_ = np.linalg.lstsq(A, ll, rcond=None)
            if slope <= 0:
                continue
            ss_tot = float(((ll - ll.mean()) ** 2).sum())
            r2 = 1.0 - float(res[0]) / ss_tot if (res.size and ss_tot > 0) else 0.0
            # prefer a steep, well-fit, reasonably long window
            score = slope * max(r2, 0.0) * math.log(b - a + 1)
            if score > best["mu_max"] * max(best["r2"], 1e-6) * math.log(best["window"][1] - best["window"][0] + 2) \
                    or best["window"] == [0, 0]:
                best = {"mu_max": float(slope), "r2": float(r2), "window": [a, b]}
    best["exponential_phase"] = bool(best["mu_max"] > 0 and best["r2"] >= 0.9 and
                                     (best["window"][1] - best["window"][0]) >= min_window)
    best["n_alive"] = int(alive.sum())
    return best


# --------------------------------------------------------------------------- #
# 3. static production order (whole-pool scaling exponent)
# --------------------------------------------------------------------------- #
def net_internal_carbon_production(net, rates: dict, organics, *, carrier: str | None = None) -> float:
    """Net rate at which internal reactions produce organic carbon (mol-C / s),
    = Σ_species n_C(species) · Σ_internal-reactions ν · v. If ``carrier`` is
    given, restrict to that species' own net production (mol / s)."""
    total = 0.0
    targets = [carrier] if carrier else list(organics)
    for sp in targets:
        nc = 1 if carrier else _n_carbons(sp)
        prod = 0.0
        for r in net.internal():
            nu = r.products.get(sp, 0.0) - r.reactants.get(sp, 0.0)
            if nu:
                prod += nu * float(rates.get(r.id, 0.0))
        total += nc * prod
    return float(total)


def production_order(rr, net, organics, *, carrier: str | None = None,
                     scales=(0.125, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0), floor: float = 1e-14) -> dict:
    """Exponent ``p`` of net internal (carbon or carrier) production vs a uniform
    scaling of the whole organic pool, fit over the positive-production region.

    p ≈ 0 feed-driven (production independent of the existing pool); p ≈ 1 linear
    autocatalysis (``dX/dt ∝ X``, exponential); p > 1 super-linear. Scaling the
    whole pool coherently captures topological (whole-cycle) autocatalysis."""
    organics = list(organics)
    x0 = {s: float(rr[s]) for s in organics}
    pools, prods = [], []
    for fac in scales:
        for s, v in x0.items():
            rr[s] = max(v * fac, 0.0)
        rates = dict(zip(rr.getReactionIds(), (float(x) for x in rr.getReactionRates())))
        pool = float(sum(_n_carbons(s) * max(float(rr[s]), 0.0) for s in organics))
        prod = net_internal_carbon_production(net, rates, organics, carrier=carrier)
        pools.append(pool)
        prods.append(prod)
    for s, v in x0.items():          # restore the live state
        rr[s] = v
    rr.getReactionRates()
    pools = np.asarray(pools, dtype=float)
    prods = np.asarray(prods, dtype=float)
    mask = (prods > 0) & (pools > floor)
    if mask.sum() < 2:
        return {"p": float("nan"), "r2": float("nan"), "n_points": int(mask.sum()),
                "pools": pools.tolist(), "productions": prods.tolist(),
                "note": "no positive-production region — production does not rise with the pool (feed-driven or net-consuming)"}
    lp, lq = np.log(pools[mask]), np.log(prods[mask])
    A = np.vstack([lp, np.ones_like(lp)]).T
    (slope, _), res, *_ = np.linalg.lstsq(A, lq, rcond=None)
    ss_tot = float(((lq - lq.mean()) ** 2).sum())
    r2 = 1.0 - float(res[0]) / ss_tot if (res.size and ss_tot > 0) else (1.0 if lq.size == 2 else 0.0)
    return {"p": float(slope), "r2": float(r2), "n_points": int(mask.sum()),
            "pools": pools.tolist(), "productions": prods.tolist()}


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
@dataclass
class ArmResult:
    label: str
    seed_dependence: dict
    growth: dict
    production_order: dict
    detector_gain_final: float
    functional_autocatalysis: bool = field(default=False)

    def to_dict(self) -> dict:
        return {"label": self.label, "seed_dependence": self.seed_dependence, "growth": self.growth,
                "production_order": self.production_order, "detector_gain_final": self.detector_gain_final,
                "functional_autocatalysis": self.functional_autocatalysis}


def _is_functional(seed: dict, growth: dict, order: dict) -> bool:
    """Functional autocatalysis = **seed-dependence that AMPLIFIES**: seeding a
    nucleus of the carrier settles the network into a state meaningfully HIGHER
    than the feed alone reaches (``bistable`` AND seeded/unseeded carrier > 1).

    This is the decisive, definition-faithful witness — self-amplification is
    exactly the carrier bootstrapping a state the feed cannot. ``growth`` and
    ``production_order`` are REPORTED as mechanistic context but do NOT gate the
    verdict: the whole-pool ``production_order`` exponent ``p`` conflates genuine
    self-catalysis with ordinary bimolecular mass-action (an aldol C2+C2→C4 makes
    carrier production scale ~s² with the pool, giving p≈2 with no
    self-amplification at all — as formose shows), and a transient growth window
    can be spurious when the nucleus is seeded above its own attractor. So the
    gate is seed-dependence; the others are evidence for the mechanism, not the
    fact."""
    return bool(seed.get("bistable"))


def run_arm(proc_cls, label: str, feeds: dict, n_steps: int, config: dict, carrier: str, *,
            seed_level: float = 1.0e-4) -> ArmResult:
    sd = seed_dependence(proc_cls, feeds, n_steps, config, carrier, seed_level=seed_level)
    # one seeded trajectory supplies both the growth window and a settled engine
    tr = run_trajectory(proc_cls, feeds, n_steps, config, carrier=carrier, seed={carrier: seed_level})
    gr = growth_signature(tr["t"], tr["carrier"])
    po = production_order(tr["rr"], tr["net"], tr["organics"], carrier=carrier)
    res = ArmResult(label=label, seed_dependence=sd.to_dict(), growth=gr, production_order=po,
                    detector_gain_final=tr["detector_gain_final"])
    res.functional_autocatalysis = _is_functional(res.seed_dependence, gr, po)
    return res


def functional_discriminator(favorable_cls, null_cls, feeds: dict, n_steps: int, base_config: dict,
                             carrier: str, *, null_seed: int = 0, seed_level: float = 1.0e-4) -> dict:
    """Run the three witnesses on the favorable network and its matched null at a
    single feed point. Topology-specificity = favorable is functionally
    autocatalytic AND the null is not."""
    fav = run_arm(favorable_cls, "favorable", feeds, n_steps, dict(base_config), carrier, seed_level=seed_level)
    nul = run_arm(null_cls, "matched_null", feeds, n_steps, {**base_config, "null_seed": null_seed}, carrier,
                  seed_level=seed_level)
    topology_specific = bool(fav.functional_autocatalysis and not nul.functional_autocatalysis)
    if fav.functional_autocatalysis and topology_specific:
        verdict = "MET"
    elif not fav.functional_autocatalysis:
        verdict = "refuted"
    else:
        verdict = "inconclusive"   # functional but not separable from the null
    return {"carrier": carrier, "feeds": dict(feeds), "n_steps": n_steps,
            "favorable": fav.to_dict(), "matched_null": nul.to_dict(),
            "topology_specific": topology_specific, "verdict": verdict}


__all__ = [
    "run_trajectory", "seed_dependence", "SeedDependence", "growth_signature",
    "net_internal_carbon_production", "production_order", "ArmResult", "run_arm",
    "functional_discriminator",
]
