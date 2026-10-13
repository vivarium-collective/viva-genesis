"""Module H — bioenergetic internalization as an evolutionary control loop.

Campaign-V transition: can SELECTION move lineages from externally imposed
geochemical gradients toward internally maintained electrochemical states
(catalytic ion transport → active pumping)? This is the study's proposed primary
method — a **custom evolutionary control loop** over membrane parameters, with the
Sojo-2014 leaky-membrane bioenergetics as the fitness substrate. It is a
coarse-grained selection model (deterministic replicator dynamics, reproducible),
not a wrapped MD/ALife engine, and is labeled as such.

Each lineage is a strategy (membrane permeability P, active-pump rate) competing
for free-energy flux:

    flux(P, pump) = k_ext · external_pmf · P            (tap the geochemical gradient
                                                         — needs LEAK, the Sojo point)
                  + k_int · pump · efficiency · (1 − P)  (pump builds an internal pmf
                                                         — needs a TIGHT membrane)
                  − c_pump · pump − c_base               (maintenance)

Replicator dynamics select strategies ∝ flux each generation (with mild mutation).
As the external gradient is lowered over the run, the external term shrinks and the
population **internalizes** — mass shifts to tight-membrane, high-pump strategies —
but only where the pump is efficient enough to beat its cost against the lost
external coupling (the Sojo constraint). Too tight with a weak pump → flux collapses
→ extinction.
"""
from __future__ import annotations

from process_bigraph import Process

_V = {"_type": "float", "_units": "volt"}
_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_WATT = {"_type": "float", "_units": "watt"}
_MPS = {"_type": "float", "_units": "meter/second"}


class BioenergeticSelectionProcess(Process):
    """Deterministic replicator-dynamics evolutionary control loop over membrane
    strategies (permeability × active-pump rate), with a Sojo-2014 leaky-membrane
    fitness. Reads the external gradient (electric potential) and catalyst
    efficiency; selects strategies ∝ free-energy flux each generation; and emits
    the population's lineage fitness, free-energy flux, internalization fraction
    and mean permeability (overwrite sensors — the current population state)."""

    contract = {
        "summary": "Evolutionary control loop (replicator dynamics) over membrane strategies with Sojo-2014 leaky-membrane fitness: does selection internalize gradient generation as the external gradient drops?",
        "description": (
            "Coarse-grained, deterministic selection model (the study's proposed primary "
            "method; not a wrapped ALife/MD engine). A grid of membrane strategies "
            "(permeability P × active-pump rate) competes for free-energy flux = "
            "k_ext*external_pmf*P + k_int*pump*efficiency*(1-P) - c_pump*pump - c_base. "
            "Replicator dynamics select strategies proportional to flux each generation; "
            "as the external gradient is lowered the population internalizes (mass shifts "
            "to tight-membrane, high-pump strategies) only where the pump beats its cost "
            "against the lost external coupling — the Sojo leaky-membrane constraint. All "
            "outputs are overwrite sensors; the population is integrated internally."
        ),
        "inputs": {
            "electric_potential": "external geochemical gradient available to tap (volt)",
            "catalyst_efficiency": "active-pump (Na+/H+) catalytic efficiency (dimensionless)",
        },
        "outputs": {
            "lineage_fitness": "population mean free-energy flux (fitness) (dimensionless, normalized)",
            "free_energy_flux": "population mean free-energy flux (watt)",
            "internalization": "mean active-pump fraction of the surviving population (dimensionless, 0-1)",
            "mean_permeability": "population mean membrane permeability (meter/second)",
            "survivors": "fraction of strategy mass above the survival threshold (dimensionless)",
        },
        "assumptions": [
            "Coarse-grained deterministic replicator dynamics (reproducible); the proposed primary method.",
            "Sojo-2014 fitness: tapping the external gradient needs leak (∝ P); internal pumping needs a tight membrane (∝ 1-P) and pays a cost.",
            "Internalization is an evolutionary outcome, not a scripted upgrade.",
        ],
        "math": [
            "flux(P,pump) = k_ext*Vext*P + k_int*pump*eff*(1-P) - c_pump*pump - c_base",
            "f_s(t+1) ∝ f_s(t) * max(flux_s, 0)   (replicator, + mild mutation)",
            "internalization = sum_s f_s * pump_s",
        ],
        "symbols": {
            "P": "membrane permeability (leakiness)", "pump": "active-pump rate",
            "Vext": "external electric potential / pmf", "eff": "pump catalyst efficiency",
        },
        "references": ["sojo2014bioenergetic", "lane2012origin", "lane2010chemiosmotic"],
    }

    config_schema = {
        "grid": {"_type": "integer", "_default": 7},                                  # P × pump strategy grid
        "k_ext": {"_type": "float", "_default": 3.0, "_units": "dimensionless"},       # external-gradient coupling (wins at high Vext)
        "k_int": {"_type": "float", "_default": 1.0, "_units": "dimensionless"},       # internal-pump coupling (wins at low Vext)
        "c_pump": {"_type": "float", "_default": 0.18, "_units": "dimensionless"},     # pump maintenance cost
        "c_base": {"_type": "float", "_default": 0.02, "_units": "dimensionless"},     # base maintenance
        # Survival floor: at a collapsed external gradient, the leaky-external
        # strategy falls below this, so a lineage persists only by internalizing —
        # and only if its pump is efficient enough (the Sojo constraint).
        "survival_threshold": {"_type": "float", "_default": 0.1, "_units": "dimensionless"},
        "mutation": {"_type": "float", "_default": 0.06, "_units": "dimensionless"},   # neighbour diffusion
        "flux_scale_watt": {"_type": "float", "_default": 1.0e-18, "_units": "watt"},  # per-cell flux -> W
        "perm_scale": {"_type": "float", "_default": 1.0e-8, "_units": "meter/second"},  # P=1 -> this permeability
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        import numpy as np
        g = int(self.config["grid"])
        self._P = np.linspace(0.05, 0.95, g)         # permeability (leakiness) axis
        self._pump = np.linspace(0.0, 1.0, g)        # active-pump axis
        PP, UU = np.meshgrid(self._P, self._pump, indexing="ij")
        self._Pflat = PP.ravel()
        self._pumpflat = UU.ravel()
        self._freq = np.ones(self._Pflat.size) / self._Pflat.size   # uniform start
        self._g = g

    def inputs(self):
        return {"electric_potential": _V, "catalyst_efficiency": _DIMLESS}

    def outputs(self):
        return {
            "lineage_fitness": {"_type": "overwrite[float]", "_units": "dimensionless"},
            "free_energy_flux": {"_type": "overwrite[float]", "_units": "watt"},
            "internalization": {"_type": "overwrite[float]", "_units": "dimensionless"},
            "mean_permeability": {"_type": "overwrite[float]", "_units": "meter/second"},
            "survivors": {"_type": "overwrite[float]", "_units": "dimensionless"},
            "external_power": {"_type": "overwrite[float]", "_units": "watt"},
            "internal_power": {"_type": "overwrite[float]", "_units": "watt"},
            "maintenance_power": {"_type": "overwrite[float]", "_units": "watt"},
        }

    def initial_state(self):
        return {"electric_potential": 0.3, "catalyst_efficiency": 1.0}

    def _flux_terms(self, vext, eff):
        """Per-strategy free-energy terms: (external tap, internal pump, maintenance
        cost). The net flux is max(ext + int − cost, 0)."""
        P, pump = self._Pflat, self._pumpflat
        external = float(self.config["k_ext"]) * vext * P
        internal = float(self.config["k_int"]) * pump * eff * (1.0 - P)
        cost = float(self.config["c_pump"]) * pump + float(self.config["c_base"])
        return external, internal, cost

    def _flux(self, vext, eff):
        import numpy as np
        external, internal, cost = self._flux_terms(vext, eff)
        return np.maximum(external + internal - cost, 0.0)

    def update(self, state, interval):
        import numpy as np
        vext = max(float(state.get("electric_potential", 0.0)), 0.0)
        eff = max(float(state.get("catalyst_efficiency", 0.0)), 0.0)

        flux = self._flux(vext, eff)
        # Replicator selection ∝ flux, then mild mutation (neighbour diffusion on
        # the strategy grid) to keep the loop exploring.
        w = self._freq * flux
        tot = w.sum()
        if tot <= 1e-30:
            self._freq = np.zeros_like(self._freq)      # population collapses
        else:
            self._freq = w / tot
            m = float(self.config["mutation"])
            if m > 0:
                grid = self._freq.reshape(self._g, self._g)
                blur = grid.copy()
                blur[1:, :] += m * grid[:-1, :]; blur[:-1, :] += m * grid[1:, :]
                blur[:, 1:] += m * grid[:, :-1]; blur[:, :-1] += m * grid[:, 1:]
                grid = blur / blur.sum()
                self._freq = grid.ravel()

        mass = float(self._freq.sum())
        mean_flux = float((self._freq * flux).sum())           # per-cell (dimensionless)
        internalization = float((self._freq * self._pumpflat).sum()) if mass > 0 else 0.0
        mean_P = float((self._freq * self._Pflat).sum()) if mass > 0 else 0.0
        survivors = float(self._freq[flux > float(self.config["survival_threshold"])].sum())

        # Energy PROVENANCE: population-mean of each term, so the trajectory shows
        # the useful disequilibrium shifting from the external geochemical gradient
        # to internally maintained (pumped) power as the environment declines.
        external, internal, cost = self._flux_terms(vext, eff)
        scale = float(self.config["flux_scale_watt"])
        external_power = float((self._freq * external).sum()) * scale
        internal_power = float((self._freq * internal).sum()) * scale
        maintenance_power = float((self._freq * cost).sum()) * scale

        return {
            "lineage_fitness": mean_flux,
            "free_energy_flux": mean_flux * scale,
            "internalization": internalization,
            "mean_permeability": mean_P * float(self.config["perm_scale"]),
            "survivors": survivors,
            "external_power": external_power,
            "internal_power": internal_power,
            "maintenance_power": maintenance_power,
        }


class EnvironmentalDeclineProcess(Process):
    """Ramps the external geochemical gradient down over the run — the environment
    the lineages must adapt to. Writes a linearly declining electric potential from
    ``v_start`` toward ``v_floor``; the selection loop reads it and (if its pump is
    efficient enough) internalizes before the gradient collapses."""

    contract = {
        "summary": "Linearly declining external electric potential — the environmental gradient the bioenergetic-selection loop must adapt to.",
        "description": "Writes electric_potential = max(v_floor, v_start - decline_rate * t), the lowering geochemical gradient that drives selection toward internalized gradient generation.",
        "inputs": {},
        "outputs": {"electric_potential": "external geochemical gradient this tick (volt)"},
        "assumptions": ["Monotone linear decline (a controlled environmental sweep, not a scripted upgrade of the cells)."],
        "references": ["sojo2014bioenergetic"],
    }

    config_schema = {
        "v_start": {"_type": "float", "_default": 0.40, "_units": "volt"},
        "v_floor": {"_type": "float", "_default": 0.02, "_units": "volt"},
        "decline_rate": {"_type": "float", "_default": 0.01, "_units": "volt/second"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._v = float(self.config["v_start"])

    def inputs(self):
        return {}

    def outputs(self):
        return {"electric_potential": {"_type": "overwrite[float]", "_units": "volt"}}

    def update(self, state, interval):
        self._v = max(float(self.config["v_floor"]),
                      self._v - float(self.config["decline_rate"]) * interval)
        return {"electric_potential": self._v}


def selection_state(proc: "BioenergeticSelectionProcess") -> dict:
    """The current strategy-frequency landscape over (permeability × pump) for the
    viz — every value a real replicator state. Returns ``{P, pump, freq}`` (freq a
    grid-flattened frequency map)."""
    import numpy as np
    if getattr(proc, "_freq", None) is None:
        return {"P": [], "pump": [], "freq": []}
    g = proc._g
    return {"P": proc._P.tolist(), "pump": proc._pump.tolist(),
            "freq": np.asarray(proc._freq).reshape(g, g).tolist()}
