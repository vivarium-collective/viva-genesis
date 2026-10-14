"""og-adv — adversarial generic-nonequilibrium control.

The campaign's falsifiability test: run the REAL og-01/02/03 composites with every
vent feature removed (no sustained H2, no Fe/Ni/S catalyst, no pore concentration)
and require that the SAME gates REJECT the control while the vent passes them. The
control is a parameterization of the real composites — not a mock — so this tests
the actual models. Pure composite runs, no heavy grid, so it runs everywhere.
"""
from __future__ import annotations

import pytest

from viva_genesis.adversarial import GENERIC_PARAMS, adversarial_verdict
from viva_genesis.core import build_core


@pytest.fixture(scope="module")
def verdict():
    return adversarial_verdict(build_core())


def test_viz_and_phase_map_registered():
    assert "VentSpecificityMap" in build_core().link_registry
    from viva_genesis import phase_maps
    assert hasattr(phase_maps, "vent_specificity_map")


def test_every_gate_rejects_the_generic_control(verdict):
    """Each vent-specific gate's measured value falls BELOW its threshold for the
    generic control — the control passes by being rejected."""
    assert verdict["generic_rejected"] is True
    assert verdict["n_gates"] == 5
    for g in verdict["gate_rows"]:
        assert g["generic"] < g["threshold"], f"gate {g['label']} did NOT reject generic"


def test_vent_passes_every_gate_the_control_fails(verdict):
    """Vent-specificity: the vent clears every gate the control fails (pass-where-
    control-fails), so a PASS certifies the vent mechanism."""
    assert verdict["vent_passes"] is True
    for g in verdict["gate_rows"]:
        assert g["vent"] >= g["threshold"], f"vent did NOT pass gate {g['label']}"
        assert g["vent"] > g["generic"]


def test_rejection_is_by_a_clear_margin(verdict):
    """The control is rejected by a real margin, not a knife-edge."""
    assert verdict["min_reject_decades"] > 1.0


def test_catalyst_zero_is_honored_not_swallowed():
    """The control-integrity fix: catalyst_active=0 must be clamped (honored), not
    swallowed by is_empty(Float, 0.0) and refilled with the default (which would
    silently run the no-catalyst control WITH catalyst)."""
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.composites.carbon_fixation import hydrothermal_carbon_fixation
    core = build_core()

    def peak_formate(catalyst):
        sim = Composite({"state": hydrothermal_carbon_fixation(
            core, catalyst_active=catalyst, h2=5.0e-3, gradient_efficiency=1.0)}, core=core)
        sim.run(40.0)
        rows = gather_emitter_results(sim)[("emitter",)]
        return max((r.get("formate", 0.0) for r in rows), default=0.0)

    # with catalyst OFF, formate must be far below the catalyst-ON case (not equal to it,
    # which is what the is_empty swallow produced).
    off = peak_formate(0.0)
    on = peak_formate(1.0)
    assert off < on * 1e-3, f"catalyst=0 ({off:.3g}) not honored vs catalyst=1 ({on:.3g})"


def test_generic_carbon_control_below_og01_band():
    """The canonical generic control (vent features off) produces formate far below
    the og-01 Preiner band (50 mM) — the headline rejection."""
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.composites.carbon_fixation import hydrothermal_carbon_fixation
    core = build_core()
    sim = Composite({"state": hydrothermal_carbon_fixation(core, **GENERIC_PARAMS["carbon"])}, core=core)
    sim.run(50.0)
    rows = gather_emitter_results(sim)[("emitter",)]
    settled_formate_mM = (sum(r.get("formate", 0.0) for r in rows[-5:]) / 5) * 1e3
    assert settled_formate_mM < 50.0


def test_vent_specificity_three_view_registered_and_renders():
    """The complete three-view (World vent-vs-generic trajectories + Mechanism per-gate
    rejection bars + Decision gate contour) is registered and renders a Plotly figure.
    Rendered via the figure builder on a small duck-typed grid to stay fast."""
    import numpy as np
    assert "VentSpecificityThreeView" in build_core().link_registry
    from viva_genesis.viz_phase import _ResultView, vent_specificity_threeview_figure
    h2 = np.geomspace(1e-9, 2e-2, 6)
    cat = np.linspace(0.0, 1.0, 6)
    peak = np.outer(np.linspace(1e-13, 4e-2, 6), np.linspace(1e-13, 1.0, 6))
    res = _ResultView(["h2", "catalyst_active"], {"h2": h2, "catalyst_active": cat},
                      {"peak_flux": peak}, {"gate_threshold": 1e-6})
    traj = {"vent": {"t": list(range(5)), "formate_mM": [1e-3, 1, 50, 150, 200]},
            "generic": {"t": list(range(5)), "formate_mM": [1e-8] * 5}}
    gate_rows = [{"label": "og-01 net C-flux", "threshold": 1e-6, "vent": 0.04, "generic": 4e-13}]
    html = vent_specificity_threeview_figure(res, traj, gate_rows=gate_rows)
    assert isinstance(html, str) and "plotly" in html.lower() and len(html) > 5000
