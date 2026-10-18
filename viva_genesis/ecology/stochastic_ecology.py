"""Module L (stochastic) — stochastic protocell ecology (og-36, Gate E ecology).

Study og-07 showed, *deterministically*, that a connected cross-feeding
metacommunity develops capability redundancy a single compartment does not.
og-36 asks the honest low-count follow-on: when a cross-feeding protocell
community is run with **genuine demographic stochasticity** (integer cell
counts, a Gillespie SSA), does the community-level productivity benefit survive,
and do stochastic dynamics materially change the outcome versus the deterministic
mean-field?

This is **Option B** — a lightweight, dependency-free Gillespie SSA written in
numpy, honestly labelled. The heavier resolution (GillesPy2 / SSA tau-leaping,
COBRApy genome-scale benchmarks) is the follow-on study og-36a. The *same*
process runs every arm and both regimes, so the comparison is matched.

The model is chemically explicit (integer molecule/cell counts): one shared,
limiting feed pool ``S`` (influx ``feed_F``, held EQUAL across arms), ``K``
byproduct pools ``B_i``, and ``K`` cell counts ``n_i``. A cell of lineage ``i``
grows either on the shared feed ``S`` (Monod), emitting one byproduct ``B_i``, or
on its upstream ring neighbour's byproduct ``B_{i-1}`` (cross-feeding, Monod),
which it consumes. Byproducts and feed wash out. All lineages compete for the one
shared feed, which alone would drive competitive exclusion down to the single
most-efficient lineage. Cross-feeding is what prevents that: a byproduct pool is
depletable, so when a lineage becomes rare its partner's byproduct accumulates
(nobody is eating it) and gives the rare lineage a growth boost when it does fire
— negative frequency dependence that **stabilizes coexistence** and lets the
community extract extra biomass from byproducts a monoculture simply loses to
washout. ``knockout=True`` switches off exactly the cross-feeding growth, so the
shared-feed competition reasserts itself and the community collapses back toward
the single best lineage — isolating cross-feeding as the cause.

  * **community**   — all ``n_lineages`` seeded; shared feed + cross-feeding ring.
  * **monoculture** — ``n_seeded = 1`` (the most feed-efficient lineage); it draws
    the whole shared feed and has no upstream partner, so cross-feeding is zero.
    The *best* such run is the strict "margin over the best single lineage" control.
  * **knockout**    — all seeded, shared feed, cross-feeding OFF (``knockout=True``)
    — isolates whether the community margin is *causally* cross-feeding.

Regime: ``deterministic=False`` (default) runs the exact Gillespie SSA on integer
counts; ``deterministic=True`` runs the mean-field Euler ODE on the identical
propensities. At low counts a lineage can stochastically hit zero and go extinct
— no cell influx brings it back — which breaks the cross-feeding ring and starves
its downstream partner. The mean-field never truly reaches zero, so it misses
this; the gap between the two is the study's "stochastic dynamics materially
change outcomes at low counts" readout.

Honesty: a reproduction (a hand-written SSA + mean-field ODE), NOT a wrapped
ALife engine; reproducible given ``seed``. Feed budget is held equal across arms;
the only things that differ are topology (community vs single) and the
cross-feeding switch. Parameters are proposed_inputs, not fitted to a target.
"""
from __future__ import annotations

from process_bigraph import Process

_OW = {"_type": "overwrite[float]", "_units": "dimensionless"}

# Safety cap on SSA events per update() so a pathological parameter set can never
# hang the engine; far above any healthy event count for the intended low-count scale.
_MAX_EVENTS_PER_UPDATE = 200_000


class StochasticProtocellEcologyProcess(Process):
    """Lightweight Gillespie-SSA cross-feeding protocell community (Option B).

    A ring of ``n_lineages`` protocell lineages with integer cell counts. Each
    seeded lineage grows (birth) on its share of a shared, limiting feed flux
    (``feed_F``, Monod-divided by total demand) plus a cross-fed byproduct from its
    upstream ring neighbour (saturating in the neighbour's biomass); it dies/washes
    out at a density-dependent rate. The ``update`` advances the community by
    ``interval`` of simulated time via an exact Gillespie SSA (``deterministic=False``)
    or a matched mean-field Euler step (``deterministic=True``), and emits the
    cumulative productivity (total births), the total/mean population, and the number
    of extinct lineages. Cumulative productivity at equal feed is the community-function
    metric; extinctions are the low-count stochastic mechanism that breaks the ring."""

    contract = {
        "summary": "Stochastic (Gillespie SSA) cross-feeding protocell community vs a matched best-single-lineage control at equal shared feed: does the community out-produce AND out-persist the best single lineage, is the benefit causally due to cross-feeding, and do low-count stochastic dynamics materially change it versus the deterministic mean-field?",
        "description": (
            "Chemically explicit, integer counts: one shared limiting feed pool S (influx feed_F, EQUAL "
            "across arms), K byproduct pools B_i, K cell counts n_i on a ring. A cell of lineage i grows "
            "on the shared feed S (Monod, emitting one B_i) or on its upstream neighbour's byproduct "
            "B_{i-1} (cross-feeding, Monod, consuming it). Feed and byproducts wash out; cells die. "
            "Shared-feed competition alone excludes down to the single best lineage; depletable byproduct "
            "pools give negative frequency dependence (a rare lineage's upstream byproduct accumulates "
            "and boosts it) that stabilizes coexistence and extracts extra biomass a monoculture loses to "
            "washout. community = all seeded, cross-feeding on; monoculture = the single most-efficient "
            "lineage on the full feed, no partner; knockout = all seeded, cross-feeding off (mu_cross "
            "gated to 0) -> exclusion reasserts. deterministic=False runs the exact Gillespie SSA (a "
            "lineage reaching 0 is extinct and breaks the ring); deterministic=True the mean-field Euler "
            "ODE on identical propensities. A dependency-free reproduction (Option B); GillesPy2/COBRApy = og-36a."
        ),
        "inputs": {},
        "outputs": {
            "cumulative_productivity": "total cell births (biomass produced) since t0 — the equal-feed community-function metric (dimensionless)",
            "total_population": "total live cells across all lineages (dimensionless)",
            "mean_population": "mean live cells per seeded lineage (dimensionless)",
            "n_extinct": "number of seeded lineages currently at zero cells — the stochastic ring-breaking mechanism (dimensionless)",
            "n_alive": "number of seeded lineages with >0 cells — community persistence (dimensionless)",
        },
        "assumptions": [
            "Lightweight dependency-free Gillespie SSA + matched mean-field ODE (Option B); honestly a reproduction, not a wrapped ALife/agent engine.",
            "One shared LIMITING feed influx feed_F, held EQUAL across arms — so the feed-limited biomass ceiling is identical and splitting feed buys the community nothing by itself.",
            "Coexistence is stabilized by DEPLETABLE byproduct pools (negative frequency dependence), not assumed; knockout switches off exactly the cross-feeding growth and exclusion reasserts.",
            "A lineage at zero cells is extinct and cannot recover (no cell influx) — how low-count noise breaks the ring; the mean-field never truly reaches zero.",
            "Per-lineage feed efficiencies eff_i are heterogeneous so 'best single lineage' is a real maximum; parameters are proposed_inputs, not fitted.",
        ],
        "math": [
            "feed growth i: n_i + S -> 2 n_i + B_i,  rate mu*eff_i*n_i*S/(S+Ks)",
            "cross growth i: n_i + B_{i-1} -> 2 n_i,  rate mu_cross'*eff_i*n_i*B_{i-1}/(B_{i-1}+Kb) ; mu_cross'=0 if knockout",
            "feed influx: 0 -> S at feed_F ; feed washout S -> 0 at k_S*S ; byproduct washout B_i -> 0 at k_B*B_i",
            "death i: n_i -> 0 at d0*n_i",
            "SSA: next event ~ Exp(sum propensities); one reaction fires by inverse-CDF; integer counts; n_i=0 absorbing",
            "mean-field: dx/dt = sum_r stoich_r * propensity_r, explicit Euler; productivity += (sum growth propensities)*dt",
        ],
        "symbols": {
            "S": "shared feed molecule count", "B_i": "byproduct pool of lineage i",
            "n_i": "integer cell count of lineage i", "eff_i": "per-lineage feed efficiency",
        },
        "references": ["weiss2016physiology", "moody2024nature"],
    }

    config_schema = {
        "n_lineages": {"_type": "integer", "_default": 4},
        # n_seeded = number of lineages alive at t0; set 1 for a monoculture arm.
        "n_seeded": {"_type": "integer", "_default": 4},
        "feed_F": {"_type": "float", "_default": 16.0, "_units": "dimensionless"},     # shared limiting feed influx (EQUAL across arms)
        "feed_Ks": {"_type": "float", "_default": 6.0, "_units": "dimensionless"},     # Monod half-saturation on shared feed S
        "cross_Kb": {"_type": "float", "_default": 6.0, "_units": "dimensionless"},    # Monod half-saturation on byproduct B
        "mu": {"_type": "float", "_default": 0.55, "_units": "dimensionless"},         # birth coeff on feed
        "mu_cross": {"_type": "float", "_default": 0.50, "_units": "dimensionless"},   # cross-feeding (recycling) birth coeff
        "k_feed_wash": {"_type": "float", "_default": 0.25, "_units": "dimensionless"},# shared-feed washout
        "k_byprod_wash": {"_type": "float", "_default": 0.30, "_units": "dimensionless"}, # byproduct washout
        "d0": {"_type": "float", "_default": 0.11, "_units": "dimensionless"},         # cell death/washout
        "eff_spread": {"_type": "float", "_default": 0.30, "_units": "dimensionless"}, # heterogeneity of eff_i (0 = identical)
        "n0": {"_type": "integer", "_default": 5},                                     # initial cells per seeded lineage
        "S0": {"_type": "float", "_default": 20.0, "_units": "dimensionless"},         # initial shared feed
        # For a monoculture arm (n_seeded=1): which lineage to seed. -1 -> the most
        # efficient (argmax eff); >=0 -> exactly that ring index, so the sims can run
        # EVERY single-lineage monoculture and take the true best (strict control).
        "mono_lineage": {"_type": "integer", "_default": -1},
        # Truthy-flag arms (process-bigraph config merge ignores a falsy 0.0/False override,
        # so knockout/deterministic are bools set True for their arm, never mu_cross=0 / stochastic=False).
        "knockout": {"_type": "boolean", "_default": False},       # True -> cross-feeding off (mu_cross gated to 0)
        "deterministic": {"_type": "boolean", "_default": False},  # True -> mean-field Euler instead of SSA
        "dt_det": {"_type": "float", "_default": 0.03, "_units": "dimensionless"},     # Euler step for the deterministic arm
        "seed": {"_type": "integer", "_default": 1},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        import numpy as np

        k = max(int(self.config["n_lineages"]), 1)
        n_seed = int(min(max(self.config["n_seeded"], 1), k))
        self._k = k
        self._n_seeded = n_seed
        self._rng = np.random.default_rng(int(self.config["seed"]))

        # Per-lineage feed efficiencies, heterogeneous so "best single lineage" is a
        # genuine maximum. Centred on 1.0, symmetric spread; deterministic given seed.
        spread = float(np.clip(self.config["eff_spread"], 0.0, 0.95))
        if k == 1:
            eff = np.array([1.0])
        else:
            eff = np.linspace(1.0 - spread, 1.0 + spread, k)
            eff = eff[self._rng.permutation(k)]          # shuffle so the ring order isn't monotone
        self._eff = eff

        # Which lineages start alive. For a monoculture (n_seeded=1) seed either the
        # requested lineage (mono_lineage>=0) or the most efficient one (default -1), so
        # the sims can run every single-lineage control and take the true best.
        if n_seed == 1:
            ml = int(self.config["mono_lineage"])
            self._seeded = np.array([ml if 0 <= ml < k else int(np.argmax(eff))])
        else:
            self._seeded = np.arange(n_seed)

        # State vector x = [S, B_0..B_{k-1}, n_0..n_{k-1}] (integers for the SSA).
        n = np.zeros(k, dtype=np.int64)
        n[self._seeded] = int(self.config["n0"])
        self._S = float(self.config["S0"])
        self._B = np.zeros(k)
        self._n = n
        # continuous mirrors for the deterministic arm
        self._Sf = float(self.config["S0"])
        self._Bf = np.zeros(k)
        self._nf = n.astype(float)
        self._productivity = 0.0
        self._t = 0.0

    def inputs(self):
        return {}

    def outputs(self):
        return {
            "cumulative_productivity": _OW,
            "total_population": _OW,
            "mean_population": _OW,
            "n_extinct": _OW,
            "n_alive": _OW,
        }

    # ------------------------------------------------------------------ dynamics
    def _propensities(self, S, B, n):
        """Propensity vector over the 2 + 4K reactions for state (S, B[k], n[k]).

        Order: [feed_influx, feed_wash, feed_growth_i(k), cross_growth_i(k),
        byprod_wash_i(k), death_i(k)]."""
        import numpy as np
        k = self._k
        mu = float(self.config["mu"])
        feed_F = float(self.config["feed_F"])
        feed_Ks = float(self.config["feed_Ks"])
        cross_Kb = float(self.config["cross_Kb"])
        mu_cross = 0.0 if bool(self.config["knockout"]) else float(self.config["mu_cross"])
        k_fw = float(self.config["k_feed_wash"])
        k_bw = float(self.config["k_byprod_wash"])
        d0 = float(self.config["d0"])

        n = np.asarray(n, dtype=float)
        B = np.asarray(B, dtype=float)
        S = max(float(S), 0.0)
        feed_growth = mu * self._eff * n * (S / (S + feed_Ks))                 # consumes S, emits B_i
        up = B[(np.arange(k) - 1) % k]                                          # upstream byproduct B_{i-1}
        cross_growth = mu_cross * self._eff * n * (up / (up + cross_Kb))        # consumes B_{i-1}
        byprod_wash = k_bw * B
        death = d0 * n
        props = np.concatenate([[feed_F, k_fw * S], feed_growth, cross_growth, byprod_wash, death])
        return np.maximum(props, 0.0)

    def _apply(self, j, S, B, n):
        """Apply reaction ``j`` to integer state in place; returns new S and whether a
        birth occurred (for the productivity tally)."""
        k = self._k
        birth = False
        if j == 0:                       # feed influx
            S += 1.0
        elif j == 1:                     # feed washout
            S = max(S - 1.0, 0.0)
        elif j < 2 + k:                  # feed growth of lineage i
            i = j - 2
            if S >= 1.0:
                S -= 1.0; n[i] += 1; B[i] += 1.0; birth = True
        elif j < 2 + 2 * k:              # cross growth of lineage i (consumes B_{i-1})
            i = j - (2 + k)
            up = (i - 1) % k
            if B[up] >= 1.0:
                B[up] -= 1.0; n[i] += 1; birth = True
        elif j < 2 + 3 * k:              # byproduct washout
            i = j - (2 + 2 * k)
            if B[i] >= 1.0:
                B[i] -= 1.0
        else:                            # death
            i = j - (2 + 3 * k)
            if n[i] > 0:
                n[i] -= 1
        return S, birth

    def _step_ssa(self, interval):
        import numpy as np
        rng = self._rng
        t_end = self._t + float(interval)
        S, B, n = self._S, self._B, self._n
        nr = 2 + 4 * self._k
        events = 0
        while events < _MAX_EVENTS_PER_UPDATE:
            props = self._propensities(S, B, n)
            total = float(props.sum())
            if total <= 0.0:
                break
            dt = rng.exponential(1.0 / total)
            if self._t + dt > t_end:
                break
            self._t += dt
            r = rng.random() * total                         # inverse-CDF (fast)
            j = int(np.searchsorted(np.cumsum(props), r, side="right"))
            if j >= nr:
                j = nr - 1
            S, birth = self._apply(j, S, B, n)
            if birth:
                self._productivity += 1.0
            events += 1
        self._t = t_end
        self._S, self._B, self._n = S, B, n

    def _step_det(self, interval):
        """Mean-field Euler on the identical propensities (continuous state)."""
        import numpy as np
        k = self._k
        dt = float(self.config["dt_det"])
        steps = max(int(round(float(interval) / dt)), 1)
        S, B, n = self._Sf, self._Bf.copy(), self._nf.copy()
        for _ in range(steps):
            props = self._propensities(S, B, n)
            feed_influx, feed_wash = props[0], props[1]
            feed_growth = props[2:2 + k]
            cross_growth = props[2 + k:2 + 2 * k]
            byprod_wash = props[2 + 2 * k:2 + 3 * k]
            death = props[2 + 3 * k:2 + 4 * k]
            up = np.arange(k)
            dS = feed_influx - feed_wash - feed_growth.sum()
            dB = feed_growth - byprod_wash
            # cross growth of lineage i consumes B_{i-1}
            consume = np.zeros(k)
            for i in range(k):
                consume[(i - 1) % k] += cross_growth[i]
            dB = dB - consume
            dn = feed_growth + cross_growth - death
            self._productivity += float(feed_growth.sum() + cross_growth.sum()) * dt
            S = max(S + dS * dt, 0.0)
            B = np.maximum(B + dB * dt, 0.0)
            n = np.maximum(n + dn * dt, 0.0)
        self._Sf, self._Bf, self._nf = S, B, n
        self._t += float(interval)

    def update(self, state, interval):
        import numpy as np
        deterministic = bool(self.config["deterministic"])
        if deterministic:
            self._step_det(interval)
            n = self._nf
            # the mean-field "extinct" check uses a <1-cell threshold; the continuous
            # model rarely truly reaches it, which is exactly the stochastic contrast.
            extinct = int(np.sum(n[self._seeded] < 1.0))
            alive = int(np.sum(n[self._seeded] >= 1.0))
        else:
            self._step_ssa(interval)
            n = self._n
            extinct = int(np.sum(n[self._seeded] == 0))
            alive = int(np.sum(n[self._seeded] > 0))
        total = float(np.asarray(n)[self._seeded].sum())
        return {
            "cumulative_productivity": float(self._productivity),
            "total_population": total,
            "mean_population": total / float(self._n_seeded),
            "n_extinct": float(extinct),
            "n_alive": float(alive),
        }


def ecology_state(proc: "StochasticProtocellEcologyProcess") -> dict:
    """Current per-lineage state for the viz — real community state. Returns
    ``{n_lineages, seeded, eff, counts, byproducts, feed, productivity,
    deterministic, knockout}``."""
    import numpy as np
    if getattr(proc, "_n", None) is None:
        return {"n_lineages": 0, "seeded": [], "eff": [], "counts": [], "productivity": 0.0}
    det = bool(proc.config["deterministic"])
    counts = (proc._nf if det else proc._n)
    byprod = (proc._Bf if det else proc._B)
    feed = (proc._Sf if det else proc._S)
    return {
        "n_lineages": int(proc._k),
        "seeded": [int(i) for i in proc._seeded],
        "eff": [float(x) for x in proc._eff],
        "counts": [float(x) for x in np.asarray(counts)],
        "byproducts": [float(x) for x in np.asarray(byprod)],
        "feed": float(feed),
        "productivity": float(proc._productivity),
        "deterministic": det,
        "knockout": bool(proc.config["knockout"]),
    }
