"""Conservation ledger — matter / charge / energy accounting across processes.

Model Upgrade plan, Phase 1 exit criterion: *a validated mass/charge/energy
ledger*; cross-cutting method "numerical verification: convergence,
mass/charge/free-energy residuals, cross-solver comparison — prevent numerical
artifacts from becoming biological conclusions."

:class:`ConservationLedgerProcess` is the first ledger: a Process that sits
beside the world processes of the geochemical world and, every tick, integrates
the source *rates* the serpentinization class publishes and compares the
integral with the *pools* the composite actually accumulated. Because each
process returns additive deltas that process-bigraph applies to the same store,
the two must agree exactly (bit-for-bit: the same floats summed in the same
order) — any gap is a wiring error, a unit error, or a process writing a pool
it should not. It also tracks the worst-case speciation charge imbalance and
spatial flux-divergence residual, and a second-law-style directionality witness
(serpentinization heat released, never absorbed), so a single ``ledger_ok``
flag summarises every conservation invariant the og-00 contract declares
(``mass_balance``, ``charge_neutrality``, ``spatial_flux_conservation``,
``energy_directionality``).

:class:`ChargeLedgerProcess` (Phase 2) is the charge + electron-count ledger
of the electrochemical interface: the anode-side electron rate a
``carbon_fixation`` class publishes must equal the sum of its cathode branches
(carbon products + hydrogen evolution) every tick (``charge_residual``), the
faradaic efficiency recomputed from those rates must never exceed 1, and the
circuit's current-voltage residual is tracked worst-case.

:class:`FreeEnergyLedgerProcess` (Phase 6) is the free-energy ledger of an
individual's power budget: the ``energy_coupling`` class's gross intake, useful
work, dissipation and store must satisfy ``free_energy_in >= work + dissipated``
cumulatively with the store (exact residual, non-negative margin, dissipation
rate never negative, capture efficiency <= 1).

Later phases extend the same pattern (``ledger.{C,N,P}_residual``,
``rewrite_residual`` across structural rewrites) — see the model-upgrade
integration doc.
"""

from __future__ import annotations

import math

from process_bigraph import Process

_MOLAR = {"_type": "float", "_units": "molar"}
_W = {"_type": "float", "_units": "watt"}
_MOLS = {"_type": "float", "_units": "mole/second"}
_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_OVW = {"_type": "overwrite[float]", "_units": "dimensionless"}


class ConservationLedgerProcess(Process):
    """Integrate published source rates and audit them against the accumulated pools."""

    contract = {
        "summary": "Conservation ledger: integrates source rates and audits pools, charge, flux and energy directionality.",
        "description": (
            "Every tick, integrates the H2 / alkalinity / heat source rates the "
            "serpentinization class publishes and compares the running integral with "
            "the pools the composite accumulated (the matter + energy ledger — exact "
            "by construction when every process writes additive deltas to the same "
            "store). Tracks the worst-case PHREEQC charge imbalance and the FVM flux "
            "divergence residual, and a directionality witness (serpentinization heat "
            "is released, never absorbed). ledger_ok = 1 when every residual is below "
            "the configured tolerance."
        ),
        "inputs": {
            "H2": "accumulated dissolved-H2 pool (molar)",
            "alkalinity": "accumulated alkalinity pool (molar)",
            "heat": "accumulated heat pool (W-equivalent)",
            "H2_flux": "instantaneous H2 source rate (mol/s)",
            "alkalinity_flux": "instantaneous alkalinity source rate (mol/s)",
            "heat_flux": "instantaneous heat rate (W)",
            "charge_imbalance": "PHREEQC charge-balance residual (eq/kgw)",
            "flux_divergence_residual": "normalised FVM balance residual",
        },
        "outputs": {
            "H2_in": "integrated H2 source (same units as the pool)",
            "H2_residual": "|pool - integral| / max(integral, eps)",
            "alkalinity_in": "integrated alkalinity source",
            "alkalinity_residual": "|pool - integral| / max(integral, eps)",
            "energy_in": "integrated heat source",
            "energy_residual": "|pool - integral| / max(integral, eps)",
            "charge_residual_max": "worst-case |charge imbalance| so far",
            "flux_residual_max": "worst-case flux-divergence residual so far",
            "energy_directionality": "1 if the heat source has never been negative, else 0",
            "ledger_ok": "1 if every residual is within tolerance, else 0",
        },
        "assumptions": [
            "Every process writing the audited pools returns additive deltas (bare float), "
            "so the pool equals the running integral of the published rates.",
            "The ledger runs at the same interval as the source process, so it reads each "
            "published rate exactly once.",
        ],
    }

    config_schema = {
        "tolerance": {"_type": "float", "_default": 1.0e-9, "_units": "dimensionless",
                      "_provenance": "inferred"},
        "charge_tolerance": {"_type": "float", "_default": 1.0e-6, "_units": "dimensionless",
                             "_provenance": "inferred"},
        "flux_tolerance": {"_type": "float", "_default": 1.0e-3, "_units": "dimensionless",
                           "_provenance": "inferred"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._int = {"H2": 0.0, "alkalinity": 0.0, "heat": 0.0}
        self._charge_max = 0.0
        self._flux_max = 0.0
        self._directional = True

    def inputs(self):
        return {
            "H2": _MOLAR, "alkalinity": _MOLAR, "heat": _W,
            "H2_flux": _MOLS, "alkalinity_flux": _MOLS, "heat_flux": _W,
            "charge_imbalance": _DIMLESS, "flux_divergence_residual": _DIMLESS,
        }

    def outputs(self):
        return {
            "H2_in": {"_type": "overwrite[float]", "_units": "molar"},
            "H2_residual": _OVW,
            "alkalinity_in": {"_type": "overwrite[float]", "_units": "molar"},
            "alkalinity_residual": _OVW,
            "energy_in": {"_type": "overwrite[float]", "_units": "watt"},
            "energy_residual": _OVW,
            "charge_residual_max": _OVW,
            "flux_residual_max": _OVW,
            "energy_directionality": _OVW,
            "ledger_ok": _OVW,
        }

    def initial_state(self):
        return {"H2": 0.0, "alkalinity": 0.0, "heat": 0.0,
                "H2_flux": 0.0, "alkalinity_flux": 0.0, "heat_flux": 0.0,
                "charge_imbalance": 0.0, "flux_divergence_residual": 0.0}

    @staticmethod
    def _rel(pool: float, integral: float) -> float:
        return abs(pool - integral) / max(abs(integral), 1e-30)

    def update(self, state, interval):
        # The rate published in the previous tick was applied to the pool in the
        # same update as it was published, so pool(now) == sum of the rates read
        # so far (including this one) x interval. Integrate the SAME floats in the
        # SAME order process-bigraph added them: the residual is then exactly zero.
        for key in ("H2", "alkalinity", "heat"):
            rate = float(state.get(f"{key}_flux", 0.0))
            self._int[key] += rate * interval
        heat_rate = float(state.get("heat_flux", 0.0))
        if heat_rate < 0.0:
            self._directional = False
        self._charge_max = max(self._charge_max, abs(float(state.get("charge_imbalance", 0.0))))
        self._flux_max = max(self._flux_max, abs(float(state.get("flux_divergence_residual", 0.0))))

        res_h2 = self._rel(float(state.get("H2", 0.0)), self._int["H2"])
        res_alk = self._rel(float(state.get("alkalinity", 0.0)), self._int["alkalinity"])
        res_e = self._rel(float(state.get("heat", 0.0)), self._int["heat"])
        tol = float(self.config["tolerance"])
        ok = (res_h2 <= tol and res_alk <= tol and res_e <= tol
              and self._charge_max <= float(self.config["charge_tolerance"])
              and self._flux_max <= float(self.config["flux_tolerance"])
              and self._directional)
        return {
            "H2_in": self._int["H2"], "H2_residual": res_h2,
            "alkalinity_in": self._int["alkalinity"], "alkalinity_residual": res_alk,
            "energy_in": self._int["heat"], "energy_residual": res_e,
            "charge_residual_max": self._charge_max,
            "flux_residual_max": self._flux_max,
            "energy_directionality": 1.0 if self._directional else 0.0,
            "ledger_ok": 1.0 if ok else 0.0,
        }


class ChargeLedgerProcess(Process):
    """Charge + electron-count ledger for the electrochemical interface (Phase 2).

    Sits beside a ``carbon_fixation`` class and audits, every tick, the three
    electron rates it publishes: the anode-side rate (``electron_flux``, the
    current through the mineral) against the two cathode branches
    (``carbon_electron_flux`` into formate / acetate / pyruvate and
    ``her_electron_flux`` into hydrogen evolution). Kirchhoff's node law makes
    ``charge_residual = |anode - (carbon + her)| / anode`` zero for a correctly
    wired class; the faradaic efficiency is recomputed as ``carbon / anode`` and
    must never exceed 1; the circuit's current-voltage residual (published by
    the Butler-Volmer class at its solved operating point) is tracked worst-case.
    Integrates the charge passed (coulomb) and the electrons delivered to carbon
    (mole) for the report, and publishes ``charge_ledger_ok``.
    """

    contract = {
        "summary": "Charge + electron ledger: Kirchhoff residual per tick, faradaic efficiency <= 1, current-voltage residual.",
        "description": (
            "Every tick compares the anode-side electron rate a carbon-fixation class publishes "
            "with the sum of its cathode branches (carbon products + hydrogen evolution): "
            "charge_residual = |anode - (carbon + her)| / anode. Recomputes the faradaic "
            "efficiency as carbon / anode and tracks that it never exceeds 1, tracks the "
            "worst-case circuit (current-voltage) residual, integrates the charge passed and the "
            "electrons delivered to carbon, and publishes charge_ledger_ok = 1 while every "
            "residual is inside tolerance."
        ),
        "inputs": {
            "electron_flux": "anode-side electron rate = current / F (mole/second)",
            "carbon_electron_flux": "electrons into carbon products (mole/second)",
            "her_electron_flux": "electrons into hydrogen evolution (mole/second)",
            "iv_residual": "circuit residual at the solved current (dimensionless)",
        },
        "outputs": {
            "charge_residual": "|anode - (carbon + her)| / max(anode, eps) this tick",
            "charge_residual_max": "worst-case charge residual so far",
            "faradaic_efficiency": "carbon / anode this tick (0 when no current)",
            "faradaic_efficiency_max": "worst-case faradaic efficiency so far (must be <= 1)",
            "iv_residual_max": "worst-case current-voltage residual so far",
            "charge_passed": "integrated anode charge (coulomb)",
            "electrons_to_carbon": "integrated electrons into carbon products (mole)",
            "charge_ledger_ok": "1 while every residual is within tolerance and FE <= 1",
        },
        "assumptions": ["The class publishes the three electron rates from the same solved operating point."],
        "math": ["charge_residual = |e_anode - (e_carbon + e_her)| / e_anode", "FE = e_carbon / e_anode <= 1"],
    }

    config_schema = {
        "tolerance": {"_type": "float", "_default": 1.0e-9, "_units": "dimensionless", "_provenance": "inferred"},
        "iv_tolerance": {"_type": "float", "_default": 1.0e-6, "_units": "dimensionless", "_provenance": "inferred"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._charge = 0.0
        self._carbon = 0.0
        self._res_max = 0.0
        self._fe_max = 0.0
        self._iv_max = 0.0

    def inputs(self):
        return {"electron_flux": _MOLS, "carbon_electron_flux": _MOLS, "her_electron_flux": _MOLS,
                "iv_residual": _DIMLESS}

    def outputs(self):
        return {
            "charge_residual": _OVW, "charge_residual_max": _OVW,
            "faradaic_efficiency": _OVW, "faradaic_efficiency_max": _OVW, "iv_residual_max": _OVW,
            "charge_passed": {"_type": "overwrite[float]", "_units": "coulomb"},
            "electrons_to_carbon": {"_type": "overwrite[float]", "_units": "mole"},
            "charge_ledger_ok": _OVW,
        }

    def initial_state(self):
        return {"electron_flux": 0.0, "carbon_electron_flux": 0.0, "her_electron_flux": 0.0, "iv_residual": 0.0}

    def update(self, state, interval):
        e_anode = float(state.get("electron_flux", 0.0))
        e_carbon = float(state.get("carbon_electron_flux", 0.0))
        e_her = float(state.get("her_electron_flux", 0.0))
        iv = abs(float(state.get("iv_residual", 0.0)))
        residual = abs(e_anode - (e_carbon + e_her)) / max(abs(e_anode), 1e-30) if e_anode != 0.0 else abs(e_carbon + e_her)
        fe = (e_carbon / e_anode) if e_anode > 0.0 else 0.0
        self._charge += 96485.33212 * e_anode * interval
        self._carbon += e_carbon * interval
        self._res_max = max(self._res_max, residual)
        self._fe_max = max(self._fe_max, fe)
        self._iv_max = max(self._iv_max, iv)
        ok = (self._res_max <= float(self.config["tolerance"])
              and self._fe_max <= 1.0 + 1e-12
              and self._iv_max <= float(self.config["iv_tolerance"]))
        return {
            "charge_residual": residual, "charge_residual_max": self._res_max,
            "faradaic_efficiency": fe, "faradaic_efficiency_max": self._fe_max,
            "iv_residual_max": self._iv_max, "charge_passed": self._charge,
            "electrons_to_carbon": self._carbon, "charge_ledger_ok": 1.0 if ok else 0.0,
        }


class RewriteLedgerProcess(Process):
    """Conservation audit for the Phase-5 structural rewrites (``_add`` /
    ``_divide`` / ``_remove``) on the ``agents`` map (FMP §5.3).

    Tracks the total matter (summed ``internal_amounts``) in the
    (agents + localized) system. Boundary formation moves matter localized→agent
    and division is agent-internal, so both leave the system total invariant;
    lysis/extinction remove an individual's matter (a reported outflow). Hence
    ``rewrite_residual = |Δtotal + removed_matter|`` must stay ~0 across every
    rewrite. ``partition_residual`` (the daughters' amounts summing to the
    mother's on ``_divide``) is passed through from :class:`DivisionStep`. The
    single ``rewrite_ok`` flag is the Phase-5 exit criterion's conservation gate."""

    config_schema = {
        "tol": {"_type": "float", "_default": 1.0e-9, "_provenance": "inferred"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config, core)
        self._prev_total = None
        self._rewrite_max = 0.0
        self._partition_max = 0.0

    def inputs(self):
        return {"agents": "map[vg_individual]", "localized": "map[vg_amount]",
                "partition_residual": "float", "removed_matter": "float"}

    def outputs(self):
        return {
            "rewrite_residual": "overwrite[float]",
            "rewrite_residual_max": "overwrite[float]",
            "partition_residual_max": "overwrite[float]",
            "agent_matter": "overwrite[float]",
            "n_agents": "overwrite[float]",
            "rewrite_ok": "overwrite[float]",
        }

    @staticmethod
    def _matter(agents):
        return sum(sum(float(v) for v in (a.get("internal_amounts", {}) or {}).values())
                   for a in agents.values())

    def update(self, state, interval):
        agents = state.get("agents", {}) or {}
        localized = state.get("localized", {}) or {}
        agent_matter = self._matter(agents)
        total = agent_matter + sum(float(v) for v in localized.values())
        removed = float(state.get("removed_matter", 0.0))
        part = float(state.get("partition_residual", 0.0))
        if self._prev_total is None:
            rewrite_resid = 0.0
        else:
            rewrite_resid = abs(total - (self._prev_total - removed))
        self._prev_total = total
        self._rewrite_max = max(self._rewrite_max, rewrite_resid)
        self._partition_max = max(self._partition_max, part)
        tol = float(self.config["tol"])
        ok = 1.0 if (self._rewrite_max <= tol and self._partition_max <= tol) else 0.0
        return {
            "rewrite_residual": rewrite_resid,
            "rewrite_residual_max": self._rewrite_max,
            "partition_residual_max": self._partition_max,
            "agent_matter": agent_matter,
            "n_agents": float(len(agents)),
            "rewrite_ok": ok,
        }


REWRITE_LEDGER_KEYS = ("rewrite_residual", "rewrite_residual_max",
                       "partition_residual_max", "agent_matter", "n_agents",
                       "rewrite_ok")


def rewrite_ledger_summary(rows) -> dict:
    """Reduce an emitter row list to the final rewrite-ledger state (worst-case)."""
    if not rows:
        return {k: float("nan") for k in REWRITE_LEDGER_KEYS}
    last = rows[-1]
    out = {k: float(last.get(k, float("nan"))) for k in REWRITE_LEDGER_KEYS}
    out["rewrite_residual_max"] = max(float(r.get("rewrite_residual", 0.0)) for r in rows)
    out["partition_residual_max"] = max(float(r.get("partition_residual_max", 0.0)) for r in rows)
    return out


CHARGE_LEDGER_KEYS = ("charge_residual", "charge_residual_max", "faradaic_efficiency",
                      "faradaic_efficiency_max", "iv_residual_max", "charge_passed",
                      "electrons_to_carbon", "charge_ledger_ok")

LEDGER_KEYS = ("H2_in", "H2_residual", "alkalinity_in", "alkalinity_residual",
               "energy_in", "energy_residual", "charge_residual_max",
               "flux_residual_max", "energy_directionality", "ledger_ok")


def ledger_summary(rows) -> dict:
    """Reduce an emitter row list to the final ledger state (worst-case residuals)."""
    if not rows:
        return {k: float("nan") for k in LEDGER_KEYS}
    last = rows[-1]
    out = {k: float(last.get(k, float("nan"))) for k in LEDGER_KEYS}
    out["max_mass_residual"] = max(
        float(r.get("H2_residual", 0.0)) for r in rows) if rows else float("nan")
    out["max_energy_residual"] = max(
        float(r.get("energy_residual", 0.0)) for r in rows) if rows else float("nan")
    return out


class NetworkLedgerProcess(Process):
    """Element + free-energy ledger over an open chemical network (Phase 3).

    Sits beside a ``proto_metabolism`` class and audits, every tick, the three
    witnesses the class publishes:

    * ``element_residual`` — ``max |E S|`` over the network's internal
      reactions (exact algebra, independent of the integrator): a generated
      universe is balanced by construction; a lumped reaction such as og-02's
      ``OAA + 2 CO2 -> 2 OAA + acetate`` or a rewired null is not, and the
      ledger says so.
    * ``carbon_residual`` — the integrated carbon balance
      ``|TOC - TOC0 - (fed + fixed - washed - degraded)| / TOC``, which must stay
      at the integrator's tolerance.
    * ``dissipation`` — ``-Σ v_r ΔG_r`` over internal reactions; the second
      law requires it to be non-negative every tick (free-energy
      directionality). ``free_energy_in >= work + dissipated`` of the roadmap
      reduces, for a reactor with no work output, to this inequality.

    Publishes the worst-case residuals so far, the directionality witness and
    one ``ledger_ok`` flag, mirroring :class:`ConservationLedgerProcess`.
    """

    contract = {
        "summary": "Element + free-energy ledger over an open reaction network: stoichiometric element residual, integrated carbon balance, dissipation >= 0.",
        "description": (
            "Audits the witnesses a proto_metabolism class publishes each tick: the exact "
            "stoichiometric element residual max|E S| (0 for a rule-generated universe; non-zero "
            "exposes lumped or rewired reactions that create or destroy atoms), the integrated "
            "carbon-balance residual (must sit at integrator tolerance) and the free-energy "
            "dissipation -sum v dG (second law: never negative). ledger_ok = 1 while every "
            "witness is within tolerance."
        ),
        "inputs": {
            "element_residual": "max |E S| over internal reactions (atoms)",
            "carbon_residual": "relative integrated carbon-balance residual",
            "dissipation": "-sum_r v_r dG_r (watt)",
            "total_organic_carbon": "organic carbon pool (molar C)",
        },
        "outputs": {
            "element_residual_max": "worst-case element residual so far",
            "carbon_residual_max": "worst-case carbon-balance residual so far",
            "dissipation_min": "minimum dissipation seen (negative = second-law violation)",
            "dissipated_energy": "time-integral of the dissipation (joule)",
            "free_energy_directionality": "1 if dissipation has never been below -tolerance",
            "ledger_ok": "1 if every witness is within tolerance",
        },
        "assumptions": ["The network class computes the witnesses from its own stoichiometry and live rates; "
                        "the ledger only accumulates and grades them."],
    }

    config_schema = {
        "element_tolerance": {"_type": "float", "_default": 1.0e-9, "_units": "dimensionless",
                              "_provenance": "inferred"},
        "carbon_tolerance": {"_type": "float", "_default": 1.0e-4, "_units": "dimensionless",
                             "_provenance": "inferred"},
        "dissipation_tolerance": {"_type": "float", "_default": 1.0e-12, "_units": "watt",
                                  "_provenance": "inferred"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._el_max = 0.0
        self._c_max = 0.0
        self._diss_min = float("inf")
        self._diss_int = 0.0
        self._directional = True

    def inputs(self):
        return {"element_residual": _DIMLESS, "carbon_residual": _DIMLESS, "dissipation": _W,
                "total_organic_carbon": _MOLAR}

    def outputs(self):
        return {"element_residual_max": _OVW, "carbon_residual_max": _OVW,
                "dissipation_min": {"_type": "overwrite[float]", "_units": "watt"},
                "dissipated_energy": {"_type": "overwrite[float]", "_units": "joule"},
                "free_energy_directionality": _OVW, "ledger_ok": _OVW}

    def initial_state(self):
        return {"element_residual": 0.0, "carbon_residual": 0.0, "dissipation": 0.0,
                "total_organic_carbon": 0.0}

    def update(self, state, interval):
        el = abs(float(state.get("element_residual", 0.0)))
        cr = abs(float(state.get("carbon_residual", 0.0)))
        d = float(state.get("dissipation", 0.0))
        self._el_max = max(self._el_max, el)
        self._c_max = max(self._c_max, cr)
        self._diss_min = min(self._diss_min, d)
        self._diss_int += d * float(interval)
        if d < -float(self.config["dissipation_tolerance"]):
            self._directional = False
        ok = (self._el_max <= float(self.config["element_tolerance"])
              and self._c_max <= float(self.config["carbon_tolerance"]) and self._directional)
        return {"element_residual_max": self._el_max, "carbon_residual_max": self._c_max,
                "dissipation_min": self._diss_min if math.isfinite(self._diss_min) else 0.0,
                "dissipated_energy": self._diss_int,
                "free_energy_directionality": 1.0 if self._directional else 0.0,
                "ledger_ok": 1.0 if ok else 0.0}


NETWORK_LEDGER_KEYS = ("element_residual_max", "carbon_residual_max", "dissipation_min",
                       "dissipated_energy", "free_energy_directionality", "ledger_ok")


class FreeEnergyLedgerProcess(Process):
    """Free-energy ledger of an individual's power budget (Phase 6).

    Sits beside an ``energy_coupling`` class and audits, every tick, the four
    witnesses it publishes — ``free_energy_in`` (W, gross free energy drawn
    from the environment), ``work`` (W, useful work delivered), ``dissipated``
    (W) and ``energy_stored`` (J, the internal store) — against the roadmap's
    invariant

        free_energy_in  >=  work + dissipated

    taken cumulatively WITH the store: integrating the rates, ``in_cum + E(0)
    - work_cum - diss_cum = E(t)`` must hold exactly (``free_energy_residual``
    at rounding) and ``E(t) >= 0`` makes the inequality (``second_law_margin``
    = ``in_cum + E0 - work_cum - diss_cum`` never negative). Per tick the
    dissipation rate must never be negative (the directionality witness, as
    :class:`NetworkLedgerProcess`) and the capture efficiency ``work_cum /
    in_cum`` must never exceed 1. Publishes the worst cases so far and one
    ``free_energy_ledger_ok`` flag.
    """

    contract = {
        "summary": "Free-energy ledger of a protocell's power budget: free_energy_in >= work + dissipated (with the store), exact residual, dissipation >= 0, efficiency <= 1.",
        "description": (
            "Integrates the gross free-energy intake, the useful work and the dissipation an energy_coupling "
            "class publishes and compares them with the store it reports: in_cum + E0 - work_cum - diss_cum "
            "must equal E(t) to rounding (free_energy_residual) and never go negative (second_law_margin); "
            "the per-tick dissipation rate must be >= -tolerance and work_cum / in_cum <= 1. "
            "free_energy_ledger_ok = 1 while every witness holds."
        ),
        "inputs": {
            "free_energy_in": "gross free energy drawn from the environment (watt)",
            "work": "useful work delivered (watt)",
            "dissipated": "free energy dissipated (watt)",
            "energy_stored": "free energy held in the internal store (joule)",
        },
        "outputs": {
            "free_energy_in_total": "integrated intake (joule)",
            "work_total": "integrated useful work (joule)",
            "dissipated_total": "integrated dissipation (joule)",
            "free_energy_residual": "|in_cum + E0 - work_cum - diss_cum - E(t)| / max(in_cum, eps) this tick",
            "free_energy_residual_max": "worst-case residual so far",
            "second_law_margin": "in_cum + E0 - work_cum - diss_cum (joule; must stay >= 0)",
            "second_law_margin_min": "minimum margin so far",
            "dissipation_min": "minimum per-tick dissipation rate seen (negative = violation)",
            "capture_efficiency": "work_cum / in_cum (must be <= 1)",
            "free_energy_ledger_ok": "1 while every witness is within tolerance",
        },
        "assumptions": ["The class publishes the four witnesses from the same tick; the ledger only integrates and grades."],
        "math": ["in_cum + E0 - work_cum - diss_cum = E(t)", "free_energy_in >= work + dissipated  <=>  E(t) >= 0"],
    }

    config_schema = {
        "tolerance": {"_type": "float", "_default": 1.0e-9, "_units": "dimensionless", "_provenance": "inferred"},
        "dissipation_tolerance": {"_type": "float", "_default": 1.0e-30, "_units": "watt", "_provenance": "inferred"},
        "seconds_per_tick": {"_type": "float", "_default": 1.0, "_units": "second", "_provenance": "inferred"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._in = 0.0
        self._work = 0.0
        self._diss = 0.0
        self._e0 = None
        self._res_max = 0.0
        self._margin_min = float("inf")
        self._diss_min = float("inf")
        self._eff_max = 0.0

    def inputs(self):
        return {"free_energy_in": _W, "work": _W, "dissipated": _W,
                "energy_stored": {"_type": "float", "_units": "joule"}}

    def outputs(self):
        return {"free_energy_in_total": {"_type": "overwrite[float]", "_units": "joule"},
                "work_total": {"_type": "overwrite[float]", "_units": "joule"},
                "dissipated_total": {"_type": "overwrite[float]", "_units": "joule"},
                "free_energy_residual": _OVW, "free_energy_residual_max": _OVW,
                "second_law_margin": {"_type": "overwrite[float]", "_units": "joule"},
                "second_law_margin_min": {"_type": "overwrite[float]", "_units": "joule"},
                "dissipation_min": {"_type": "overwrite[float]", "_units": "watt"},
                "capture_efficiency": _OVW, "free_energy_ledger_ok": _OVW}

    def initial_state(self):
        return {"free_energy_in": 0.0, "work": 0.0, "dissipated": 0.0, "energy_stored": 0.0}

    def update(self, state, interval):
        dt = float(interval) * float(self.config["seconds_per_tick"])
        fin = float(state.get("free_energy_in", 0.0))
        w = float(state.get("work", 0.0))
        d = float(state.get("dissipated", 0.0))
        e = float(state.get("energy_stored", 0.0))
        if self._e0 is None:
            # The witnesses read this tick were produced from the store level BEFORE
            # this tick's update; the first read fixes E0 as that level minus the
            # first net gain, so the identity holds from tick one.
            self._e0 = e - (fin - w - d) * dt
        self._in += fin * dt
        self._work += w * dt
        self._diss += d * dt
        margin = self._in + self._e0 - self._work - self._diss
        residual = abs(margin - e) / max(abs(self._in), 1e-30)
        eff = (self._work / self._in) if self._in > 0.0 else 0.0
        self._res_max = max(self._res_max, residual)
        self._margin_min = min(self._margin_min, margin)
        self._diss_min = min(self._diss_min, d)
        self._eff_max = max(self._eff_max, eff)
        tol = float(self.config["tolerance"])
        ok = (self._res_max <= tol
              and self._margin_min >= -tol * max(abs(self._in), 1e-30)
              and self._diss_min >= -float(self.config["dissipation_tolerance"])
              and self._eff_max <= 1.0 + 1e-12)
        return {"free_energy_in_total": self._in, "work_total": self._work, "dissipated_total": self._diss,
                "free_energy_residual": residual, "free_energy_residual_max": self._res_max,
                "second_law_margin": margin,
                "second_law_margin_min": self._margin_min if math.isfinite(self._margin_min) else 0.0,
                "dissipation_min": self._diss_min if math.isfinite(self._diss_min) else 0.0,
                "capture_efficiency": eff, "free_energy_ledger_ok": 1.0 if ok else 0.0}


FREE_ENERGY_LEDGER_KEYS = ("free_energy_in_total", "work_total", "dissipated_total", "free_energy_residual",
                           "free_energy_residual_max", "second_law_margin", "second_law_margin_min",
                           "dissipation_min", "capture_efficiency", "free_energy_ledger_ok")


__all__ = ["ConservationLedgerProcess", "ChargeLedgerProcess", "NetworkLedgerProcess",
           "RewriteLedgerProcess", "FreeEnergyLedgerProcess",
           "LEDGER_KEYS", "CHARGE_LEDGER_KEYS", "NETWORK_LEDGER_KEYS", "REWRITE_LEDGER_KEYS",
           "FREE_ENERGY_LEDGER_KEYS", "ledger_summary", "rewrite_ledger_summary"]
