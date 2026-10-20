"""og-evolvable-lineages: evolvability given a granted individual.

Covers: real heritable selection shifts composition above both matched nulls
(no-inheritance and shared-feed), it adapts to a changed environment, and it is
BOUNDED (heritable variance declines as the population converges; the trait space
is a fixed scalar) — not open-ended. The nulls are genuinely matched (each kills
the response for a different reason), so the signal is heritability AND selection.
"""
from __future__ import annotations

from process_bigraph.composite_generator import _REGISTRY  # noqa: F401
from viva_genesis.core import build_core
from viva_genesis.compartments.heredity_population import HeredityPopulationProcess
import viva_genesis.composites  # noqa: F401  (fires generators)


def _evolve(core, gens=30, flip_at=None, **cfg):
    base = {"inheritance": True, "n_pop": 120, "sigma": 0.03, "seed": 7,
            "fitness_exponent": 2.0, "retention_lo": 0.333, "retention_hi": 0.661}
    base.update(cfg)
    p = HeredityPopulationProcess(config=base, core=core)
    st = p.initial_state() if hasattr(p, "initial_state") else {}
    traj = []
    for g in range(gens):
        if flip_at is not None and g == flip_at:
            p.config["retention_lo"], p.config["retention_hi"] = base["retention_hi"], base["retention_lo"]
        last = p.update(st, 1.0)
        traj.append(last)
    return traj


def test_composite_registered():
    assert "viva_genesis.composites.evolvable_lineages.og_evolvable_lineages" in _REGISTRY


def test_full_selection_real_above_nulls():
    core = build_core()
    full = _evolve(core)
    no_inh = _evolve(core, inheritance=False)
    shared = _evolve(core, retention_lo=0.5, retention_hi=0.5)  # flat landscape = shared-feed null

    def shift(tr):
        return tr[-1]["mean_composition"] - tr[0]["mean_composition"]

    # real heritable selection: strong shift + high parent-offspring correlation
    assert shift(full) > 0.3
    assert full[-1]["parent_offspring_fitness_correlation"] > 0.5
    # both matched nulls kill the directional response
    assert shift(no_inh) < 0.1
    assert shift(shared) < 0.1


def test_bounded_not_open_ended():
    """Heritable variance declines as the population converges — bounded fixed-trait
    selection, not open-ended (where variance would be sustained)."""
    core = build_core()
    full = _evolve(core)
    v0 = full[0]["heritable_fitness_variance"]
    vN = full[-1]["heritable_fitness_variance"]
    assert vN < v0                      # variance consumed on convergence -> bounded


def test_adapts_to_changed_environment():
    """Flipping the favored composition mid-run: the inheriting population re-tracks
    toward the new optimum; the no-inheritance null does not."""
    core = build_core()
    full = _evolve(core, gens=40, flip_at=20)
    null = _evolve(core, gens=40, flip_at=20, inheritance=False)
    retrack_full = full[-1]["mean_composition"] - full[19]["mean_composition"]
    retrack_null = null[-1]["mean_composition"] - null[19]["mean_composition"]
    assert retrack_full < -0.1                      # re-tracks down toward the flipped (low-c) optimum
    assert abs(retrack_full) > abs(retrack_null)    # above the no-inheritance null
