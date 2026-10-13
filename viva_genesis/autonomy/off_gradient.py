"""Module M — off-gradient persistence as a free-energy + resource budget under
relaxation of geological support (og-08: escape from the vent).

Campaign-VIII transition: what is the **minimum set of innovations** a lineage needs
to persist as the geological reactor's support is withdrawn — the external pmf
gradient, the mineral (FeS) catalyst access, and the geochemical feed all relaxing
toward zero? This is a coarse-grained, deterministic budget model (reproducible),
not a wrapped ALife/MD engine, and is labeled as such.

A lineage lives on a **co-limited** budget (Liebig's law of the minimum): growth needs
BOTH usable free energy AND usable resources —

    energy   = k_ext·gradient_support  +  has_pump·machinery·k_pump·efficiency
    resource = k_res·(feed·mineral_access) + has_importer·machinery·k_imp
    gross    = min(energy, resource)                    # neither substitutes the other
    cost     = c_base + machinery·(has_pump·c_pump + has_importer·c_imp)
    net      = gross − cost

Three toggleable innovations buy independence from the vent:

  - ``has_pump``     — internal energy conversion (Sojo/og-05): make pmf internally,
                       so ``energy`` no longer needs the external gradient.
  - ``has_importer`` — active resource import: acquire scarce feed/minerals, so
                       ``resource`` no longer needs ambient abundance.
  - ``has_heredity`` — information maintenance: without it the adaptive machinery
                       degrades over the run (an error-catastrophe decay), so the
                       pump and importer cannot be *held* — ``machinery`` → 0 and the
                       innovation terms vanish.

Because the budget is co-limited, a single innovation is a cost without a co-benefit
(a pump with nothing to feed it, or an importer with no energy to run it); the set is
**irreducible**. As support → 0 only the full set keeps ``net ≥ survival_floor``, so
the survival frontier identifies ``{pump, importer, heredity}`` as the minimum robust
innovation set. The whole model is deterministic — no RNG — so runs are reproducible.
"""
from __future__ import annotations

from process_bigraph import Process

_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_WATT = {"_type": "float", "_units": "watt"}

# Shared budget coefficients (module-level so the Process, the relaxation driver, and
# the standalone sweep sim all reduce to ONE set of numbers → one physics).
_COEFFS = {
    "k_ext": 1.0,      # external geochemical gradient -> energy (needs gradient_support)
    "k_res": 1.0,      # ambient substrate -> resource (needs feed x mineral_access)
    "k_pump": 0.7,     # internal pump energy (has_pump, scales with machinery)
    "k_imp": 0.7,      # active resource import (has_importer, scales with machinery)
    "c_base": 0.10,    # base maintenance
    "c_pump": 0.12,    # pump upkeep (paid only while machinery holds the innovation)
    "c_imp": 0.12,     # importer upkeep
    "decay_heredity": 0.0,       # machinery decay/step WITH heredity (held)
    "decay_no_heredity": 0.08,   # machinery decay/step WITHOUT heredity (error catastrophe)
    "survival_floor": 0.10,      # net budget must clear this to grow
    "grow": 0.30,      # survivors relaxation toward 1 when net >= floor
    "die": 0.45,       # survivors decay/step when net < floor
    "flux_scale_watt": 1.0e-18,  # per-cell dimensionless flux -> watt
}


def _budget(gradient_support, mineral_access, feed, machinery, *,
            has_pump, has_importer, catalyst_efficiency, c):
    """Co-limited free-energy + resource budget (Liebig minimum). All dimensionless
    per-cell terms. ``machinery`` (0-1) gates the innovation contributions and their
    upkeep — a degraded lineage loses the pump/importer AND stops paying for them."""
    energy = c["k_ext"] * gradient_support + has_pump * machinery * c["k_pump"] * catalyst_efficiency
    resource = c["k_res"] * (feed * mineral_access) + has_importer * machinery * c["k_imp"]
    gross = min(energy, resource)
    cost = c["c_base"] + machinery * (has_pump * c["c_pump"] + has_importer * c["c_imp"])
    return {"energy": energy, "resource": resource, "gross": gross,
            "cost": cost, "net": gross - cost}


def _advance(survivors, machinery, env, *, has_pump, has_importer, has_heredity,
             catalyst_efficiency, c, interval=1.0):
    """One deterministic tick: machinery maintenance (heredity gates the decay), the
    co-limited budget, and the survivors response. Returns (survivors, machinery, b)."""
    decay = c["decay_heredity"] if has_heredity else c["decay_no_heredity"]
    machinery = max(0.0, machinery * (1.0 - decay * interval))
    b = _budget(env["gradient_support"], env["mineral_access"], env["feed"], machinery,
                has_pump=has_pump, has_importer=has_importer,
                catalyst_efficiency=catalyst_efficiency, c=c)
    if b["net"] >= c["survival_floor"]:
        survivors = survivors + c["grow"] * interval * (1.0 - survivors)
    else:
        survivors = survivors * (1.0 - min(1.0, c["die"] * interval))
    survivors = min(1.0, max(0.0, survivors))
    return survivors, machinery, b


def _flags(has_pump=1.0, has_importer=1.0, has_heredity=1.0):
    return {"has_pump": float(has_pump), "has_importer": float(has_importer),
            "has_heredity": float(has_heredity)}


def simulate_offgradient(support, *, has_pump=1.0, has_importer=1.0, has_heredity=1.0,
                         catalyst_efficiency=1.0, n_steps=60, coeffs=None) -> dict:
    """Hold environmental support FIXED at ``support`` (all three channels equal) and
    run the lineage to steady state; return the final persistence (survivors) + budget.
    This is what the Decision-view phase map sweeps over (support x innovation set)."""
    c = dict(_COEFFS)
    if coeffs:
        c.update(coeffs)
    env = {"gradient_support": float(support), "mineral_access": float(support),
           "feed": float(support)}
    survivors, machinery, b = 1.0, 1.0, None
    for _ in range(int(n_steps)):
        survivors, machinery, b = _advance(
            survivors, machinery, env, has_pump=float(has_pump),
            has_importer=float(has_importer), has_heredity=float(has_heredity),
            catalyst_efficiency=float(catalyst_efficiency), c=c)
    return {"survivors": survivors, "machinery": machinery,
            "net": b["net"], "energy": b["energy"], "resource": b["resource"]}


def decline_trajectory(*, has_pump=1.0, has_importer=1.0, has_heredity=1.0,
                       catalyst_efficiency=1.0, n_steps=60, decline_rate=0.02,
                       start=1.0, floor=0.0, coeffs=None) -> dict:
    """Relax support linearly from ``start`` toward ``floor`` over the run and return
    the survivors/support trajectory — the 'escape' time-course for the Decision view
    (the full set persists off-gradient; each knockout collapses as support falls)."""
    c = dict(_COEFFS)
    if coeffs:
        c.update(coeffs)
    survivors, machinery, s = 1.0, 1.0, float(start)
    t, surv, supp, mach = [], [], [], []
    for i in range(int(n_steps) + 1):
        env = {"gradient_support": s, "mineral_access": s, "feed": s}
        t.append(i); surv.append(survivors); supp.append(s); mach.append(machinery)
        survivors, machinery, _ = _advance(
            survivors, machinery, env, has_pump=float(has_pump),
            has_importer=float(has_importer), has_heredity=float(has_heredity),
            catalyst_efficiency=float(catalyst_efficiency), c=c)
        s = max(float(floor), s - float(decline_rate))
    return {"t": t, "survivors": surv, "support": supp, "machinery": mach}


class EnvironmentalRelaxationProcess(Process):
    """Relaxes the geological support the lineage lives on — the external gradient,
    the mineral (FeS) catalyst access, and the geochemical feed — each declining
    linearly from its start toward a floor over the run. The off-gradient lineage
    reads these and must survive their withdrawal (or not)."""

    contract = {
        "summary": "Linearly relaxing environmental support (external gradient, mineral access, feed) — the withdrawal of geological support the lineage must survive to become autonomous.",
        "description": (
            "Writes gradient_support / mineral_access / feed, each = max(floor, start - "
            "decline_rate * t), the relaxation of the vent's support toward zero. A controlled "
            "environmental sweep (not a scripted upgrade of the cells): whether a lineage "
            "persists as support is withdrawn is an emergent property of its innovation set."
        ),
        "inputs": {},
        "outputs": {
            "gradient_support": "external geochemical-gradient availability this tick (dimensionless, 0-1)",
            "mineral_access": "mineral / FeS-catalyst availability this tick (dimensionless, 0-1)",
            "feed": "geochemical feed availability this tick (dimensionless, 0-1)",
        },
        "assumptions": ["Monotone linear relaxation of each support channel (a controlled withdrawal, not a cell upgrade)."],
        "references": ["martin2007origin", "sojo2014bioenergetic"],
    }

    config_schema = {
        "g_start": {"_type": "float", "_default": 1.0, "_units": "dimensionless"},
        "m_start": {"_type": "float", "_default": 1.0, "_units": "dimensionless"},
        "f_start": {"_type": "float", "_default": 1.0, "_units": "dimensionless"},
        "g_floor": {"_type": "float", "_default": 0.0, "_units": "dimensionless"},
        "m_floor": {"_type": "float", "_default": 0.0, "_units": "dimensionless"},
        "f_floor": {"_type": "float", "_default": 0.0, "_units": "dimensionless"},
        "decline_rate": {"_type": "float", "_default": 0.02, "_units": "1/second"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._g = float(self.config["g_start"])
        self._m = float(self.config["m_start"])
        self._f = float(self.config["f_start"])

    def inputs(self):
        return {}

    def outputs(self):
        return {"gradient_support": {"_type": "overwrite[float]", "_units": "dimensionless"},
                "mineral_access": {"_type": "overwrite[float]", "_units": "dimensionless"},
                "feed": {"_type": "overwrite[float]", "_units": "dimensionless"}}

    def update(self, state, interval):
        r = float(self.config["decline_rate"]) * interval
        self._g = max(float(self.config["g_floor"]), self._g - r)
        self._m = max(float(self.config["m_floor"]), self._m - r)
        self._f = max(float(self.config["f_floor"]), self._f - r)
        return {"gradient_support": self._g, "mineral_access": self._m, "feed": self._f}


class OffGradientPersistenceProcess(Process):
    """A lineage's co-limited free-energy + resource budget under relaxing geological
    support, with three toggleable innovations (internal pump, resource importer,
    information maintenance/heredity). Reads the environmental support channels and
    emits survivors, net budget (fitness / free-energy flux), machinery integrity and
    the energy/resource provenance — all overwrite sensors (the lineage state is
    integrated internally). Deterministic and reproducible (no RNG)."""

    contract = {
        "summary": "Co-limited (Liebig-minimum) free-energy + resource budget for a lineage under relaxing geological support, with pump / importer / heredity as toggleable innovations: which minimum set persists off-gradient?",
        "description": (
            "Coarse-grained deterministic budget model (reproducible; not a wrapped ALife/MD "
            "engine). energy = k_ext*gradient_support + has_pump*machinery*k_pump*efficiency; "
            "resource = k_res*feed*mineral_access + has_importer*machinery*k_imp; gross = "
            "min(energy, resource) (co-limitation — neither substitutes the other); net = gross "
            "- (c_base + machinery*(has_pump*c_pump + has_importer*c_imp)). Heredity gates the "
            "machinery decay: without it machinery -> 0 over the run and the pump/importer vanish "
            "(error catastrophe). Survivors grow when net >= survival_floor and decay otherwise. "
            "Because the budget is co-limited, the innovation set is irreducible — as support -> 0 "
            "only {pump, importer, heredity} keeps net above the floor."
        ),
        "inputs": {
            "gradient_support": "external geochemical-gradient availability (dimensionless, 0-1)",
            "mineral_access": "mineral / FeS-catalyst availability (dimensionless, 0-1)",
            "feed": "geochemical feed availability (dimensionless, 0-1)",
        },
        "outputs": {
            "survivors": "persisting population fraction (dimensionless, 0-1)",
            "lineage_fitness": "net co-limited budget (fitness) (dimensionless)",
            "free_energy_flux": "net budget as power (watt)",
            "machinery_integrity": "integrity of the adaptive machinery, gated by heredity (dimensionless, 0-1)",
            "external_power": "power tapped from the external geochemical gradient (watt)",
            "internal_power": "power from internal innovations (pump + importer) (watt)",
        },
        "assumptions": [
            "Coarse-grained deterministic budget (reproducible); the proposed integrated-modules method.",
            "Co-limitation (Liebig minimum): growth needs BOTH usable energy AND usable resources, so a lone innovation is a cost without a co-benefit.",
            "Heredity maintains the adaptive machinery; without it the innovations degrade (error catastrophe) and cannot be held.",
            "Autonomy is emergent (persistence as support is withdrawn), not a scripted upgrade.",
        ],
        "math": [
            "energy = k_ext*g + has_pump*m*k_pump*eff",
            "resource = k_res*f*ma + has_importer*m*k_imp",
            "net = min(energy, resource) - (c_base + m*(has_pump*c_pump + has_importer*c_imp))",
            "m(t+1) = m(t)*(1 - decay),  decay = 0 if heredity else decay_no_heredity",
            "survivors -> 1 if net >= floor else -> 0",
        ],
        "symbols": {"g": "gradient_support", "ma": "mineral_access", "f": "feed",
                    "m": "machinery integrity", "eff": "pump catalyst efficiency"},
        "references": ["sojo2014bioenergetic", "lane2012origin", "martin2007origin"],
    }

    # The three innovations are STRING toggles ("on"/"off"), not floats: a
    # process-bigraph config schema replaces a *falsy* value (a 0.0 float) with its
    # default, so a numeric "0 = knocked out" flag silently reads back as 1.0. Strings
    # are preserved (cf. heredity_module_comparison's ``module`` field).
    config_schema = {
        "pump": {"_type": "string", "_default": "on"},        # internal energy conversion ("on"/"off")
        "importer": {"_type": "string", "_default": "on"},    # active resource import ("on"/"off")
        "heredity": {"_type": "string", "_default": "on"},    # information maintenance ("on"/"off")
        "catalyst_efficiency": {"_type": "float", "_default": 1.0, "_units": "dimensionless"},
        "flux_scale_watt": {"_type": "float", "_default": 1.0e-18, "_units": "watt"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._survivors = 1.0
        self._machinery = 1.0
        self._c = dict(_COEFFS)
        self._c["flux_scale_watt"] = float(self.config["flux_scale_watt"])
        self._has_pump = 1.0 if str(self.config["pump"]).lower() == "on" else 0.0
        self._has_importer = 1.0 if str(self.config["importer"]).lower() == "on" else 0.0
        self._has_heredity = 1.0 if str(self.config["heredity"]).lower() == "on" else 0.0

    def inputs(self):
        return {"gradient_support": _DIMLESS, "mineral_access": _DIMLESS, "feed": _DIMLESS}

    def outputs(self):
        return {
            "survivors": {"_type": "overwrite[float]", "_units": "dimensionless"},
            "lineage_fitness": {"_type": "overwrite[float]", "_units": "dimensionless"},
            "free_energy_flux": {"_type": "overwrite[float]", "_units": "watt"},
            "machinery_integrity": {"_type": "overwrite[float]", "_units": "dimensionless"},
            "external_power": {"_type": "overwrite[float]", "_units": "watt"},
            "internal_power": {"_type": "overwrite[float]", "_units": "watt"},
        }

    def initial_state(self):
        return {"gradient_support": 1.0, "mineral_access": 1.0, "feed": 1.0}

    def update(self, state, interval):
        env = {
            "gradient_support": max(float(state.get("gradient_support", 0.0)), 0.0),
            "mineral_access": max(float(state.get("mineral_access", 0.0)), 0.0),
            "feed": max(float(state.get("feed", 0.0)), 0.0),
        }
        has_pump = self._has_pump
        has_importer = self._has_importer
        has_heredity = self._has_heredity
        eff = float(self.config["catalyst_efficiency"])
        c = self._c

        self._survivors, self._machinery, b = _advance(
            self._survivors, self._machinery, env, has_pump=has_pump,
            has_importer=has_importer, has_heredity=has_heredity,
            catalyst_efficiency=eff, c=c, interval=float(interval))

        scale = c["flux_scale_watt"]
        external = c["k_ext"] * env["gradient_support"]
        internal = (has_pump * self._machinery * c["k_pump"] * eff
                    + has_importer * self._machinery * c["k_imp"])
        return {
            "survivors": self._survivors,
            "lineage_fitness": b["net"],
            "free_energy_flux": max(b["net"], 0.0) * scale,
            "machinery_integrity": self._machinery,
            "external_power": external * scale,
            "internal_power": internal * scale,
        }
