"""Spatial metabolite-exchange process for the proto_endosymbiosis bridge (M6).

M1–M5 treat the exchange benefit as a LUMPED, frequency-dependent term and ASSUME that
contact scales exchange access. M6 tests that premise mechanistically: a 1-D reaction–
diffusion field where a producer cell (x=0) releases a shared metabolite that diffuses
(coefficient `diffusion`) and decays (`decay`), and a consumer cell at `consumer_distance`
takes it up. The steady-state metabolite level at the consumer sets the REALISED exchange
benefit, and it falls off with distance over the screening length lambda = sqrt(D/decay).

So the model answers: is realised exchange strongly proximity-dependent (steep falloff ⇒
contact genuinely confers an exchange advantage ⇒ M1's lumped premise is justified), or is
the field effectively well-mixed (shallow falloff ⇒ contact barely helps ⇒ the premise is
weak)? It can go either way depending on the diffusion/decay regime, so it MEASURES rather
than imposes the proximity dependence.

Inferential scope: reduced 1-D screened-diffusion field at steady state with reflecting
boundaries; captures the proximity–benefit relationship and its screening regime, not a full
3-D geometry, advection, or multi-metabolite stoichiometry.
"""
from __future__ import annotations

from process_bigraph import Process


class DiffusiveExchangeProcess(Process):
    """1-D screened diffusion of a shared metabolite from a producer to a distant consumer.

    The field `conc` (a map of cell -> concentration) relaxes to steady state; the consumer
    concentration `consumer_conc` is exposed (set-via-delta) as the realised exchange level.
    """

    config_schema = {
        "n_cells": {"_type": "integer", "_default": 16},
        "diffusion": {"_type": "float", "_default": 0.4},        # D
        "decay": {"_type": "float", "_default": 0.08},           # k  (lambda = sqrt(D/k))
        "production": {"_type": "float", "_default": 1.0},       # source flux at the producer (cell 0)
        "uptake": {"_type": "float", "_default": 0.2},           # consumer uptake rate
        "consumer_distance": {"_type": "integer", "_default": 1},
    }

    def inputs(self):
        return {"conc": "map[float]", "consumer_conc": "float"}

    def outputs(self):
        return {"conc": "map[float]", "consumer_conc": "float"}

    def update(self, state, interval):
        c = self.config
        n = int(c["n_cells"])
        D = float(c["diffusion"]); k = float(c["decay"])
        dt = float(interval)
        cons = min(int(c["consumer_distance"]), n - 1)
        field = state.get("conc") or {}
        x = [float(field.get(str(i), 0.0) or 0.0) for i in range(n)]
        dc = [0.0] * n
        for i in range(n):
            left = x[i - 1] if i > 0 else x[i]        # reflecting (no-flux) boundaries
            right = x[i + 1] if i < n - 1 else x[i]
            lap = left - 2.0 * x[i] + right
            dc[i] = (D * lap - k * x[i]) * dt
        dc[0] += float(c["production"]) * dt           # producer source
        dc[cons] -= float(c["uptake"]) * x[cons] * dt  # consumer uptake sink
        new_cons = x[cons] + dc[cons]
        delta_map = {str(i): dc[i] for i in range(n)}
        # expose the consumer level as an absolute store via a set-to-target delta
        return {"conc": delta_map,
                "consumer_conc": new_cons - float(state.get("consumer_conc", 0.0) or 0.0)}
