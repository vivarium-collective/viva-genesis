"""Heredity module family — information, replication fidelity and the error threshold.

Covers the chemistry→heredity transition (Module J): whether an inherited (replicable)
polymer state improves lineage persistence/throughput despite replication fidelity and
cost — the Eigen quasispecies error threshold — comparing heredity modules head-to-head.
"""

from .replicator import HeredityReplicatorProcess  # noqa: E402,F401
from .lineage import LineageReplicatorProcess  # noqa: E402,F401

__all__ = ["HeredityReplicatorProcess", "LineageReplicatorProcess"]
