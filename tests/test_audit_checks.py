"""Audit checks wired into lint-workspace: baseline-param + optional-import guards."""
from viva_genesis.audit_checks import (
    check_baseline_params,
    check_unguarded_optional_imports,
)


# --------------------------------------------------------------------------- #
# check_baseline_params
# --------------------------------------------------------------------------- #
def _study(baseline):
    return {"baseline": baseline}


def test_baseline_param_declared_is_clean():
    studies = {"s": _study([{"name": "b", "composite": "pkg.m.g",
                             "params": {"flow_velocity": 1.0}}])}
    gen = {"pkg.m.g": {"flow_velocity", "nx"}}
    assert check_baseline_params(studies, gen) == []


def test_baseline_param_orphan_is_flagged():
    # The og-12 break: a param left after a repoint that the composite no longer declares.
    studies = {"s": _study([{"name": "b", "composite": "pkg.m.g",
                             "params": {"model_proto_metabolism": "curated_rtca"}}])}
    gen = {"pkg.m.g": {"flow_velocity", "nx"}}
    errs = check_baseline_params(studies, gen)
    assert len(errs) == 1
    assert "model_proto_metabolism" in errs[0] and "pkg.m.g" in errs[0]


def test_baseline_unresolved_composite_is_skipped():
    # A planned / unresolved composite ref isn't in gen_parameters -> not our check.
    studies = {"s": _study([{"name": "b", "composite": "pkg.m.planned",
                             "params": {"anything": 1}}])}
    assert check_baseline_params(studies, {"pkg.m.g": {"x"}}) == []


def test_baseline_empty_params_clean():
    studies = {"s": _study([{"name": "b", "composite": "pkg.m.g", "params": {}}])}
    assert check_baseline_params(studies, {"pkg.m.g": {"x"}}) == []


# --------------------------------------------------------------------------- #
# check_unguarded_optional_imports
# --------------------------------------------------------------------------- #
_OPT = {"viva_openmm", "openmm", "rdkit", "fipy"}


def test_module_level_optional_import_flagged():
    src = "import pytest\nimport viva_openmm\n\ndef test_x():\n    assert True\n"
    errs = check_unguarded_optional_imports([("test_martini.py", src)], _OPT)
    assert len(errs) == 1 and "viva_openmm" in errs[0]


def test_from_import_of_optional_flagged():
    src = "from openmm import unit\n"
    errs = check_unguarded_optional_imports([("test_md.py", src)], _OPT)
    assert len(errs) == 1 and "openmm" in errs[0]


def test_importorskip_guarded_is_clean():
    # The correct pattern — no bare module-level import of the dep.
    src = ('import pytest\n'
           'viva_openmm = pytest.importorskip("viva_openmm")\n'
           'def test_x():\n    assert viva_openmm\n')
    assert check_unguarded_optional_imports([("test_ok.py", src)], _OPT) == []


def test_import_inside_function_is_clean():
    # Nested (lazy) import runs only when the test runs — fine.
    src = "def test_x():\n    import rdkit\n    assert rdkit\n"
    assert check_unguarded_optional_imports([("test_lazy.py", src)], _OPT) == []


def test_non_optional_import_ignored():
    src = "import numpy\nimport pytest\n"
    assert check_unguarded_optional_imports([("test_n.py", src)], _OPT) == []
