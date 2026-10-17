"""viva-openmm integration: the Martini CG MD engine for membrane studies (31/32).

OpenMM is a heavy opt-in extra; build_core registers OpenMMMartiniProcess only
when viva-openmm is installed (guarded). These tests skip cleanly without it, so
CI without the membrane extra stays green.
"""
import pytest

from viva_genesis.core import build_core

pytest.importorskip("viva_openmm")


def test_openmm_martini_process_registered_when_installed():
    assert "OpenMMMartiniProcess" in build_core().link_registry


def test_openmm_martini_process_imports_lazily():
    # The class imports without OpenMM present (OpenMM is imported inside update()),
    # so registration never requires the heavy runtime dep at import time.
    from viva_openmm import OpenMMMartiniProcess
    assert hasattr(OpenMMMartiniProcess, "update")
