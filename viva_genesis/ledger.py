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

Later phases extend the same pattern (``ledger.{C,N,P}_residual``,
``rewrite_residual`` across structural rewrites, ``free_energy_in >= work +
dissipated``) — see the model-upgrade integration doc.
"""

from __future__ import annotations

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


__all__ = ["ConservationLedgerProcess", "ChargeLedgerProcess", "LEDGER_KEYS", "CHARGE_LEDGER_KEYS",
           "ledger_summary"]
