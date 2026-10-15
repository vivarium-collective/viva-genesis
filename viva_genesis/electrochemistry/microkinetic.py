"""Microkinetic carbon fixation — the deferred CatMAP / Cantera class (Phase 2).

The third class on the ``carbon_fixation`` face: mean-field adsorbate
microkinetics on the Fe/Ni-sulfide surface — site balance over ``*``, ``H*``,
``CO2*``, ``COOH*``/``HCOO*``, ``CO*`` and the passivating ``S*``/``O*``
species, potential-dependent elementary rate constants, coverage-dependent
hydrogen evolution and surface passivation — the physics the Butler-Volmer
class lumps into two exchange currents and a Ni gain.

The backend is **CatMAP** (descriptor-based microkinetic solver, needs
``mpmath`` + a compiled ASE/GPAW-adjacent stack) or **Cantera** (surface
``Interface`` phases with electrochemical reactions, conda-only wheels on
macOS/arm64). Neither installs in the uv ``.venv``; per the plan they run under
a pixi env the way ``viva-fenics`` does for dolfinx. So, exactly like the
FEniCS transport classes, this class **registers unconditionally** (its
``inputs()`` / ``outputs()`` are static, so ``resolve_checked`` / ``assert_face``
and composite *build* work everywhere) and **raises a clear error in
``update()``** when the backend is missing. It never returns canned numbers.

NEXT STEPS (recorded in ``NEXT_STEPS.md``): write ``mkm/fe_ni_s_co2rr.mkm``
(reaction list + descriptor scaling from the Preiner catalysts), bridge the
CatMAP ``ReactionModel`` solve to the same face ports as the Butler-Volmer
class, and re-run ``og-01-cal-electrochemistry`` with the third class under
pixi.
"""

from __future__ import annotations

from process_bigraph import Process

from .butler_volmer import ButlerVolmerCarbonFixationProcess, T_REF

_BV = ButlerVolmerCarbonFixationProcess

BACKENDS = ("catmap", "cantera")


def backend_available() -> str | None:
    """The first importable microkinetic backend, or ``None`` (the uv ``.venv`` case)."""
    import importlib
    for name in BACKENDS:
        try:
            importlib.import_module(name)
            return name
        except Exception:
            continue
    return None


class MicrokineticBackendMissing(RuntimeError):
    """Raised when the microkinetic class is run without CatMAP / Cantera."""


class MicrokineticCarbonFixationProcess(Process):
    """Adsorbate microkinetics of CO2 reduction on the Fe/Ni-sulfide surface
    (site coverages, potential-dependent elementary steps, passivation) — the
    plan's third ``carbon_fixation`` class. Same face ports as the Butler-Volmer
    class. Requires CatMAP or Cantera under the pixi env; in the uv ``.venv``
    the class builds and face-checks but ``update`` raises."""

    contract = {
        "summary": "Mean-field adsorbate microkinetics of CO2 reduction (CatMAP / Cantera backend; runs under pixi).",
        "description": (
            "Planned third class on the carbon_fixation face: a site balance over the "
            "Fe/Ni-sulfide surface (free sites, H*, CO2*, COOH*/HCOO*, CO*, passivating "
            "S*/O*), potential-dependent elementary rate constants from descriptor "
            "scaling, coverage-dependent hydrogen evolution and surface passivation, "
            "solved at steady state each tick and reduced to the same circuit readouts "
            "and loss fractions the Butler-Volmer class publishes. The backend (CatMAP or "
            "Cantera) is conda-only, so the class registers everywhere, builds and "
            "face-checks in the uv venv, and raises a clear 'run under pixi' error in "
            "update() when the backend is missing. It never returns placeholder numbers."
        ),
        "inputs": dict(_BV.contract["inputs"]),
        "outputs": dict(_BV.contract["outputs"]),
        "assumptions": ["Mean-field coverages; steady state per tick.",
                        "Descriptor scaling from the Preiner catalyst set (to be written: mkm/fe_ni_s_co2rr.mkm)."],
        "references": ["commchem2026energeticconstraints", "preiner2020hydrogen"],
    }

    config_schema = {
        "backend": {"_type": "string", "_default": "catmap", "_provenance": "inferred"},
        "mkm_file": {"_type": "string", "_default": "mkm/fe_ni_s_co2rr.mkm", "_provenance": "hypothetical"},
        "site_density": {"_type": "float", "_default": 1.0e-5, "_units": "mole/meter**2", "_provenance": "inferred"},
        "interface_area": dict(_BV.config_schema["interface_area"]),
        "reactor_volume": dict(_BV.config_schema["reactor_volume"]),
        "dilution_rate": dict(_BV.config_schema["dilution_rate"]),
    }

    def inputs(self):
        return _BV.inputs(self)

    def outputs(self):
        return _BV.outputs(self)

    def initial_state(self):
        return _BV.initial_state(self)

    def update(self, state, interval):
        backend = backend_available()
        if backend is None:
            raise MicrokineticBackendMissing(
                "MicrokineticCarbonFixationProcess requires CatMAP or Cantera, which are conda-only "
                "and not installed in this uv venv. Run under the pixi env (the viva-fenics pattern: "
                "`pixi run python ...` with catmap/cantera in pixi.toml), or select the "
                "'butler_volmer' / 'empirical' class on the carbon_fixation face. This class does not "
                "fall back to a mock.")
        raise MicrokineticBackendMissing(
            f"{backend} is importable but the Fe/Ni-S CO2RR mechanism bridge "
            f"({self.config['mkm_file']}) is not implemented yet — see NEXT_STEPS.md (Phase 2).")


__all__ = ["MicrokineticCarbonFixationProcess", "MicrokineticBackendMissing", "backend_available", "BACKENDS"]
