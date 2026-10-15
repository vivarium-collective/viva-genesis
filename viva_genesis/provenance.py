"""vg-data — the machine-readable parameter-provenance layer.

Model Upgrade plan section 12: *a curated, machine-readable evidence layer sits
beside the simulation code; every numerical parameter carries value or
distribution, units, environmental context, source, and a provenance class:
measured, calibrated, inferred, extrapolated or hypothetical.*

This module is that layer's minimal core:

* :class:`Parameter` — one parameter record: ``value`` and/or a ``distribution``
  (``fixed | uniform | loguniform | normal | lognormal | triangular``), ``units``,
  ``context`` (T / pH / site / regime the value applies to), ``sources``
  (bibkeys in ``workspace/references/papers.bib``), ``provenance``
  (:class:`ProvenanceClass`), ``consumed_by`` (the process config key that reads
  it) and free-text ``how_to_use``. ``sample(rng, n)`` draws from the
  distribution; ``nominal()`` is the single value a canonical run uses.
* :class:`ParameterPackage` — a named, versioned set of parameters loaded from
  a YAML file (``viva_genesis/data/vg_data/*.yaml`` ships the packages the
  campaign calibrates against). ``audit()`` counts parameters per provenance
  class — the plan's "honesty indicator" — and ``to_config()`` maps nominal
  values onto a process ``config``/generator kwargs.

The older ``workspace/datasets/parameter-registry.yaml`` classes (FIELD,
LAB-DIRECT, LAB-ANALOG, MODEL, RECONSTRUCTION, HYPOTHESIS) are mapped onto the
plan's five classes by :data:`LEGACY_CLASS_MAP` so both vocabularies coexist.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np


class ProvenanceClass(str, Enum):
    """The plan's five provenance classes, in decreasing evidential strength."""

    MEASURED = "measured"          # a field or laboratory measurement of this quantity
    CALIBRATED = "calibrated"      # fit to observations through a model
    INFERRED = "inferred"          # derived from theory / other measured quantities
    EXTRAPOLATED = "extrapolated"  # measured elsewhere, carried outside its regime
    HYPOTHETICAL = "hypothetical"  # a proposition not yet independently constrained

    @classmethod
    def parse(cls, value: str | "ProvenanceClass") -> "ProvenanceClass":
        if isinstance(value, cls):
            return value
        key = str(value).strip()
        if key.upper() in LEGACY_CLASS_MAP:
            return LEGACY_CLASS_MAP[key.upper()]
        return cls(key.lower())


# parameter-registry.yaml vocabulary -> plan vocabulary
LEGACY_CLASS_MAP: dict[str, ProvenanceClass] = {
    "FIELD": ProvenanceClass.MEASURED,
    "LAB-DIRECT": ProvenanceClass.MEASURED,
    "LAB-ANALOG": ProvenanceClass.EXTRAPOLATED,
    "MODEL": ProvenanceClass.INFERRED,
    "RECONSTRUCTION": ProvenanceClass.INFERRED,
    "HYPOTHESIS": ProvenanceClass.HYPOTHETICAL,
}

_STRENGTH = {
    ProvenanceClass.MEASURED: 4,
    ProvenanceClass.CALIBRATED: 3,
    ProvenanceClass.INFERRED: 2,
    ProvenanceClass.EXTRAPOLATED: 1,
    ProvenanceClass.HYPOTHETICAL: 0,
}

DISTRIBUTION_KINDS = ("fixed", "uniform", "loguniform", "normal", "lognormal", "triangular")


@dataclass
class Distribution:
    """A one-dimensional prior.

    ``kind`` ∈ :data:`DISTRIBUTION_KINDS`; ``low``/``high`` bound the uniform,
    loguniform and triangular kinds (``mode`` for triangular); ``mean``/``sd``
    parameterise normal (in natural units) and lognormal (in log10 units, so
    ``mean`` is log10 of the median and ``sd`` is in decades).
    """

    kind: str = "fixed"
    low: float | None = None
    high: float | None = None
    mode: float | None = None
    mean: float | None = None
    sd: float | None = None

    def __post_init__(self):
        if self.kind not in DISTRIBUTION_KINDS:
            raise ValueError(f"unknown distribution kind {self.kind!r}; have {DISTRIBUTION_KINDS}")
        if self.kind in ("uniform", "loguniform", "triangular"):
            if self.low is None or self.high is None:
                raise ValueError(f"{self.kind} needs low and high")
            if not (self.high >= self.low):
                raise ValueError(f"{self.kind}: high ({self.high}) < low ({self.low})")
            if self.kind == "loguniform" and self.low <= 0:
                raise ValueError("loguniform needs low > 0")
            if self.kind == "triangular" and self.mode is None:
                self.mode = 0.5 * (self.low + self.high)
        if self.kind in ("normal", "lognormal") and (self.mean is None or self.sd is None):
            raise ValueError(f"{self.kind} needs mean and sd")

    def bounds(self) -> tuple[float | None, float | None]:
        if self.kind in ("uniform", "loguniform", "triangular"):
            return (self.low, self.high)
        if self.kind == "normal":
            return (self.mean - 3.0 * self.sd, self.mean + 3.0 * self.sd)
        if self.kind == "lognormal":
            return (10 ** (self.mean - 3.0 * self.sd), 10 ** (self.mean + 3.0 * self.sd))
        return (None, None)

    def ppf(self, u: np.ndarray) -> np.ndarray:
        """Inverse CDF on ``u ∈ [0, 1]`` — the hook the LHS / Sobol samplers use."""
        u = np.asarray(u, dtype=float)
        if self.kind == "uniform":
            return self.low + u * (self.high - self.low)
        if self.kind == "loguniform":
            return np.exp(np.log(self.low) + u * (np.log(self.high) - np.log(self.low)))
        if self.kind == "triangular":
            c = (self.mode - self.low) / max(self.high - self.low, 1e-300)
            left = self.low + np.sqrt(u * (self.high - self.low) * (self.mode - self.low))
            right = self.high - np.sqrt((1 - u) * (self.high - self.low) * (self.high - self.mode))
            return np.where(u < c, left, right)
        if self.kind in ("normal", "lognormal"):
            from scipy.special import ndtri
            z = ndtri(np.clip(u, 1e-12, 1 - 1e-12))
            if self.kind == "normal":
                return self.mean + self.sd * z
            return 10 ** (self.mean + self.sd * z)
        raise ValueError("a fixed distribution has no ppf; use Parameter.nominal()")

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class Parameter:
    """One provenance-carrying parameter (plan section 12)."""

    id: str
    units: str
    provenance: ProvenanceClass
    value: float | None = None
    distribution: Distribution | None = None
    context: dict = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    consumed_by: str | None = None       # e.g. "PhreeqcSerpentinizationProcess.olivine_rate"
    how_to_use: str = ""
    quantity: str = ""

    def __post_init__(self):
        self.provenance = ProvenanceClass.parse(self.provenance)
        if self.value is None and (self.distribution is None or self.distribution.kind == "fixed"):
            raise ValueError(f"parameter {self.id!r} has neither a value nor a sampling distribution")
        if self.distribution is None:
            self.distribution = Distribution(kind="fixed")

    @property
    def is_fixed(self) -> bool:
        return self.distribution.kind == "fixed"

    def nominal(self) -> float:
        """The single value a canonical run uses (value, or the distribution's centre)."""
        if self.value is not None:
            return float(self.value)
        d = self.distribution
        if d.kind == "uniform":
            return 0.5 * (d.low + d.high)
        if d.kind == "loguniform":
            return math.sqrt(d.low * d.high)
        if d.kind == "triangular":
            return float(d.mode)
        if d.kind == "normal":
            return float(d.mean)
        if d.kind == "lognormal":
            return float(10 ** d.mean)
        raise ValueError(f"cannot take a nominal of {d.kind}")

    def sample(self, rng: np.random.Generator, n: int = 1) -> np.ndarray:
        """Draw ``n`` values (a fixed parameter repeats its value)."""
        if self.is_fixed:
            return np.full(n, self.nominal())
        return self.distribution.ppf(rng.random(n))

    def bounds(self) -> tuple[float | None, float | None]:
        return self.distribution.bounds() if not self.is_fixed else (self.nominal(), self.nominal())

    def to_dict(self) -> dict:
        out = {"id": self.id, "units": self.units, "provenance": self.provenance.value}
        if self.quantity:
            out["quantity"] = self.quantity
        if self.value is not None:
            out["value"] = self.value
        if not self.is_fixed:
            out["distribution"] = self.distribution.to_dict()
        if self.context:
            out["context"] = dict(self.context)
        if self.sources:
            out["sources"] = list(self.sources)
        if self.consumed_by:
            out["consumed_by"] = self.consumed_by
        if self.how_to_use:
            out["how_to_use"] = self.how_to_use
        return out

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Parameter":
        dist = d.get("distribution")
        return cls(
            id=str(d["id"]),
            units=str(d.get("units", "dimensionless")),
            provenance=d.get("provenance", "hypothetical"),
            value=(float(d["value"]) if d.get("value") is not None else None),
            distribution=(Distribution(**dist) if isinstance(dist, Mapping) else None),
            context=dict(d.get("context") or {}),
            sources=list(d.get("sources") or d.get("refs") or []),
            consumed_by=d.get("consumed_by"),
            how_to_use=str(d.get("how_to_use", "")),
            quantity=str(d.get("quantity", "")),
        )


@dataclass
class ParameterPackage:
    """A named, versioned set of provenance-carrying parameters (one ``vg-data`` file)."""

    name: str
    parameters: dict[str, Parameter]
    version: str = "0"
    description: str = ""
    sources: list[str] = field(default_factory=list)
    observations: dict[str, dict] = field(default_factory=dict)

    # -- construction ------------------------------------------------------
    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "ParameterPackage":
        params = [Parameter.from_dict(p) for p in (d.get("parameters") or [])]
        return cls(
            name=str(d.get("name", "unnamed")),
            parameters={p.id: p for p in params},
            version=str(d.get("version", "0")),
            description=str(d.get("description", "")),
            sources=list(d.get("sources") or []),
            observations=dict(d.get("observations") or {}),
        )

    @classmethod
    def load(cls, path: str | Path) -> "ParameterPackage":
        import yaml
        with open(path, encoding="utf-8") as fh:
            return cls.from_dict(yaml.safe_load(fh) or {})

    def to_dict(self) -> dict:
        return {
            "name": self.name, "version": self.version, "description": self.description,
            "sources": list(self.sources),
            "parameters": [p.to_dict() for p in self.parameters.values()],
            "observations": dict(self.observations),
        }

    # -- access ------------------------------------------------------------
    def __getitem__(self, pid: str) -> Parameter:
        return self.parameters[pid]

    def __contains__(self, pid: str) -> bool:
        return pid in self.parameters

    def __iter__(self):
        return iter(self.parameters.values())

    def free(self) -> list[Parameter]:
        """Parameters with a sampling distribution (the uncertain ones)."""
        return [p for p in self.parameters.values() if not p.is_fixed]

    def nominal(self) -> dict[str, float]:
        return {pid: p.nominal() for pid, p in self.parameters.items()}

    def to_config(self, mapping: Mapping[str, str] | None = None,
                  values: Mapping[str, float] | None = None) -> dict[str, float]:
        """Map parameters onto config / generator kwargs.

        ``mapping`` is ``{parameter_id: config_key}``; when omitted the config
        key is the suffix of ``consumed_by`` after the last ``.`` (or the id).
        ``values`` overrides the nominal values (one ensemble draw).
        """
        values = dict(values or {})
        out = {}
        for pid, p in self.parameters.items():
            key = (mapping or {}).get(pid)
            if key is None:
                key = (p.consumed_by or pid).rsplit(".", 1)[-1]
            out[key] = float(values.get(pid, p.nominal()))
        return out

    def sample(self, rng: np.random.Generator, n: int) -> list[dict[str, float]]:
        """``n`` independent Monte-Carlo draws (``{parameter_id: value}`` each)."""
        draws = {pid: p.sample(rng, n) for pid, p in self.parameters.items()}
        return [{pid: float(draws[pid][i]) for pid in draws} for i in range(n)]

    # -- audit -------------------------------------------------------------
    def audit(self) -> dict:
        """Count parameters per provenance class + list the weakest ones.

        The plan's one-glance honesty indicator: how much of a stage rests on
        hypothetical or extrapolated numbers.
        """
        counts = {c.value: 0 for c in ProvenanceClass}
        for p in self.parameters.values():
            counts[p.provenance.value] += 1
        weakest = sorted(self.parameters.values(), key=lambda p: _STRENGTH[p.provenance])
        return {
            "n": len(self.parameters),
            "counts": counts,
            "n_free": len(self.free()),
            "hypothetical": [p.id for p in self.parameters.values()
                             if p.provenance is ProvenanceClass.HYPOTHETICAL],
            "extrapolated": [p.id for p in self.parameters.values()
                             if p.provenance is ProvenanceClass.EXTRAPOLATED],
            "weakest": [p.id for p in weakest[:3]],
            "unsourced": [p.id for p in self.parameters.values()
                          if not p.sources and p.provenance is not ProvenanceClass.HYPOTHETICAL],
        }


# --------------------------------------------------------------------------- #
# Packaged data (viva_genesis/data/vg_data/*.yaml)
# --------------------------------------------------------------------------- #
def data_dir() -> Path:
    return Path(__file__).resolve().parent / "data" / "vg_data"


def list_packages() -> list[str]:
    return sorted(p.stem for p in data_dir().glob("*.yaml"))


def load_package(name: str) -> ParameterPackage:
    """Load a packaged ``vg-data`` parameter set by file stem."""
    path = data_dir() / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"no vg-data package {name!r}; have {list_packages()}")
    return ParameterPackage.load(path)


def audit_config_schema(config_schema: Mapping[str, Any]) -> dict:
    """Audit a process ``config_schema`` for ``_provenance`` annotations.

    Returns ``{"declared": [...], "undeclared": [...], "counts": {...}}``. The
    plan asks every parameter of a canonical model to declare a provenance
    class; this is the check (advisory for legacy processes, enforced in tests
    for the new ones).
    """
    declared, undeclared = [], []
    counts = {c.value: 0 for c in ProvenanceClass}
    for key, spec in config_schema.items():
        if isinstance(spec, Mapping) and spec.get("_provenance"):
            declared.append(key)
            counts[ProvenanceClass.parse(spec["_provenance"]).value] += 1
        else:
            undeclared.append(key)
    return {"declared": declared, "undeclared": undeclared, "counts": counts}


def bibkeys(package: ParameterPackage) -> set[str]:
    """Every bibkey the package cites (to cross-check against papers.bib)."""
    keys: set[str] = set(package.sources)
    for p in package:
        keys.update(p.sources)
    for obs in package.observations.values():
        keys.update(obs.get("sources") or [])
    return keys


def check_bib(package: ParameterPackage, bib_path: str | Path) -> list[str]:
    """Return the package's bibkeys that are NOT in ``bib_path`` (empty = all cited)."""
    import re
    text = Path(bib_path).read_text(encoding="utf-8")
    present = set(re.findall(r"@\w+\{([A-Za-z0-9_:-]+),", text))
    return sorted(k for k in bibkeys(package) if k not in present)


__all__ = [
    "ProvenanceClass", "LEGACY_CLASS_MAP", "Distribution", "DISTRIBUTION_KINDS",
    "Parameter", "ParameterPackage", "data_dir", "list_packages", "load_package",
    "audit_config_schema", "bibkeys", "check_bib",
]
