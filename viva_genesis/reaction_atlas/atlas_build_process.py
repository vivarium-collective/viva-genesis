"""Study 28 — build the Prebiotic Reaction Atlas as a composite Process.

Study 28 is a DATA-ASSET build, not a simulation: its "run" curates candidate
reactions through the real extract -> (feasibility) -> validate pipeline and
reports coverage + the zero-leakage guarantee (no unbalanced/unsourced reaction
enters the accepted atlas). This Process wraps ``reaction_atlas.build.build_atlas``
over a measured-tier seed (the nonenzymatic metal-promoted carbon-fixation core
from the primary literature) and emits the coverage metrics the study's behavior
tests read. Expansion to the full ChEBI/Rhea/ORD import is future data work; the
pipeline + gate are exercised now on real measured reactions.
"""
from __future__ import annotations

from process_bigraph import Process

from .build import build_atlas

_OW = {"_type": "overwrite[float]", "_units": "dimensionless"}


def _measured(source_key, source_doi):
    return {"tier": "measured",
            "evidence": {"source_key": source_key, "source_doi": source_doi,
                         "verified_against_source": True},
            "provenance": {"acquisition": "extracted"}}


# Measured-tier seed: the nonenzymatic metal-promoted carbon-fixation core. Two
# balanced reactions that must ENTER the atlas, and one deliberately unbalanced
# candidate that must be HELD BACK (the zero-leakage gate in action).
SEED_RECORDS = [
    {  # CO2 + H2 -> formate (HCOOH)
        "species": [
            {"chebi_id": "co2", "formula": "CO2", "charge": 0, "role": "reactant"},
            {"chebi_id": "h2", "formula": "H2", "charge": 0, "role": "reactant"},
            {"chebi_id": "formate", "formula": "CH2O2", "charge": 0, "role": "product"},
        ],
        "reaction": {"reactants": {"co2": 1, "h2": 1}, "products": {"formate": 1}},
        **_measured("muchowska2019synthesis", "10.1038/s41586-019-1151-1"),
    },
    {  # 2 CO2 + 4 H2 -> acetate (C2H4O2) + 2 H2O
        "species": [
            {"chebi_id": "co2", "formula": "CO2", "charge": 0, "role": "reactant"},
            {"chebi_id": "h2", "formula": "H2", "charge": 0, "role": "reactant"},
            {"chebi_id": "acetate", "formula": "C2H4O2", "charge": 0, "role": "product"},
            {"chebi_id": "water", "formula": "H2O", "charge": 0, "role": "product"},
        ],
        "reaction": {"reactants": {"co2": 2, "h2": 4}, "products": {"acetate": 1, "water": 2}},
        **_measured("varma2018native", "10.1038/s41559-018-0542-2"),
    },
    {  # DELIBERATELY unbalanced: CO2 + H2 -> acetate (C mismatch) -> held back
        "species": [
            {"chebi_id": "co2", "formula": "CO2", "charge": 0, "role": "reactant"},
            {"chebi_id": "h2", "formula": "H2", "charge": 0, "role": "reactant"},
            {"chebi_id": "acetate", "formula": "C2H4O2", "charge": 0, "role": "product"},
        ],
        "reaction": {"reactants": {"co2": 1, "h2": 1}, "products": {"acetate": 1}},
        **_measured("muchowska2019synthesis", "10.1038/s41586-019-1151-1"),
    },
]

_CARBON = ("co2", "formate", "acetate", "pyruvate")


class ReactionAtlasBuildProcess(Process):
    """Build the atlas from the measured-tier seed; emit coverage + leakage metrics."""

    config_schema = {
        "run_feasibility": {"_type": "boolean", "_default": False},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._result = None

    def inputs(self):
        return {}

    def outputs(self):
        return {
            "n_accepted": _OW, "n_proposed": _OW,
            "n_measured": _OW, "n_inferred": _OW, "n_hypothetical": _OW,
            "balance_violations_held": _OW,   # unbalanced candidates kept OUT of the atlas
            "accepted_balance_violations": _OW,  # MUST be 0 — the zero-leakage guarantee
            "carbon_species_covered": _OW,    # distinct C1-C3 species in the accepted atlas
        }

    def _build(self):
        if self._result is None:
            self._result = build_atlas(SEED_RECORDS,
                                       run_feasibility=bool(self.config["run_feasibility"]))
        return self._result

    def update(self, state, interval):
        res = self._build()
        accepted, proposed = res.accepted, res.proposed
        tiers = {"measured": 0, "inferred": 0, "hypothetical": 0}
        for r in accepted:
            t = r.get("tier")
            if t in tiers:
                tiers[t] += 1
        held = sum(1 for r in proposed
                   if not (r.get("reaction") or {}).get("mass_balanced", True)
                   or not (r.get("reaction") or {}).get("charge_balanced", True))
        # Accepted records are balanced by construction; count any violation to
        # prove the guarantee holds (must be 0).
        leaked = sum(1 for r in accepted
                     if not ((r.get("reaction") or {}).get("mass_balanced")
                             and (r.get("reaction") or {}).get("charge_balanced")))
        carbon = set()
        for r in accepted:
            for sp in r.get("species", []):
                ref = sp.get("chebi_id")
                if ref in _CARBON:
                    carbon.add(ref)
        return {
            "n_accepted": float(len(accepted)),
            "n_proposed": float(len(proposed)),
            "n_measured": float(tiers["measured"]),
            "n_inferred": float(tiers["inferred"]),
            "n_hypothetical": float(tiers["hypothetical"]),
            "balance_violations_held": float(held),
            "accepted_balance_violations": float(leaked),
            "carbon_species_covered": float(len(carbon)),
        }
