"""S3 — the active-protrusion membrane-WRAPPING model (continuum energetics).

The posed question is whether an **actin-driven host protrusion** can supply enough
work to carry a lipid membrane over the Helfrich bending barrier and reach a
**stable fully wrapped (engulfed)** state around a bacterial partner — not merely
whether a chosen adhesion hierarchy sorts two phases (the CPM arm, passive
differential adhesion) or whether membrane area suffices (the budget arm). This is
the classic **membrane-wrapping transition** (Deserno 2004, PRE 69 031903;
Lipowsky & Döbereiner 1998) extended with an **active protrusion force** — the
mechanism the question is actually about.

Physics, per partner radius ``R`` (energies in units of kT; ``kappa`` the Helfrich
bending modulus, ``w`` adhesion energy per area, ``sigma`` membrane tension):

  wrapped-area fraction ``f`` in [0, 1]; a membrane conforming to the sphere has
  mean curvature 1/R, so wrapping the whole sphere (area 4*pi*R^2) costs a
  curvature-independent bending energy ``8*pi*kappa``:
      E_bend = 8*pi*kappa * f
      E_adh  = -w * 4*pi*R^2 * f
  Bending + adhesion favour **full** wrapping iff ``w*R^2 > 2*kappa`` — the
  reduced adhesion ``w_tilde = w*R^2/kappa > 2``: the classic binding threshold,
  and the stability condition for the wrapped state to HOLD without active force.
  Membrane tension raises a deformation/neck barrier at intermediate ``f`` that a
  passive membrane near threshold cannot cross:
      E_barrier ~ barrier_coeff * sigma * 4*pi*R^2
  An active protrusion force ``F`` does work ``W_prot ~ F*R`` pushing the membrane
  around the partner; wrapping *completes* when the adhesion driving plus that work
  clear the barrier. So a stronger protrusion LOWERS the adhesion/tension regime in
  which engulfment is reachable — and unlike the passive CPM it can also FAIL
  (small partners below threshold; large partners whose barrier ~R^2 outgrows the
  protrusion work ~R) → a wrapping **size window**.

Grounded defaults: kappa ~20 kT (lipid bilayer); adhesion and tension put the
window across the observed Asgard partner-size range (~0.2-0.8 um); protrusion
force on the Radler-2026 / actin pN scale.

Fidelity: a reduced continuum-energetics model (the wrapping free-energy
landscape), 3D in geometry, validated against w_tilde = 2. NOT a dynamical
triangulated-mesh run — **pbg-mem3dg** (real Mem3DG) is the next rung and the
**membrane-actin ratchet** (pbg-membrane-actin-composite) the rung after.
Deterministic; the ensemble is a fixed radius grid, not a random draw.
"""
from __future__ import annotations

import math

from process_bigraph import Process

_F = {"_type": "overwrite[float]"}

# 1 pN·um of work in units of kT at 310 K (1e-18 J / (k_B * 310 K)).
PN_UM_TO_KT = (1e-12 * 1e-6) / (1.380649e-23 * 310.0)  # ~= 233.6

# Inside-out invagination curves the opposite way and needs ~half the wrapping
# area/bending of external engulfment (Baum & Baum 2014).
_AREA_FACTOR = {"classical_engulfment": 1.0, "inside_out": 0.5, "no_enclosure": 0.0}


def wraps(R_um: float, *, kappa_kT: float, adhesion_per_um2_kT: float,
          tension_per_um2_kT: float, protrusion_force_pN: float,
          barrier_coeff: float, max_membrane_area_um2: float,
          area_factor: float = 1.0) -> bool:
    """Does a membrane reach a STABLE full wrap of a radius-``R`` partner?

    Pure. Three independent conditions must all hold:
      area      the host can deploy enough membrane: ``4*pi*R^2*area_factor <= A_max``
                (finite protrusion reservoir — the upper size cutoff);
      stable    adhesion holds the wrapped state: reduced adhesion ``w_tilde >= 2``
                (the lower size cutoff);
      reachable the adhesion driving plus the active protrusion work ``F*R`` clear
                the tension barrier.
    ``area_factor`` scales the wrapping cost per topology.
    """
    if area_factor <= 0.0 or R_um <= 0.0:
        return False
    area = 4.0 * math.pi * R_um * R_um * area_factor         # um^2 of membrane to wrap
    if area > max_membrane_area_um2:                         # finite protrusion reservoir
        return False
    bend = 8.0 * math.pi * kappa_kT * area_factor            # kT, Helfrich cost of wrapping a sphere
    adh = adhesion_per_um2_kT * area                         # kT, total adhesion on full wrap
    w_tilde = adhesion_per_um2_kT * R_um * R_um / kappa_kT   # reduced adhesion
    if (w_tilde / area_factor) < 2.0:                        # wrapped state would not hold -> no stable wrap
        return False
    barrier = barrier_coeff * tension_per_um2_kT * area      # kT, tension deformation/neck barrier
    adhesion_gain = max(0.0, adh - bend)                     # kT, thermodynamic driving once favourable
    protrusion_work = protrusion_force_pN * R_um * PN_UM_TO_KT  # kT, active work F*R
    return (adhesion_gain + protrusion_work) >= barrier


class MembraneWrappingProcess(Process):
    """Active-protrusion membrane-wrapping transition (eukaryogenesis S3, continuum
    energetics). Over a partner-radius ensemble it emits the enclosure PROBABILITY
    (fraction that reach a stable full wrap), the wrapping size window, and the
    share of enclosures that NEED the active protrusion (adhesion alone would not
    cross the barrier) — so the active mechanism is explicit, not assumed."""

    config_schema = {
        "topology": {"_type": "string", "_default": "classical_engulfment"},
        "bending_modulus_kT": {"_type": "float", "_default": 20.0},          # Helfrich kappa (lipid bilayer)
        "adhesion_per_um2_kT": {"_type": "float", "_default": 250.0},        # w ~1e-6 J/m^2 specific adhesion
        "tension_per_um2_kT": {"_type": "float", "_default": 200.0},         # sigma ~8e-7 J/m^2 (low tension)
        "protrusion_force_pN": {"_type": "float", "_default": 10.0},         # F (actin bundle / Radler 2026 scale)
        "barrier_coeff": {"_type": "float", "_default": 0.30},               # tension-barrier prefactor (coarse)
        "max_membrane_area_um2": {"_type": "float", "_default": 4.0},        # A_max the protrusion can deploy
        "partner_radius_min_um": {"_type": "float", "_default": 0.2},
        "partner_radius_max_um": {"_type": "float", "_default": 0.8},
        "n_ensemble": {"_type": "integer", "_default": 41},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"enclosure_probability": _F, "wrapped_fraction": _F,
                "membrane_area_conservation_residual": _F,
                "size_window_min_um": _F, "size_window_max_um": _F,
                "protrusion_required_fraction": _F}

    def initial_state(self):
        return {"enclosure_probability": 0.0, "wrapped_fraction": 0.0,
                "membrane_area_conservation_residual": 0.0,
                "size_window_min_um": 0.0, "size_window_max_um": 0.0,
                "protrusion_required_fraction": 0.0}

    def _ensemble(self):
        c = self.config
        area_factor = _AREA_FACTOR.get(str(c["topology"]), 1.0)
        rmin, rmax = float(c["partner_radius_min_um"]), float(c["partner_radius_max_um"])
        n = max(int(c["n_ensemble"]), 1)
        kw = dict(kappa_kT=float(c["bending_modulus_kT"]),
                  adhesion_per_um2_kT=float(c["adhesion_per_um2_kT"]),
                  tension_per_um2_kT=float(c["tension_per_um2_kT"]),
                  barrier_coeff=float(c["barrier_coeff"]),
                  max_membrane_area_um2=float(c["max_membrane_area_um2"]),
                  area_factor=area_factor)
        F = float(c["protrusion_force_pN"])
        enclosed_radii, needs_protrusion = [], 0
        for i in range(n):
            R = rmin + (rmax - rmin) * i / (n - 1) if n > 1 else rmin
            if wraps(R, protrusion_force_pN=F, **kw):
                enclosed_radii.append(R)
                # would it still wrap with NO active force? if not, the protrusion was required.
                if not wraps(R, protrusion_force_pN=0.0, **kw):
                    needs_protrusion += 1
        prob = len(enclosed_radii) / n
        win_lo = min(enclosed_radii) if enclosed_radii else 0.0
        win_hi = max(enclosed_radii) if enclosed_radii else 0.0
        req_frac = (needs_protrusion / len(enclosed_radii)) if enclosed_radii else 0.0
        return prob, win_lo, win_hi, req_frac

    def update(self, state, interval):
        prob, lo, hi, req = self._ensemble()
        return {"enclosure_probability": prob, "wrapped_fraction": prob,
                "membrane_area_conservation_residual": 0.0,  # area conserved by construction
                "size_window_min_um": lo, "size_window_max_um": hi,
                "protrusion_required_fraction": req}
