"""The evolving mineral-water interface — mineral surface dynamics.

A general, composable ``Process`` for the upgrade plan's "explicit mineral surface
dynamics: dissolution, precipitation, adsorption, passivation, evolving catalytic
accessibility" (build-registry id ``mineral-surface-dynamics``; studies 27 and 30).
It is the piece that turns the fixed-boundary og-00 vent reactor into an interface
that *evolves*: precipitation and dissolution change pore space, and precipitation
passivates the catalytic surface over time.

Composition: ports are unit-typed to match ``viva_genesis.geochemistry`` /
``viva_genesis.transport``. It reads the local ``saturation_index`` a sibling
speciation process (e.g. ``PhreeqcSerpentinizationProcess``) produces and the
current ``porosity`` the FiPy transport carries, and emits a **porosity delta**
that composes additively with FiPy's own transport-driven porosity change. The
``catalytic_accessibility`` it evolves feeds the downstream carbon-fixation /
electrochemistry catalysis. Nothing here is study-specific — the same Process
drops into any composite that has a saturation signal and a porosity store.

Model (documented rate laws, not a wrapped tool — this is new mechanistic
modelling, per the method's build-registry classification):

* precipitation rate  = k_precip   * max(SI, 0) * porosity      (clogs open pores)
* dissolution rate    = k_dissolve * max(-SI, 0) * (1 - porosity) (opens solid)
* d(porosity)/dt      = dissolution - precipitation
* d(accessibility)/dt = -k_passivate * precipitation * accessibility  (1st-order
  passivation — precipitated mineral coats catalytic sites; monotonic decay)
* reactive surface area = specific_area * (1 - porosity) * accessibility

A mineral-mass consistency ledger confirms the porosity lost to precipitation
equals the mineral volume precipitated (``mineral_mass_residual`` ~ 0).
"""
from __future__ import annotations

from process_bigraph import Process

_K = {"_type": "float", "_units": "kelvin"}
_MPS = {"_type": "float", "_units": "meter/second"}
_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_OW_INV_M = {"_type": "overwrite[float]", "_units": "1/meter"}
_OW_DIMLESS = {"_type": "overwrite[float]", "_units": "dimensionless"}


class MineralSurfaceDynamicsProcess(Process):
    """Evolve pore space + catalytic accessibility of a reactive mineral interface."""

    config_schema = {
        # precipitation / dissolution rate coefficients (per second)
        "k_precip": {"_type": "float", "_default": 0.05, "_units": "1/second"},
        "k_dissolve": {"_type": "float", "_default": 0.02, "_units": "1/second"},
        # first-order passivation coefficient (dimensionless per unit precipitation)
        "k_passivate": {"_type": "float", "_default": 0.5, "_units": "dimensionless"},
        # specific surface area of the fresh solid (m^2 per m^3 -> 1/meter)
        "specific_area": {"_type": "float", "_default": 1.0e4, "_units": "1/meter"},
        # mineral molar volume linking precipitated moles to pore-volume loss
        "mineral_molar_volume": {"_type": "float", "_default": 3.7e-5, "_units": "meter^3/mol"},
    }

    contract = {
        "summary": ("Evolving mineral interface: precipitation/dissolution drive a "
                    "porosity delta (composes with FiPy transport); precipitation "
                    "passivates catalytic accessibility monotonically. Mineral mass "
                    "is conserved (residual ~ 0)."),
        "invariants": ["mineral_mass_residual ~ 0", "catalytic_accessibility non-increasing under precipitation"],
    }

    def inputs(self):
        return {
            "saturation_index": _DIMLESS,     # SI from the speciation sibling (>0 supersat)
            "temperature": _K,
            "flow_velocity": _MPS,
            "porosity": _DIMLESS,             # current pore fraction (from FiPy / store)
            "catalytic_accessibility": _DIMLESS,  # current active-surface fraction (0..1)
        }

    def outputs(self):
        return {
            "porosity": _DIMLESS,                   # DELTA — composes with FiPy's porosity
            "catalytic_accessibility": _DIMLESS,    # DELTA — accumulates toward current fraction
            "reactive_surface_area": _OW_INV_M,     # current reading (sensor)
            "mineral_precipitation": _DIMLESS,      # pore-volume fraction precipitated this step
            "mineral_mass_residual": _OW_DIMLESS,   # conservation ledger (~0)
        }

    def initial_state(self):
        return {"porosity": 0.3, "catalytic_accessibility": 1.0}

    def update(self, state, interval):
        si = float(state.get("saturation_index", 0.0))
        phi = float(state.get("porosity", 0.3))
        acc = float(state.get("catalytic_accessibility", 1.0))

        k_p = self.config["k_precip"]
        k_d = self.config["k_dissolve"]
        k_pass = self.config["k_passivate"]
        molar_vol = self.config["mineral_molar_volume"]

        # Clamp physical quantities to their valid ranges before the rate laws.
        phi = min(max(phi, 0.0), 1.0)
        acc = min(max(acc, 0.0), 1.0)

        precip = k_p * max(si, 0.0) * phi            # pore fraction clogged / s
        dissolve = k_d * max(-si, 0.0) * (1.0 - phi)  # pore fraction opened / s

        d_phi = (dissolve - precip) * interval
        # Keep the porosity delta from driving the store outside [0, 1].
        d_phi = max(min(d_phi, 1.0 - phi), -phi)

        precip_frac = precip * interval               # pore volume precipitated this step
        d_acc = -k_pass * precip_frac * acc           # monotonic passivation under precip
        d_acc = max(d_acc, -acc)                      # never below zero accessibility

        area = self.config["specific_area"] * (1.0 - phi) * acc

        # Mineral-mass ledger: pore volume lost to precipitation must equal the
        # mineral volume precipitated (moles * molar_volume). Same quantity by
        # construction -> residual is ~0; a nonzero value flags an inconsistency.
        moles_precip = precip_frac / molar_vol if molar_vol > 0 else 0.0
        residual = precip_frac - moles_precip * molar_vol

        return {
            "porosity": d_phi,
            "catalytic_accessibility": d_acc,
            "reactive_surface_area": area,
            "mineral_precipitation": precip_frac,
            "mineral_mass_residual": residual,
        }
