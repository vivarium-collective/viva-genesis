"""S06 evolutionary individuality: generational group-selection Process.

One ``update()`` advances ONE generation: build a CPM world of ``n_founders``
patches (founder f = cell type f+1; mixed arm adds a patch-specific cheater type
f+1+n), grow/divide through a transient window, measure group fitness
(largest-cluster fraction), compute the Price partition, then select + reseed.
"""
from __future__ import annotations

import math

from process_bigraph import Process

_EMIT_KEYS = ("mean_adhesion", "among_group", "within_group", "delta_adhesion",
              "mean_toughness", "heritability")


class GroupSelectionProcess(Process):
    config_schema = {
        "n_founders": {"_type": "integer", "_default": 6},
        "generations": {"_type": "integer", "_default": 6},
        "window": {"_type": "integer", "_default": 40},
        "mcs_per_update": {"_type": "integer", "_default": 16},
        "grow_rate": {"_type": "number", "_default": 2.0},
        "divide_threshold": {"_type": "number", "_default": 55.0},
        "seed_volume": {"_type": "number", "_default": 30.0},
        "region": {"_type": "integer", "_default": 60},
        "mutation_sd": {"_type": "number", "_default": 0.08},
        "selection": {"_type": "boolean", "_default": True},
        "clonality": {"_type": "string", "_default": "clonal"},
        "cheater_adhesion": {"_type": "number", "_default": 0.0},
        "selection_fraction": {"_type": "number", "_default": 0.5},
        "init_adhesion_lo": {"_type": "number", "_default": 0.0},
        "init_adhesion_hi": {"_type": "number", "_default": 0.6},
        "seed": {"_type": "integer", "_default": 1},
    }

    def initialize(self, config):
        import numpy as np

        self.rng = np.random.default_rng(int(self.config["seed"]))
        self.n = int(self.config["n_founders"])
        self.adhesions = np.clip(
            self.rng.uniform(self.config["init_adhesion_lo"],
                             self.config["init_adhesion_hi"], self.n), 0, 1)
        self.gen = 0
        self.last_world = None
        self.last_seeded_cells = 0
        self.last_seeded_types = ()

    def inputs(self):
        return {}

    def outputs(self):
        out = {k: "overwrite[float]" for k in _EMIT_KEYS}
        out["generation"] = "overwrite[integer]"
        return out

    # ------------------------------------------------------------------
    def _build_world(self, mixed):
        from viva_cpm.schema import load_world
        from viva_genesis.composites.multicellularity_world import (
            J_MEDIUM, homotypic_j)

        c = self.config
        n, region = self.n, int(c["region"])
        vol = float(c["seed_volume"])
        cols = int(math.ceil(math.sqrt(n)))
        grid = cols * region + 8
        side = max(2, int(round(vol ** 0.5)))
        gap = 1
        cells = []
        contact = [{"a": 0, "b": 0, "j": 0.0}]
        for f in range(n):
            ft = f + 1
            contact.append({"a": 0, "b": ft, "j": J_MEDIUM})
            contact.append({"a": ft, "b": ft, "j": homotypic_j(float(self.adhesions[f]))})
            if mixed:
                ct = ft + n
                contact.append({"a": 0, "b": ct, "j": J_MEDIUM})
                contact.append({"a": ct, "b": ct,
                                "j": homotypic_j(float(c["cheater_adhesion"]))})
                contact.append({"a": ft, "b": ct, "j": J_MEDIUM})
            r, col = divmod(f, cols)
            ox, oy = col * region + 4, r * region + 4
            k = 0
            for i in range(2):
                for j in range(2):
                    x0, y0 = ox + i * (side + gap), oy + j * (side + gap)
                    t = ft + n if (mixed and k % 2 == 1) else ft
                    cells.append({"type": t, "target_volume": vol,
                                  "lambda_volume": 2.0,
                                  "target_surface": 4.0 * side,
                                  "lambda_surface": 0.2,
                                  "seed_block": [x0, y0, 0, x0 + side, y0 + side, 1]})
                    k += 1
        spec = {"potts": {"dims": [grid, grid, 1], "boundary": "noflux",
                          "neighbor_order": 2, "temperature": 8.0,
                          "seed": int(c["seed"]) + self.gen},
                "cells": cells, "contact": contact}
        return load_world(spec)

    def _group_traits(self, part, f, mixed):
        """Cell-count-weighted mean adhesion of patch f from by_cell_type; None if empty."""
        bt = part["by_cell_type"]
        a = bt.get(f + 1, {"n_cells": 0})["n_cells"]
        b = bt.get(f + 1 + self.n, {"n_cells": 0})["n_cells"] if mixed else 0
        if a + b == 0:
            return None
        ch = float(self.config["cheater_adhesion"])
        return (a * float(self.adhesions[f]) + b * ch) / (a + b)

    def update(self, state, interval):
        import numpy as np
        from viva_cpm import metrics
        from viva_genesis.composites.multicellularity_world import group_partition

        c = self.config
        n = self.n
        mixed = c["clonality"] == "mixed"
        founders = [f + 1 for f in range(n)]
        all_types = founders + ([f + 1 + n for f in range(n)] if mixed else [])

        world = self._build_world(mixed)
        self.last_seeded_cells = int(world.n_cells())
        self.last_seeded_types = tuple(all_types)
        adh = np.array(self.adhesions, dtype=float)

        # parent group trait at seeding (realized, count-weighted)
        p0 = group_partition(world, founders)
        z = np.array([self._group_traits(p0, f, mixed) for f in range(n)], dtype=float)

        for _ in range(int(c["window"])):
            for t in all_types:
                try:
                    world.grow(t, float(c["grow_rate"]))
                except Exception:
                    pass
            world.step(int(c["mcs_per_update"]))
            try:
                world.divide_cells(float(c["divide_threshold"]), float(c["seed_volume"]))
            except Exception:
                pass
        self.last_world = world

        part = group_partition(world, founders)
        w = np.zeros(n)
        zp = z.copy()
        for f in range(n):
            types = [f + 1, f + 1 + n] if mixed else [f + 1]
            try:
                w[f] = float(metrics.largest_cluster_fraction(world, types))
            except Exception:
                w[f] = 0.0
            t_end = self._group_traits(part, f, mixed)
            if t_end is not None:
                zp[f] = t_end

        wbar = float(w.mean())
        if wbar > 0:
            among = float((np.mean(w * z) - w.mean() * z.mean()) / wbar)
            within = float(np.mean(w * (zp - z)) / wbar)
            delta = float(np.sum(w * zp) / np.sum(w) - z.mean())
        else:
            among = within = delta = 0.0
        if np.var(adh) > 0:
            herit = float(np.cov(adh, z, bias=True)[0, 1] / np.var(adh))
        else:
            herit = 1.0

        emit = {"generation": int(self.gen), "mean_adhesion": float(adh.mean()),
                "among_group": among, "within_group": within,
                "delta_adhesion": delta, "mean_toughness": wbar,
                "heritability": herit}

        # selection (or drift null) + reseed
        k = max(1, int(math.ceil(n * float(c["selection_fraction"]))))
        if c["selection"]:
            winners = np.argsort(-w, kind="stable")[:k]
        else:
            winners = self.rng.permutation(n)[:k]
        nxt = []
        for wi in winners:
            for _ in range(2):
                nxt.append(float(np.clip(adh[wi] + self.rng.normal(0, float(c["mutation_sd"])), 0, 1)))
        # k winners * 2 offspring may be < n for small fractions; cycle winners
        i = 0
        while len(nxt) < n:
            nxt.append(float(np.clip(adh[winners[i % k]] + self.rng.normal(0, float(c["mutation_sd"])), 0, 1)))
            i += 1
        self.adhesions = np.array(nxt[:n])
        self.gen += 1
        return emit
