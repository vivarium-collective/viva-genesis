"""Module A real-bridge tests — PHREEQC serpentinization.

Guarded with ``importorskip`` so CI without ``phreeqpython`` installed skips
(not fails); a dev/CI machine with it exercises the genuine IPhreeqc engine.
"""
from __future__ import annotations

import pytest

pytest.importorskip("phreeqpython")

from process_bigraph import allocate_core  # noqa: E402

from viva_genesis.geochemistry.phreeqc_serpentinization import (  # noqa: E402
    PhreeqcSerpentinizationProcess,
)


def _proc():
    return PhreeqcSerpentinizationProcess(config={}, core=allocate_core())


def test_ports_declared():
    p = _proc()
    assert set(p.inputs()) == {"temperature", "flow_velocity", "DIC"}
    assert set(p.outputs()) == {
        "H2", "alkalinity", "heat", "H2_flux", "alkalinity_flux",
        "heat_flux", "pe", "pH_eq", "charge_imbalance",
    }


def test_real_speciation_is_reducing_and_charge_balanced():
    p = _proc()
    u = p.update({"temperature": 315.0, "flow_velocity": 1e-3, "DIC": 2e-3}, 1.0)
    # Genuine serpentinization: dissolved H2 source is positive (reducing power).
    assert u["H2_flux"] > 0.0
    assert u["H2"] > 0.0
    # Strongly reducing pe from the Fe(II)->magnetite + water->H2 redox.
    assert u["pe"] < 0.0
    # PHREEQC balances charge by construction -> charge_neutrality invariant.
    assert abs(u["charge_imbalance"]) < 1e-6
    # Exothermic reaction heat.
    assert u["heat_flux"] > 0.0


def test_temperature_window():
    """H2 production peaks in the serpentinization window and collapses when
    very hot (the Gaussian kinetic driver on top of the real equilibrium)."""
    p = _proc()
    warm = p.update({"temperature": 315.0, "flow_velocity": 1e-3, "DIC": 2e-3}, 1.0)
    hot = p.update({"temperature": 520.0, "flow_velocity": 1e-3, "DIC": 2e-3}, 1.0)
    assert warm["H2_flux"] > hot["H2_flux"]


def test_flow_dependence():
    """Serpentinization is water-flux limited: no flow -> no source."""
    p = _proc()
    stalled = p.update({"temperature": 315.0, "flow_velocity": 0.0, "DIC": 2e-3}, 1.0)
    assert stalled["H2_flux"] == pytest.approx(0.0, abs=1e-12)
