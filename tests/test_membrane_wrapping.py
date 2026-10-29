"""Physics validation for the active-protrusion membrane-wrapping model (S3).

Checks the model against known membrane-wrapping results: the passive binding
threshold (reduced adhesion w_tilde = 2), that an active protrusion force enables
wrapping passive adhesion cannot reach, the finite-area upper cutoff, and that the
ensemble enclosure probability discriminates across regimes (unlike the
regime-assumed CPM arm).
"""
from __future__ import annotations

from viva_genesis.membrane_wrapping import wraps, MembraneWrappingProcess
from viva_genesis.core import build_core

# a permissive base regime (no tension barrier, huge area reservoir) to isolate one effect at a time
_PASSIVE = dict(kappa_kT=20.0, tension_per_um2_kT=0.0, protrusion_force_pN=0.0,
                barrier_coeff=0.3, max_membrane_area_um2=1e9)


def test_passive_binding_threshold_at_w_tilde_2():
    # w_tilde = w*R^2/kappa ; with no barrier, wraps iff w_tilde >= 2
    # R=0.5, kappa=20 -> threshold adhesion w* = 2*kappa/R^2 = 160 kT/um^2
    assert wraps(0.5, adhesion_per_um2_kT=240.0, **_PASSIVE) is True    # w_tilde = 3.0
    assert wraps(0.5, adhesion_per_um2_kT=120.0, **_PASSIVE) is False   # w_tilde = 1.5


def test_active_protrusion_enables_wrapping_passive_adhesion_cannot():
    # stable (w_tilde>=2) but the tension barrier exceeds the adhesion driving:
    # passive membrane cannot wrap; the protrusion force carries it over.
    base = dict(kappa_kT=20.0, adhesion_per_um2_kT=170.0, tension_per_um2_kT=200.0,
                barrier_coeff=0.3, max_membrane_area_um2=10.0)
    assert wraps(0.5, protrusion_force_pN=0.0, **base) is False
    assert wraps(0.5, protrusion_force_pN=10.0, **base) is True


def test_finite_membrane_area_is_an_upper_size_cutoff():
    base = dict(kappa_kT=20.0, adhesion_per_um2_kT=250.0, tension_per_um2_kT=50.0,
                protrusion_force_pN=20.0, barrier_coeff=0.3, max_membrane_area_um2=4.0)
    # 4*pi*R^2 at R=0.5 is ~3.14 (<4, ok); at R=0.6 is ~4.52 (>4, no membrane to deploy)
    assert wraps(0.5, **base) is True
    assert wraps(0.6, **base) is False


def test_no_enclosure_topology_never_wraps():
    assert wraps(0.5, adhesion_per_um2_kT=240.0, area_factor=0.0, **_PASSIVE) is False


def test_ensemble_probability_discriminates_and_is_bounded():
    core = build_core()
    favourable = MembraneWrappingProcess(config={}, core=core)          # grounded defaults
    p_fav, lo, hi, req = favourable._ensemble()
    assert 0.0 < p_fav < 1.0                 # a real window, not all-or-nothing (cf. CPM's 1.0)
    assert lo > 0.0 and hi >= lo             # bounded wrapping size window
    # a low-adhesion regime cannot wrap anything -> probability collapses to 0
    starved = MembraneWrappingProcess(config={"adhesion_per_um2_kT": 20.0}, core=core)
    p_starved, _, _, _ = starved._ensemble()
    assert p_starved == 0.0
    assert p_fav > p_starved                 # the model discriminates across regimes


def test_active_protrusion_raises_ensemble_enclosure_probability():
    # grid-level check via the pure function (the Process config-merge treats an
    # explicit 0.0 force as unset, so compare forces directly here).
    base = dict(kappa_kT=20.0, adhesion_per_um2_kT=250.0, tension_per_um2_kT=200.0,
                barrier_coeff=0.3, max_membrane_area_um2=4.0)
    grid = [0.2 + 0.6 * i / 40 for i in range(41)]
    p0 = sum(wraps(R, protrusion_force_pN=0.0, **base) for R in grid) / len(grid)
    p10 = sum(wraps(R, protrusion_force_pN=10.0, **base) for R in grid) / len(grid)
    assert p10 > p0 > 0.0                     # the observed protrusion mechanics are load-bearing
