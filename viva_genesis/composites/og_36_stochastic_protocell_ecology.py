"""Study 36 (Gate E, optional) — Stochastic Protocell Ecology.

Does a heterogeneous population of cross-feeding protocells, run under HONEST
low-count demographic stochasticity (an integer-count Gillespie SSA), develop a
community-level productivity that the best single lineage cannot match at equal
feed — and do stochastic dynamics materially change the outcome versus the
deterministic mean-field? (⚑4: the concrete community-function metric is the
equal-feed productivity margin over the best single lineage, with a causal
cross-feeding knockout and a stochastic-vs-deterministic comparison.)

One :class:`~viva_genesis.ecology.stochastic_ecology.StochasticProtocellEcologyProcess`
drives every arm via config (the feed budget ``feed_total`` is held EQUAL across
arms — only topology and the cross-feeding switch change):

  * **community**   — ``n_seeded = n_lineages``, cross-feeding ON: a ring of
    lineages splitting the feed, byproduct of each cross-feeding the next.
  * **monoculture** — ``n_seeded = 1`` (the most feed-efficient lineage), full
    feed, no partner → cross-feeding is zero. The control the community must beat.
  * **knockout**    — all lineages seeded, feed split, ``knockout=True`` →
    cross-feeding gated off. Isolates whether the margin is causally cross-feeding.

``deterministic=False`` runs the exact SSA (integer counts, a lineage can go
extinct and break the ring); ``deterministic=True`` runs the matched mean-field
Euler ODE. The study compares both.

Option B: a lightweight, dependency-free numpy SSA (reproduction, honestly
labelled); the GillesPy2 / COBRApy genome-scale resolution is the follow-on
og-36a. Parameters are proposed_inputs, not fitted; the metabolism is the
sustained A1 cross-feeding community, not autocatalysis (A2 refuted). Ties to
og-07 (ecology before LUCA), og-32 (the self-maintaining protocell lineage) and
og-34 (selectable heredity).
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core


@composite_generator(
    name="og_36_stochastic_protocell_ecology",
    methods=["lightweight dependency-free Gillespie SSA (integer cell counts)",
             "matched mean-field Euler ODE on identical propensities",
             "ring cross-feeding community vs best-single-lineage control at equal feed"],
    fidelity="reproduction",
    description=(
        "Gate E ecology: does a cross-feeding protocell community out-produce the best single "
        "lineage at EQUAL feed, is the margin causally due to cross-feeding (knockout), and do "
        "low-count stochastic dynamics materially change it versus the deterministic mean-field? "
        "One StochasticProtocellEcologyProcess drives all arms: community (all seeded, cross-feeding "
        "on), monoculture (best single lineage, full feed, no partner), knockout (all seeded, "
        "cross-feeding off). deterministic=False is the exact Gillespie SSA (extinction breaks the "
        "ring); deterministic=True the matched mean-field. Option B (dependency-free SSA); "
        "GillesPy2/COBRApy = og-36a. Metabolism = sustained A1 community, NOT autocatalytic (A2 refuted)."
    ),
    parameters={
        "n_lineages": {"type": "integer", "default": 4, "description": "Number of protocell lineages on the ring"},
        "n_seeded": {"type": "integer", "default": 4, "description": "Lineages alive at t0 (set 1 for a monoculture arm — the best single lineage)"},
        "knockout": {"type": "boolean", "default": False, "description": "Cross-feeding OFF (b_cross gated to 0) — the causal ablation"},
        "deterministic": {"type": "boolean", "default": False, "description": "Mean-field Euler ODE (True) vs exact Gillespie SSA (False)"},
        "feed_F": {"type": "float", "default": 16.0, "description": "Shared limiting feed influx, held EQUAL across arms (NOT split by lineage count)"},
        "feed_Ks": {"type": "float", "default": 6.0, "description": "Monod half-saturation on the shared feed S"},
        "cross_Kb": {"type": "float", "default": 6.0, "description": "Monod half-saturation on the byproduct B"},
        "mu": {"type": "float", "default": 0.55, "description": "Birth coefficient on the shared feed"},
        "mu_cross": {"type": "float", "default": 0.50, "description": "Cross-feeding (byproduct recycling) birth coefficient"},
        "k_feed_wash": {"type": "float", "default": 0.25, "description": "Shared-feed washout rate"},
        "k_byprod_wash": {"type": "float", "default": 0.30, "description": "Byproduct washout rate (what a monoculture loses)"},
        "d0": {"type": "float", "default": 0.11, "description": "Cell death/washout rate"},
        "eff_spread": {"type": "float", "default": 0.30, "description": "Heterogeneity of per-lineage feed efficiency (0 = identical)"},
        "n0": {"type": "integer", "default": 5, "description": "Initial cells per seeded lineage"},
        "S0": {"type": "float", "default": 20.0, "description": "Initial shared feed"},
        "mono_lineage": {"type": "integer", "default": -1, "description": "Monoculture arm: which lineage to seed (-1 = most efficient); lets the sims take the true best single lineage"},
        "seed": {"type": "integer", "default": 1, "description": "RNG seed (reproducible SSA trajectory / efficiency assignment)"},
    },
    default_n_steps=120,
    preferred_time="100 years",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter",
               "paths": ["community/cumulative_productivity", "community/total_population",
                         "community/n_extinct", "community/n_alive"]}],
)
def og_36_stochastic_protocell_ecology(
        core=None, *, n_lineages=4, n_seeded=4, knockout=False, deterministic=False,
        feed_F=16.0, feed_Ks=6.0, cross_Kb=6.0, mu=0.55, mu_cross=0.50,
        k_feed_wash=0.25, k_byprod_wash=0.30, d0=0.11, eff_spread=0.30,
        n0=5, S0=20.0, mono_lineage=-1, seed=1):
    if core is None:
        core = build_core()
    return {
        "ecology": {
            "_type": "process",
            "address": "local:StochasticProtocellEcologyProcess",
            "config": {"n_lineages": int(n_lineages), "n_seeded": int(n_seeded),
                       "knockout": bool(knockout), "deterministic": bool(deterministic),
                       "feed_F": float(feed_F), "feed_Ks": float(feed_Ks), "cross_Kb": float(cross_Kb),
                       "mu": float(mu), "mu_cross": float(mu_cross), "k_feed_wash": float(k_feed_wash),
                       "k_byprod_wash": float(k_byprod_wash), "d0": float(d0), "eff_spread": float(eff_spread),
                       "n0": int(n0), "S0": float(S0), "mono_lineage": int(mono_lineage), "seed": int(seed)},
            "interval": 1.0,
            "inputs": {},
            "outputs": {"cumulative_productivity": ["community", "cumulative_productivity"],
                        "total_population": ["community", "total_population"],
                        "mean_population": ["community", "mean_population"],
                        "n_extinct": ["community", "n_extinct"],
                        "n_alive": ["community", "n_alive"]},
        },
        "community": {"cumulative_productivity": 0.0, "total_population": 0.0, "mean_population": 0.0,
                      "n_extinct": 0.0, "n_alive": 0.0},
    }
