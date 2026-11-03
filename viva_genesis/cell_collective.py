"""Cell-collective process for the multicellularity first cycle (A/B/C comparison).

A reduced mean-field model of a cell population partitioned into unicells and persistent
clonal groups, under three stackable mechanisms matching the seed's first-cycle priority:

    A  adhesion only                 -> do groups FORM and persist?
    B  adhesion + predation/settling -> do groups gain a FITNESS advantage?
    C  model B + oxygen-limited growth -> does transport BOUND the group size/advantage?

It is a reduced model (inferential scope): a mean-field population split, not an explicit
spatial agent/mechanics simulation (that is the next fidelity — PhysiCell / viva-cpm /
Spatio-Flux backends named in the seed's §4). It establishes WHICH mechanism confers group
formation versus a group-level fitness advantage, and how transport limits set in — it does
not reconstruct a historical sequence.

Dynamics (per tick): the persistent-group fraction relaxes toward the adhesion/fragmentation
balance; mean group size grows with that same ratio. Unicell fitness is division minus a
baseline predation death. Group predation death is REDUCED by size when predation rewards
size (ecology); group growth is PENALIZED for large groups when oxygen/transport limits bite.
The discriminating observables are the settled group fraction and the settled group-minus-
unicell fitness difference.
"""
from __future__ import annotations

import math

from process_bigraph import Process


def _sig(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(x, 50.0), -50.0)))


class CellCollectiveProcess(Process):
    """Mean-field unicell/group population under adhesion + ecology + transport.

    group_fraction relaxes to adhesion*division / (adhesion*division + fragmentation).
    mean_group_size relaxes to 1 + size_scale * adhesion / (fragmentation + eps).
    unicell_fitness  = division * (1 - base_predation).
    group_predation  = base_predation * (1 - predation_size_reward * sigmoid(k*(size - predation_size_threshold))).
    group_growth     = division * (1 - transport_penalty * sigmoid(k*(size - oxygen_size_limit))).
    group_fitness    = group_growth * (1 - group_predation).
    """

    config_schema = {
        "adhesion": {"_type": "float", "_default": 0.8},                 # clonal incomplete separation / bond drive
        "fragmentation": {"_type": "float", "_default": 0.2},            # group breakup
        "division_rate": {"_type": "float", "_default": 0.5},
        "base_predation": {"_type": "float", "_default": 0.4},           # size-independent death
        "predation_size_reward": {"_type": "float", "_default": 0.8},    # ecology: size reduces predation
        "predation_size_threshold": {"_type": "float", "_default": 3.0},
        "transport_penalty": {"_type": "float", "_default": 0.8},        # O2-limited growth penalty for large groups
        "oxygen_size_limit": {"_type": "float", "_default": 6.0},
        "size_scale": {"_type": "float", "_default": 4.0},               # adhesion/fragmentation -> size gain
        "relax_rate": {"_type": "float", "_default": 0.4},
        "sharpness": {"_type": "float", "_default": 2.0},
        "seed": {"_type": "integer", "_default": 1},
    }

    def inputs(self):
        return {k: "float" for k in (
            "group_fraction", "mean_group_size",
            "unicell_fitness", "group_fitness", "group_fitness_advantage")}

    def outputs(self):
        return self.inputs()

    def update(self, state, interval):
        c = self.config
        dt = float(interval)
        k = float(c["sharpness"])

        def g(key, default=0.0):
            v = state.get(key, default)
            try:
                return float(v)
            except (TypeError, ValueError):
                return float(default)

        adh = float(c["adhesion"])
        frag = float(c["fragmentation"])
        div = float(c["division_rate"])

        # persistent-group fraction: equilibrium of formation vs fragmentation
        form = adh * div
        gf_target = form / (form + frag + 1e-9)
        gf = g("group_fraction")
        gf_new = gf + float(c["relax_rate"]) * (gf_target - gf) * dt

        # mean group size grows with the adhesion/fragmentation ratio
        gs_target = 1.0 + float(c["size_scale"]) * adh / (frag + 1e-6)
        gs = g("mean_group_size", 1.0)
        gs_new = gs + float(c["relax_rate"]) * (gs_target - gs) * dt

        # fitness: unicell vs group, with ecology (size lowers predation) and transport (size lowers growth)
        uf = div * (1.0 - float(c["base_predation"]))
        size_protection = float(c["predation_size_reward"]) * _sig(k * (gs_new - float(c["predation_size_threshold"])))
        group_pred = float(c["base_predation"]) * (1.0 - size_protection)
        growth_pen = float(c["transport_penalty"]) * _sig(k * (gs_new - float(c["oxygen_size_limit"])))
        group_growth = div * (1.0 - growth_pen)
        gfit = group_growth * (1.0 - group_pred)

        return {
            "group_fraction": gf_new - gf,
            "mean_group_size": gs_new - gs,
            "unicell_fitness": uf - g("unicell_fitness"),
            "group_fitness": gfit - g("group_fitness"),
            "group_fitness_advantage": (gfit - uf) - g("group_fitness_advantage"),
        }
