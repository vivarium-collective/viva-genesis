"""Vertical-transmission + conflict process for the proto_endosymbiosis bridge (M5).

M1–M4 measure whether the endosymbiosis ESTABLISHES (selection for contact, stable
enclosure, their joint feasibility). They do not test whether, once established, the
partnership is EVOLUTIONARILY STABLE across lineage generations. M5 adds that axis
explicitly: a population of host lineages, some bearing a functional symbiont, reproducing
with division, where

  * vertical transmission is imperfect — at division a symbiont-bearing host produces a
    symbiont-free daughter with probability (1 - fidelity) (segregational loss);
  * conflict / partner-loss removes the symbiont from a bearing lineage at rate loss_rate
    (antagonism, digestion, failure to re-partition);
  * the symbiont confers a net fitness advantage (exchange benefit minus maintenance cost),
    so selection favours bearers — the counter-force to loss;
  * rare horizontal re-acquisition lets symbiont-free hosts regain one at reacquire_rate.

The observable ``endosymbiont_retention_fraction`` is the settled fraction of lineages that
still bear a functional symbiont after many generations. It is EMERGENT: high only when
transmission fidelity and the selective advantage together outrun loss; it collapses to ~0
when loss or segregational leakage dominates — i.e. the transition can establish yet still
be evolutionarily unstable.

Inferential scope: reduced two-compartment logistic replicator (symbiont-bearing vs free)
with a carrying capacity; captures the balance of inheritance, selection, and loss, not the
molecular partition machinery or an explicit genome.
"""
from __future__ import annotations

from process_bigraph import Process


class VerticalTransmissionProcess(Process):
    """Two-compartment heredity dynamics: n_sym (symbiont-bearing) vs n_free (host-only).

    Logistic growth under a shared carrying capacity; symbiont bearers grow faster by the
    net benefit, leak to free by imperfect transmission, and are lost to conflict; free
    hosts rarely re-acquire.
    """

    config_schema = {
        "benefit": {"_type": "float", "_default": 0.6},        # net exchange benefit of bearing a symbiont
        "cost": {"_type": "float", "_default": 0.1},           # maintenance cost of the symbiont
        "fidelity": {"_type": "float", "_default": 0.95},      # P(daughter inherits symbiont) at division
        "loss_rate": {"_type": "float", "_default": 0.05},     # conflict / partner-loss (sym -> free)
        "reacquire_rate": {"_type": "float", "_default": 0.01},# horizontal re-acquisition (free -> sym)
        "base_growth": {"_type": "float", "_default": 0.3},    # selection timescale (per-generation turnover)
    }

    def inputs(self):
        return {"n_sym": "float", "n_free": "float"}

    def outputs(self):
        return {"n_sym": "float", "n_free": "float"}

    def update(self, state, interval):
        c = self.config
        sym = max(float(state.get("n_sym", 0.0) or 0.0), 0.0)
        free = max(float(state.get("n_free", 0.0) or 0.0), 0.0)
        N = sym + free
        if N <= 0:
            return {"n_sym": 0.0, "n_free": 0.0}
        dt = float(interval)
        g = float(c["base_growth"])
        p = sym / N
        # frequency replicator at constant population (selection keeps acting via turnover):
        #   + selective advantage of bearers (benefit - cost), via differential reproduction
        #   - segregational loss: bearers produce symbiont-free daughters at rate (1-fidelity)
        #   - conflict / partner-loss removes the symbiont
        #   + rare horizontal re-acquisition
        rate_p = (g * (float(c["benefit"]) - float(c["cost"])) * p * (1.0 - p)
                  - g * (1.0 - float(c["fidelity"])) * p
                  - float(c["loss_rate"]) * p
                  + float(c["reacquire_rate"]) * (1.0 - p))
        dn = N * rate_p * dt
        dn = max(min(dn, free), -sym)      # keep both compartments non-negative (N constant)
        return {"n_sym": dn, "n_free": -dn}
