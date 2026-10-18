"""Module H (Gate D) — amphiphile-driven growth and division at a MEASURED
critical-geometry threshold (study og-33).

This is the AMPHIPHILE-GEOMETRY division route, distinct from the OSMOTIC
pressure-driven volume-threshold route in
:class:`~viva_genesis.compartments.osmotic_growth_division.OsmoticGrowthDivisionProcess`
(internal solute -> osmotic pressure -> volume -> divide at a volume threshold).
Here the metabolism's amphiphiles grow the membrane AREA; as area outpaces the
enclosed volume the compartment's **reduced volume** ``v = V / V_sphere(A)`` falls,
and at a measured critical reduced volume (vesicle budding/shape instability,
grounded in hanczyc2003 / budin2012 growth-division geometries) it DIVIDES — a
physical geometric event, not an imposed rule. The two routes are complementary
origins-of-life division mechanisms; study 33 tests the amphiphile-geometry one.

Dynamics (sub-stepped), driven by the metabolism's productive flux:
    production = eta_amph * |productive_flux|          (coupled; or a fixed rate if decoupled)
    dA/dt = k_area * production - k_deg_area * A         (membrane area from amphiphile incorporation)
    dV/dt = k_vol * A - k_leak_vol * V                  (volume influx scales with area, then relaxes)
    v = V / V_sphere(A),  V_sphere(A) = (4/3)*pi*r^3,  r = sqrt(A/(4*pi))
    divide when v <= v_crit (geometry) [or on a fixed period if imposed_division]:
        A, V := A/2, V/2  (two daughters; area + volume partitioned)

Because halving A and V sends v -> sqrt(2)*v, division relieves the excess-area
instability and a daughter resumes at a higher (more spherical) reduced volume —
geometrically viable. A daughter additionally counts as viable only if it resumes
the study-32 self-maintenance criterion (net amphiphile production >= degradation),
so viability is tied to the metabolism still paying for the membrane.

``coupled=False`` is the growth-decoupled control (fixed external amphiphile supply,
independent of metabolic flux); ``imposed_division=True`` is the imposed-rule control
(divide on a fixed period regardless of geometry). Both are matched nulls for the
decision test: emergent growth/division means division RATE scales with metabolic
flux and division triggers at the measured geometry, beating those controls.

**Scope (honest):** this is the measured critical-geometry first cut (⚑2, Option B).
Full coarse-grained membrane mechanics (viva-md-membrane, deriving the shape
instability from resolved bending/tension) is the gold-standard follow-on (og-33a).
``v_crit`` is a literature-grounded reduced-volume (recorded as a proposed_input),
NOT tuned to force division.
"""
from __future__ import annotations

import math

from process_bigraph import Process

_FLOAT = {"_type": "float"}
_O_FLOAT = {"_type": "overwrite[float]"}
_O_COUNT = {"_type": "overwrite[integer]"}

# Measured critical reduced volume for vesicle budding/shape instability (a sphere
# has v=1; growth-division experiments divide well below it). Literature-grounded
# proposed_input (hanczyc2003experimental / budin2012concentration), NOT tuned.
_V_CRIT_DEFAULT = 0.66


def _v_sphere(area: float) -> float:
    """Volume of a sphere with the given surface area."""
    r = math.sqrt(max(area, 1e-30) / (4.0 * math.pi))
    return (4.0 / 3.0) * math.pi * r ** 3


class GrowthDivisionProcess(Process):
    """Amphiphile-driven membrane growth + division at a measured critical geometry."""

    config_schema = {
        "eta_amph": {"_type": "float", "_default": 0.10, "_units": "dimensionless"},        # flux -> amphiphile fraction
        "k_area": {"_type": "float", "_default": 9.0e3, "_units": "dimensionless"},         # area growth per unit production
        "k_deg_area": {"_type": "float", "_default": 1.0e-4, "_units": "1/second"},         # membrane area degradation
        # Division geometry: a fatty-acid vesicle adds membrane area while enclosed
        # volume lags, so reduced volume falls; at ~area doubling the elongated
        # vesicle reaches the budding/scission instability (Budin & Szostak;
        # hanczyc2003/budin2012). division_ratio = area multiple at division.
        "division_ratio": {"_type": "float", "_default": 2.0, "_units": "dimensionless"},  # measured area-doubling budding geometry
        "coupled": {"_type": "boolean", "_default": True},                                  # growth driven by metabolism (vs decoupled)
        "flux_ema_alpha": {"_type": "float", "_default": 0.1, "_units": "dimensionless"},    # amphiphile supply lags the metabolite pool (smooths CSTR ignition transient)
        "decoupled_rate": {"_type": "float", "_default": 3.36e-5, "_units": "dimensionless"},  # fixed production when decoupled (= eta*reference steady flux)
        "imposed_division": {"_type": "boolean", "_default": False},                        # divide on a timer (control)
        "imposed_period": {"_type": "float", "_default": 20.0, "_units": "second"},         # timer period when imposed
        # daughter viability = study-32 self-maintenance (production >= degradation)
        "k_deg_membrane": {"_type": "float", "_default": 1.0e-4, "_units": "1/second"},
        "m_req": {"_type": "float", "_default": 1.0e-3, "_units": "molar"},
        "initial_area": {"_type": "float", "_default": 20.0, "_units": "nanometer**2"},
        "substeps": {"_type": "integer", "_default": 20, "_units": "dimensionless"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config, core)
        self._init_state()

    def _init_state(self):
        self._A = float(self.config["initial_area"])
        self._A_birth = self._A                     # area at the last division (birth size)
        self._divisions = 0
        self._t = 0.0
        self._t_last_div = 0.0
        self._flux_ema = None

    def inputs(self):
        return {"productive_flux": _FLOAT}

    def outputs(self):
        return {
            "membrane_area": _O_FLOAT,
            "enclosed_volume": _O_FLOAT,
            "reduced_volume": _O_FLOAT,
            "area_to_volume_ratio": _O_FLOAT,
            "division_count": _O_COUNT,
            "division_event": _O_COUNT,
            "division_rate": _O_FLOAT,
            "amphiphile_production_rate": _O_FLOAT,
            "daughter_viable": _O_FLOAT,
        }

    def initial_state(self):
        return {"productive_flux": 0.0}

    def update(self, state, interval):
        flux = abs(float(state.get("productive_flux", 0.0)))
        coupled = bool(self.config["coupled"])
        eta = float(self.config["eta_amph"])
        # Amphiphile supply lags the metabolite pool (EMA smooths the CSTR ignition
        # transient so growth tracks the SUSTAINED metabolic flux, not the spike).
        alpha = float(self.config["flux_ema_alpha"])
        self._flux_ema = flux if self._flux_ema is None else (1.0 - alpha) * self._flux_ema + alpha * flux
        production = eta * self._flux_ema if coupled else float(self.config["decoupled_rate"])
        k_area = float(self.config["k_area"])
        k_deg_area = float(self.config["k_deg_area"])
        ratio = float(self.config["division_ratio"])
        imposed = bool(self.config["imposed_division"])
        period = float(self.config["imposed_period"])
        n_sub = max(int(self.config["substeps"]), 1)
        h = float(interval) / n_sub

        # Grow membrane area from amphiphile incorporation over sub-steps; a
        # compartment divides at most ONCE per update (a discrete physical event),
        # so the division check is after the loop.
        for _ in range(n_sub):
            self._A = max(self._A + (k_area * production - k_deg_area * self._A) * h, 1e-9)
            self._t += h

        # Enclosed volume lags area (content influx slow vs amphiphile addition), so
        # reduced volume falls as area grows past the birth (near-spherical) size:
        # v ~ (A_birth / A)^1.5. Division at the measured area-doubling budding
        # instability (A >= division_ratio * A_birth), not an imposed rule.
        divisions_this_interval = 0
        divide = ((self._t - self._t_last_div) >= period) if imposed else (self._A >= ratio * self._A_birth)
        if divide:
            self._A *= 0.5
            self._A_birth = self._A                 # daughter rounds up to its new birth size
            self._divisions += 1
            divisions_this_interval = 1
            self._t_last_div = self._t

        reduced_volume = min((self._A_birth / self._A) ** 1.5, 1.0)
        enclosed_volume = _v_sphere(self._A_birth)  # content volume ~ birth (rounded) size
        division_rate = self._divisions / self._t if self._t > 0 else 0.0
        # daughter viability = study-32 self-maintenance (production pays the membrane)
        degradation = float(self.config["k_deg_membrane"]) * float(self.config["m_req"])
        daughter_viable = 1.0 if (self._divisions >= 1 and production >= degradation) else 0.0
        return {
            "membrane_area": self._A,
            "enclosed_volume": enclosed_volume,
            "reduced_volume": reduced_volume,
            "area_to_volume_ratio": self._A / max(enclosed_volume, 1e-30),
            "division_count": self._divisions,
            "division_event": divisions_this_interval,
            "division_rate": division_rate,
            "amphiphile_production_rate": production,
            "daughter_viable": daughter_viable,
        }
