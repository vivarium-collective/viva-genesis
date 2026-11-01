"""Enclosure-mechanics process for the proto_endosymbiosis bridge (M2).

Measures ``probability_of_stable_enclosure`` — whether physically-constrained membrane
remodelling reaches STABLE, persistent enclosure (sealed and surviving perturbation),
WITHOUT imposing the sealed topology as a starting condition. Discriminates
H2-geometry-first (stable enclosure in a majority of the feasible regime, P>=0.5) from
H3-parasitism-or-conflict (enclosure reached but unstable/exploitative, P<0.5).

Reduced coupled model (inferential scope): a three-compartment ensemble of enclosure
attempts — attempting -> sealed <-> stalled — with sealing driven by the net energetic
drive (adhesion_energy - bending_modulus, the neck-closure barrier) and UNWRAPPING of
sealed attempts driven by (perturbation - adhesion). The settled sealed fraction is the
stable-enclosure probability. It does NOT resolve the full membrane PDE / CPM geometry
(that is the next fidelity); it establishes whether, given an adhesion/bending/perturbation
balance, stable enclosure is the majority outcome — emergent, not imposed.
"""
from __future__ import annotations

import math

from process_bigraph import Process


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(x, 50.0), -50.0)))


class EnclosureProcess(Process):
    """Three-compartment enclosure ensemble (attempting -> sealed <-> stalled).

    Each tick: an attempting attempt SEALS with prob ~ sigmoid(k*(adhesion-bending)) —
    adhesion must overcome the bending neck-closure barrier; a sealed attempt UNWRAPS to
    stalled with prob ~ sigmoid(k*(perturbation-adhesion)); stalled attempts slowly retry.
    The settled sealed fraction = probability_of_stable_enclosure.
    """

    config_schema = {
        "adhesion_energy": {"_type": "float", "_default": 0.6},   # drives sealing + resists unwrap
        "bending_modulus": {"_type": "float", "_default": 0.3},   # neck-closure barrier (cost)
        "perturbation": {"_type": "float", "_default": 0.2},      # unwrapping stress on sealed attempts
        "seal_rate": {"_type": "float", "_default": 0.3},
        "unwrap_rate": {"_type": "float", "_default": 0.3},
        "retry_rate": {"_type": "float", "_default": 0.05},
        "sharpness": {"_type": "float", "_default": 6.0},         # k in the sigmoids
    }

    def inputs(self):
        return {"n_attempting": "float", "n_sealed": "float", "n_stalled": "float"}

    def outputs(self):
        return {"n_attempting": "float", "n_sealed": "float", "n_stalled": "float"}

    def update(self, state, interval):
        c = self.config
        att = max(float(state.get("n_attempting", 0.0) or 0.0), 0.0)
        seal = max(float(state.get("n_sealed", 0.0) or 0.0), 0.0)
        stall = max(float(state.get("n_stalled", 0.0) or 0.0), 0.0)
        k = float(c["sharpness"])
        p_seal = _sigmoid(k * (float(c["adhesion_energy"]) - float(c["bending_modulus"])))
        p_unwrap = _sigmoid(k * (float(c["perturbation"]) - float(c["adhesion_energy"])))
        dt = float(interval)
        flow_seal = att * p_seal * float(c["seal_rate"]) * dt           # attempting -> sealed
        flow_unwrap = seal * p_unwrap * float(c["unwrap_rate"]) * dt     # sealed -> stalled
        flow_retry = stall * float(c["retry_rate"]) * dt                 # stalled -> attempting
        return {
            "n_attempting": -flow_seal + flow_retry,
            "n_sealed": flow_seal - flow_unwrap,
            "n_stalled": flow_unwrap - flow_retry,
        }
