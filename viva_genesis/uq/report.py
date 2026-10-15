"""The three-quantity standard + evidence tiers a stage reports.

Model Upgrade plan section 1: *for every major transition, report three
distinct quantities* —

* **Feasibility** — does at least one physically admissible parameterization
  support the transition?
* **Robustness** — what fraction of the empirically supported parameter
  distribution supports it, and across which model classes?
* **Discrimination** — which observations or perturbations distinguish the
  favored mechanism from plausible alternatives?

— and label the result with an **evidence tier** that fixes the language the
study may use: *reproduction* ("reproduces / validates"), *mechanistic
prediction* ("predicts under stated assumptions"), *conceptual demonstration*
("demonstrates in a coarse-grained model").

:class:`TransitionReport` is the serialisable triple a study's findings /
``study_card`` cite, and :func:`verdict_language` returns the sentence stem the
tier permits so a finding cannot overclaim by construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class EvidenceTier(str, Enum):
    REPRODUCTION = "reproduction"
    MECHANISTIC_PREDICTION = "mechanistic_prediction"
    CONCEPTUAL_DEMONSTRATION = "conceptual_demonstration"

    @property
    def language(self) -> str:
        return _TIER_LANGUAGE[self]

    @property
    def meaning(self) -> str:
        return _TIER_MEANING[self]


_TIER_LANGUAGE = {
    EvidenceTier.REPRODUCTION: "reproduces / validates",
    EvidenceTier.MECHANISTIC_PREDICTION: "predicts under stated assumptions",
    EvidenceTier.CONCEPTUAL_DEMONSTRATION: "demonstrates in a coarse-grained model",
}
_TIER_MEANING = {
    EvidenceTier.REPRODUCTION: "reproduces an external measured or established result",
    EvidenceTier.MECHANISTIC_PREDICTION: "a parameterized model makes a new quantitative prediction",
    EvidenceTier.CONCEPTUAL_DEMONSTRATION: "a reduced model shows that an organizational principle is possible",
}


def verdict_language(tier: EvidenceTier | str) -> str:
    return EvidenceTier(tier).language


@dataclass
class Feasibility:
    """Is there >= 1 physically admissible parameterization that supports the transition?"""

    feasible: bool
    n_admissible: int                 # draws / grid points that are physically admissible
    n_supporting: int                 # ... and support the transition
    example: dict[str, Any] = field(default_factory=dict)   # one supporting parameterization
    admissibility: str = ""          # what "physically admissible" meant (the conditioning set)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Robustness:
    """What fraction of the empirically supported distribution supports it, across which classes?"""

    fraction: float                              # posterior-weighted support, headline class
    by_class: dict[str, float] = field(default_factory=dict)      # per model class
    structure_agreement: float | None = None     # fraction of draws where all classes agree
    structure_uncertainty: float | None = None   # 1 - agreement
    n_posterior: int = 0
    n_prior: int = 0
    binding_observation: str = ""                # the observation that rejects most prior draws
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Discrimination:
    """Which observations / perturbations distinguish the favored mechanism from alternatives?"""

    alternatives: list[str] = field(default_factory=list)
    discriminating: list[dict] = field(default_factory=list)   # [{readout, d, mean_diff, ...}] best first
    non_discriminating: list[str] = field(default_factory=list)
    proposed_perturbations: list[str] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TransitionReport:
    """The three-quantity report for one transition / stage, with its evidence tier."""

    transition: str
    tier: EvidenceTier
    feasibility: Feasibility
    robustness: Robustness
    discrimination: Discrimination
    gate: str = ""                 # the pre-registered gate the quantities refer to
    model_classes: list[str] = field(default_factory=list)
    provenance_audit: dict = field(default_factory=dict)   # ParameterPackage.audit()
    numerical_verification: dict = field(default_factory=dict)  # ledger residuals, convergence
    sensitivity: dict = field(default_factory=dict)        # Morris / Sobol summary
    meta: dict = field(default_factory=dict)

    @property
    def language(self) -> str:
        return self.tier.language

    def headline(self) -> str:
        f, r = self.feasibility, self.robustness
        bits = [
            f"{self.transition}: {self.tier.language}",
            f"feasible={'yes' if f.feasible else 'no'} ({f.n_supporting}/{f.n_admissible} admissible parameterizations support it)",
            f"robustness={r.fraction:.2f} of the posterior" + (
                f" (agreement across classes {r.structure_agreement:.2f})" if r.structure_agreement is not None else ""),
        ]
        if self.discrimination.discriminating:
            top = self.discrimination.discriminating[0]
            bits.append(f"most discriminating readout: {top.get('readout')} (d={top.get('d', float('nan')):.2f})")
        return "; ".join(bits)

    def to_dict(self) -> dict:
        return {
            "transition": self.transition,
            "tier": self.tier.value,
            "language": self.tier.language,
            "gate": self.gate,
            "model_classes": list(self.model_classes),
            "feasibility": self.feasibility.to_dict(),
            "robustness": self.robustness.to_dict(),
            "discrimination": self.discrimination.to_dict(),
            "provenance_audit": dict(self.provenance_audit),
            "numerical_verification": dict(self.numerical_verification),
            "sensitivity": dict(self.sensitivity),
            "meta": dict(self.meta),
            "headline": self.headline(),
        }


# The decision-discipline rules of plan section 14, as machine-checkable predicates
# a report can be audited against before a headline conclusion moves forward.
def decision_discipline(report: TransitionReport, *, residual_tol: float = 1.0e-6) -> list[str]:
    """Return the plan's decision-discipline violations for ``report`` (empty = clean)."""
    problems = []
    nv = report.numerical_verification
    if nv and not nv.get("ok", True):
        problems.append("headline depends on a numerically unvalidated regime (ledger/convergence not OK)")
    worst = max((float(v) for k, v in nv.items() if k.endswith("_residual") and v is not None),
                default=0.0)
    if worst > residual_tol:
        problems.append(f"conservation residual {worst:.2e} exceeds {residual_tol:.0e}")
    if report.robustness.structure_agreement is not None and report.robustness.structure_agreement < 0.5 \
            and report.tier is not EvidenceTier.CONCEPTUAL_DEMONSTRATION:
        problems.append("model classes disagree on most of the posterior; conclusion is structure-sensitive, "
                        "cannot be called necessary")
    if report.tier is EvidenceTier.REPRODUCTION and not report.feasibility.admissibility:
        problems.append("reproduction tier claimed without a stated conditioning set")
    return problems


__all__ = ["EvidenceTier", "verdict_language", "Feasibility", "Robustness", "Discrimination",
           "TransitionReport", "decision_discipline"]
