"""Campaign UQ layer (Model Upgrade plan, section 11 + the "campaign UQ layer" deliverable).

Cross-cutting computational methods behind every stage's three-quantity report:

* :mod:`.sampling` — Latin-hypercube / Monte-Carlo draws from a provenance-carrying
  :class:`~viva_genesis.provenance.ParameterPackage` (uncertainty propagation).
* :mod:`.sensitivity` — Morris elementary-effects screening then Sobol first /
  total-order indices (global sensitivity analysis), on any ``model(x) -> float``.
* :mod:`.calibration` — the Bayesian-calibration interface: observation windows,
  ABC-rejection posterior (the worked example), Gaussian importance weights, and
  the ``Calibrator`` protocol a PyMC/NumPyro backend plugs into.
* :mod:`.ensemble` — structural model ensembles on a ``SweepResult`` with a
  categorical model-class axis: ``pass_fraction`` per class, ``structure_agreement``
  across classes, ``decision_envelope``.
* :mod:`.report` — the Feasibility / Robustness / Discrimination triple + evidence
  tier (reproduction / mechanistic prediction / conceptual demonstration) a stage
  reports.
* :mod:`.environment_calibration` — Phase 1 worked concretely: the Lost-City-
  conditioned vent ensemble on the real PHREEQC + FiPy geochemical world.
"""

from .report import (  # noqa: F401
    EvidenceTier, Feasibility, Robustness, Discrimination, TransitionReport,
)
from .ensemble import pass_fraction, structure_agreement, decision_envelope  # noqa: F401
from .sampling import lhs_unit, sample_package  # noqa: F401
from .sensitivity import morris, sobol  # noqa: F401
from .calibration import Observation, abc_rejection, gaussian_weights  # noqa: F401

__all__ = [
    "EvidenceTier", "Feasibility", "Robustness", "Discrimination", "TransitionReport",
    "pass_fraction", "structure_agreement", "decision_envelope",
    "lhs_unit", "sample_package", "morris", "sobol",
    "Observation", "abc_rejection", "gaussian_weights",
]
