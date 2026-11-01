"""Multi-metabolite bidirectional exchange process for the proto_endosymbiosis bridge (M7).

M6 models a SINGLE metabolite flowing one way (producer -> consumer). But the eukaryogenesis
syntrophy hypotheses (the hydrogen hypothesis, syntrophy hypothesis) are OBLIGATE MUTUALISMS:
host and symbiont RECIPROCALLY exchange two metabolites, and each partner's realised benefit
is stoichiometrically limited by whichever exchanged metabolite is scarcer at its location
(Liebig's law of the minimum). M7 adds that: two screened reaction-diffusion fields A and B,

  * host at x=0 PRODUCES A and CONSUMES B;
  * symbiont at x=d PRODUCES B and CONSUMES A;
  * the mutualistic benefit = min(B reaching the host, A reaching the symbiont) * yield.

Because the benefit is the MINIMUM of two proximity-dependent fluxes, obligate bidirectional
syntrophy is predicted to be MORE steeply proximity-dependent than a one-way benefit (the
falloff compounds) and MORE fragile to production asymmetry (the scarcer flux caps both). The
model MEASURES these rather than assuming them, by comparing contact vs distal and symmetric
vs asymmetric production.

Inferential scope: reduced 1-D screened two-field diffusion at steady state with Liebig
coupling; captures the stoichiometric + bidirectional structure of syntrophy, not full
genome-scale metabolic stoichiometry or 3-D geometry.
"""
from __future__ import annotations

from process_bigraph import Process


class MultiMetaboliteExchangeProcess(Process):
    """Two reciprocal screened fields (A host->symbiont, B symbiont->host), Liebig-coupled.

    Exposes the cross-received levels — ``symbiont_a_conc`` (A reaching the symbiont) and
    ``host_b_conc`` (B reaching the host) — whose minimum is the realised mutualistic benefit.
    """

    config_schema = {
        "n_cells": {"_type": "integer", "_default": 16},
        "diffusion": {"_type": "float", "_default": 0.4},
        "decay": {"_type": "float", "_default": 0.08},
        "production_a": {"_type": "float", "_default": 1.0},   # host output of metabolite A
        "production_b": {"_type": "float", "_default": 1.0},   # symbiont output of metabolite B
        "uptake": {"_type": "float", "_default": 0.2},
        "symbiont_distance": {"_type": "integer", "_default": 1},
    }

    def inputs(self):
        return {"conc_a": "map[float]", "conc_b": "map[float]",
                "symbiont_a_conc": "float", "host_b_conc": "float"}

    def outputs(self):
        return {"conc_a": "map[float]", "conc_b": "map[float]",
                "symbiont_a_conc": "float", "host_b_conc": "float"}

    def _step_field(self, x, n, D, k, dt, src_cell, src_rate, sink_cell, uptake):
        dc = [0.0] * n
        for i in range(n):
            left = x[i - 1] if i > 0 else x[i]
            right = x[i + 1] if i < n - 1 else x[i]
            dc[i] = (D * (left - 2.0 * x[i] + right) - k * x[i]) * dt
        dc[src_cell] += src_rate * dt
        dc[sink_cell] -= uptake * x[sink_cell] * dt
        return dc

    def update(self, state, interval):
        c = self.config
        n = int(c["n_cells"])
        D = float(c["diffusion"]); k = float(c["decay"]); up = float(c["uptake"])
        dt = float(interval)
        d = min(int(c["symbiont_distance"]), n - 1)
        fa = state.get("conc_a") or {}
        fb = state.get("conc_b") or {}
        a = [float(fa.get(str(i), 0.0) or 0.0) for i in range(n)]
        b = [float(fb.get(str(i), 0.0) or 0.0) for i in range(n)]
        # A: produced at host (0), consumed by symbiont (d). B: produced at symbiont (d), consumed by host (0).
        dca = self._step_field(a, n, D, k, dt, 0, float(c["production_a"]), d, up)
        dcb = self._step_field(b, n, D, k, dt, d, float(c["production_b"]), 0, up)
        new_sym_a = a[d] + dca[d]        # A reaching the symbiont
        new_host_b = b[0] + dcb[0]       # B reaching the host
        return {
            "conc_a": {str(i): dca[i] for i in range(n)},
            "conc_b": {str(i): dcb[i] for i in range(n)},
            "symbiont_a_conc": new_sym_a - float(state.get("symbiont_a_conc", 0.0) or 0.0),
            "host_b_conc": new_host_b - float(state.get("host_b_conc", 0.0) or 0.0),
        }
