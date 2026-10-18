"""Module H (Gate D) — chemical heredity & selection in a protocell population
(study og-34).

A population of study-33 dividing protocells, each carrying an inherited NETWORK
COMPOSITION trait ``c`` in [0,1] (⚑3 Option B: compositional / GARD-style
inheritance; template copying is the follow-on og-34a). The trait is GROUNDED in
the real study-32/33 coupling: ``c`` sets the amphiphile chain length -> membrane
retention via the study-32 MD-informed relation (short di-C12 retention ~0.333 ->
long di-C16 ~0.661), and higher retention raises the standing pool and so the
division rate (study 33) = FITNESS. Selection therefore favours higher-retention
composition.

One ``update`` = one generation of a Wright-Fisher birth step: N offspring, each
from a parent sampled in proportion to fitness.
  inheritance=True  — offspring inherit the parent trait + heritable noise N(0, sigma)
  inheritance=False — matched NO-INHERITANCE null: offspring trait is drawn around
                      the common (population-mean) composition, breaking the
                      parent-offspring link (daughters reset to a common composition)

Reports, per generation: the parent-offspring FITNESS correlation (Pearson r over
the birth pairs), the population COMPOSITION SHIFT (mean c minus the initial mean),
the heritable fitness variance, and the selection response (dmean per generation).

The vasas-2010 evolvability caveat (compositional inheritance may lack the variance
selection needs) is TESTED, not assumed: whether the inheriting population actually
shifts above the no-inheritance control is the readout; ``sigma`` is a declared
heritable variance, NOT tuned to force a shift. The metabolism is the sustained A1
carbon-fixing network, not autocatalytic (A2 refuted).
"""
from __future__ import annotations

from process_bigraph import Process

_FLOAT = {"_type": "float"}
_O_FLOAT = {"_type": "overwrite[float]"}
_O_COUNT = {"_type": "overwrite[integer]"}


class HeredityPopulationProcess(Process):
    """Wright-Fisher selection on an inherited network-composition trait."""

    config_schema = {
        "inheritance": {"_type": "boolean", "_default": True},                    # inherit parent trait vs no-inheritance null
        "n_pop": {"_type": "integer", "_default": 80, "_units": "dimensionless"},  # population size
        "sigma": {"_type": "float", "_default": 0.03, "_units": "dimensionless"},  # heritable mutation std (declared, not tuned)
        "c_init_mean": {"_type": "float", "_default": 0.4, "_units": "dimensionless"},
        "c_init_sigma": {"_type": "float", "_default": 0.15, "_units": "dimensionless"},
        # composition c in [0,1] -> membrane retention (study-32 MD endpoints: short/long chain)
        "retention_lo": {"_type": "float", "_default": 0.333, "_units": "dimensionless"},
        "retention_hi": {"_type": "float", "_default": 0.661, "_units": "dimensionless"},
        "fitness_exponent": {"_type": "float", "_default": 2.0, "_units": "dimensionless"},  # sharpens selection on retention
        "seed": {"_type": "integer", "_default": 7, "_units": "dimensionless"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config, core)
        self._init_state()

    def _init_state(self):
        import numpy as np
        self._np = np
        self._rng = np.random.default_rng(int(self.config["seed"]))
        n = int(self.config["n_pop"])
        c = self._rng.normal(float(self.config["c_init_mean"]),
                             float(self.config["c_init_sigma"]), size=n)
        self._c = np.clip(c, 0.0, 1.0)
        self._c0_mean = float(self._c.mean())
        self._prev_mean = self._c0_mean
        self._gen = 0

    def _fitness(self, c):
        lo, hi = float(self.config["retention_lo"]), float(self.config["retention_hi"])
        retention = lo + (hi - lo) * self._np.clip(c, 0.0, 1.0)
        # fitness rises with retention (higher standing pool -> higher division rate)
        return retention ** float(self.config["fitness_exponent"])

    def inputs(self):
        return {"metabolic_flux": _FLOAT}

    def outputs(self):
        return {
            "parent_offspring_fitness_correlation": _O_FLOAT,
            "population_composition_shift": _O_FLOAT,
            "heritable_fitness_variance": _O_FLOAT,
            "selection_response": _O_FLOAT,
            "mean_composition": _O_FLOAT,
            "generation": _O_COUNT,
        }

    def initial_state(self):
        return {"metabolic_flux": 0.0}

    def update(self, state, interval):
        np = self._np
        inheritance = bool(self.config["inheritance"])
        sigma = float(self.config["sigma"])
        n = self._c.size

        fit = self._fitness(self._c)
        p = fit / fit.sum() if fit.sum() > 0 else np.full(n, 1.0 / n)
        parents = self._rng.choice(n, size=n, replace=True, p=p)
        parent_fit = fit[parents]

        if inheritance:
            offspring = self._c[parents] + self._rng.normal(0.0, sigma, size=n)
        else:
            # no-inheritance null: daughters reset to the common (mean) composition,
            # so offspring trait is independent of the parent (link broken).
            common = float(self._c.mean())
            offspring = common + self._rng.normal(0.0, sigma, size=n)
        offspring = np.clip(offspring, 0.0, 1.0)
        offspring_fit = self._fitness(offspring)

        # parent-offspring fitness correlation over this generation's birth pairs
        if np.std(parent_fit) > 1e-12 and np.std(offspring_fit) > 1e-12:
            r = float(np.corrcoef(parent_fit, offspring_fit)[0, 1])
        else:
            r = 0.0

        self._c = offspring
        self._gen += 1
        mean_c = float(self._c.mean())
        selection_response = mean_c - self._prev_mean
        self._prev_mean = mean_c

        return {
            "parent_offspring_fitness_correlation": r,
            "population_composition_shift": mean_c - self._c0_mean,
            "heritable_fitness_variance": float(np.var(self._fitness(self._c))),
            "selection_response": selection_response,
            "mean_composition": mean_c,
            "generation": self._gen,
        }
