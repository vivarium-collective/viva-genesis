"""vg-data provenance layer: parameters carry value-or-distribution, units,
context, source and a provenance class; packages load, sample, audit and map
onto configs; the packaged vent_environment cites only bibkeys that exist."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from viva_genesis import provenance as P

WS_ROOT = Path(__file__).resolve().parents[1]


def test_provenance_classes_and_legacy_map():
    assert P.ProvenanceClass.parse("measured") is P.ProvenanceClass.MEASURED
    assert P.ProvenanceClass.parse("FIELD") is P.ProvenanceClass.MEASURED
    assert P.ProvenanceClass.parse("HYPOTHESIS") is P.ProvenanceClass.HYPOTHETICAL
    assert P.ProvenanceClass.parse("MODEL") is P.ProvenanceClass.INFERRED
    with pytest.raises(ValueError):
        P.ProvenanceClass.parse("guessed")


def test_parameter_requires_value_or_distribution():
    with pytest.raises(ValueError):
        P.Parameter(id="x", units="molar", provenance="measured")
    p = P.Parameter(id="x", units="molar", provenance="measured", value=1.0)
    assert p.is_fixed and p.nominal() == 1.0
    assert np.all(p.sample(np.random.default_rng(0), 3) == 1.0)


def test_distributions_sample_inside_bounds():
    rng = np.random.default_rng(1)
    for kind, kw in [("uniform", dict(low=1, high=3)), ("loguniform", dict(low=1e-3, high=1e-1)),
                     ("triangular", dict(low=0, high=2, mode=0.5))]:
        d = P.Distribution(kind=kind, **kw)
        x = d.ppf(rng.random(500))
        lo, hi = d.bounds()
        assert x.min() >= lo - 1e-12 and x.max() <= hi + 1e-12
    ln = P.Distribution(kind="lognormal", mean=-3.0, sd=0.5)
    x = ln.ppf(rng.random(2000))
    assert 1e-4 < np.median(x) < 1e-2
    with pytest.raises(ValueError):
        P.Distribution(kind="loguniform", low=0, high=1)


def test_package_roundtrip_sample_audit_config():
    pkg = P.ParameterPackage.from_dict({
        "name": "toy", "version": "1",
        "parameters": [
            {"id": "a", "units": "molar", "provenance": "measured", "value": 2.0,
             "sources": ["x2020"], "consumed_by": "Proc.alpha"},
            {"id": "b", "units": "kelvin", "provenance": "hypothetical",
             "distribution": {"kind": "uniform", "low": 300, "high": 400}},
        ],
    })
    assert pkg.nominal() == {"a": 2.0, "b": 350.0}
    draws = pkg.sample(np.random.default_rng(0), 5)
    assert len(draws) == 5 and all(300 <= d["b"] <= 400 and d["a"] == 2.0 for d in draws)
    cfg = pkg.to_config(values=draws[0])
    assert cfg["alpha"] == 2.0 and cfg["b"] == draws[0]["b"]      # consumed_by suffix / id fallback
    audit = pkg.audit()
    assert audit["counts"]["measured"] == 1 and audit["counts"]["hypothetical"] == 1
    assert audit["hypothetical"] == ["b"] and audit["n_free"] == 1
    again = P.ParameterPackage.from_dict(pkg.to_dict())
    assert again.nominal() == pkg.nominal()


def test_packaged_vent_environment_loads_and_cites_real_bibkeys():
    assert "vent_environment" in P.list_packages()
    pkg = P.load_package("vent_environment")
    assert {"flow_velocity", "olivine_rate", "pyroxene_fraction", "heat_to_fluid_fraction"} <= set(pkg.parameters)
    assert len(pkg.free()) >= 5
    for p in pkg:
        assert p.units and p.provenance in P.ProvenanceClass
    assert pkg.observations["outlet_pH"]["low"] == 9.0
    missing = P.check_bib(pkg, WS_ROOT / "workspace" / "references" / "papers.bib")
    assert not missing, f"vent_environment cites bibkeys not in papers.bib: {missing}"
    audit = pkg.audit()
    # the audit must be honest: the Hadean DIC proxy is flagged, not hidden
    assert "fluid_dic" in audit["extrapolated"] and "fluid_dic" in audit["unsourced"]
    assert "olivine_rate" in audit["hypothetical"]


def test_audit_config_schema_flags_undeclared_provenance():
    from viva_genesis.ledger import ConservationLedgerProcess
    from viva_genesis.geochemistry.phreeqc_serpentinization import PhreeqcSerpentinizationProcess
    assert not P.audit_config_schema(ConservationLedgerProcess.config_schema)["undeclared"]
    legacy = P.audit_config_schema(PhreeqcSerpentinizationProcess.config_schema)
    assert legacy["undeclared"]   # the legacy process has not been annotated yet (advisory)
