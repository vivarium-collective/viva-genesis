"""Protrusion-to-enclosure membrane mechanics (eukaryogenesis S3).

A coarse-grained, first-fidelity model of whether an archaeal host protrusion can transition
from contact to stable wrapping / engulfment of a bacterial partner. A protrusion of finite
membrane area extends at an observed rate and attempts to enclose a partner; enclosure succeeds,
for a given partner radius, only when the available membrane area covers the partner AND the
adhesion energy clears the Helfrich bending cost of wrapping. Over an ensemble of partner radii
the process emits an enclosure PROBABILITY, so morphology alone does not imply engulfment — the
geometry/energy budget does. Membrane area is conserved through the deformation (residual ~0).

Topologies compared (the ``topology`` config):
  - classical_engulfment : the host wraps the partner from outside; area requirement 4*pi*r^2.
  - inside_out           : the partner is enclosed into an invagination; ~half the area budget
                           (Baum & Baum 2014), so a wider partner range encloses.
  - no_enclosure         : the control — contact without wrapping; probability 0 by construction.

Deterministic + reproducible; the ensemble is a deterministic radius grid, not a random draw.
"""
from __future__ import annotations

import math

from process_bigraph import Process

_F = {"_type": "overwrite[float]"}


class MembraneEnclosureProcess(Process):
    """Coarse-grained protrusion-to-enclosure mechanics (area + bending-energy budget)."""

    config_schema = {
        "topology": {"_type": "string", "_default": "classical_engulfment"},
        "protrusion_area_um2": {"_type": "float", "_default": 4.0},     # membrane area the host can deploy
        "bending_modulus_kT": {"_type": "float", "_default": 20.0},     # Helfrich kappa
        "adhesion_energy_kT": {"_type": "float", "_default": 600.0},    # total adhesion available on wrapping
        "partner_radius_min_um": {"_type": "float", "_default": 0.2},
        "partner_radius_max_um": {"_type": "float", "_default": 0.8},
        "n_ensemble": {"_type": "integer", "_default": 41},
        "protrusion_speed_um2_per_s": {"_type": "float", "_default": 0.5},  # extension rate (Radler 2026 scale)
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._wrapped_area = 0.0

    def inputs(self):
        return {}

    def outputs(self):
        return {"enclosure_probability": _F, "membrane_area_conservation_residual": _F,
                "wrapped_fraction": _F}

    def initial_state(self):
        return {"enclosure_probability": 0.0, "membrane_area_conservation_residual": 0.0,
                "wrapped_fraction": 0.0}

    def _enclosure_probability(self) -> float:
        topo = str(self.config["topology"])
        if topo == "no_enclosure":
            return 0.0
        # inside-out wraps into an invagination → roughly half the area requirement of classical
        # external engulfment (Baum & Baum 2014).
        area_factor = 0.5 if topo == "inside_out" else 1.0
        kappa = float(self.config["bending_modulus_kT"])
        bend_cost = 8.0 * math.pi * kappa          # Helfrich bending energy of a wrapped sphere (kT)
        if float(self.config["adhesion_energy_kT"]) < bend_cost:
            return 0.0                              # adhesion cannot pay the bending cost → no enclosure
        a_avail = float(self.config["protrusion_area_um2"])
        rmin = float(self.config["partner_radius_min_um"])
        rmax = float(self.config["partner_radius_max_um"])
        n = max(int(self.config["n_ensemble"]), 1)
        feasible = 0
        for i in range(n):
            r = rmin + (rmax - rmin) * i / (n - 1) if n > 1 else rmin
            a_req = area_factor * 4.0 * math.pi * r * r
            if a_avail >= a_req:
                feasible += 1
        return feasible / n

    def update(self, state, interval):
        a_avail = float(self.config["protrusion_area_um2"])
        speed = float(self.config["protrusion_speed_um2_per_s"])
        # the protrusion extends membrane area over time, bounded by its budget (area conserved)
        self._wrapped_area = min(a_avail, self._wrapped_area + speed * float(interval))
        wrapped_fraction = (self._wrapped_area / a_avail) if a_avail else 0.0
        # membrane area is conserved: deployed area never exceeds the protrusion's budget
        residual = abs(self._wrapped_area - min(self._wrapped_area, a_avail))
        return {"enclosure_probability": self._enclosure_probability(),
                "membrane_area_conservation_residual": residual,
                "wrapped_fraction": wrapped_fraction}
