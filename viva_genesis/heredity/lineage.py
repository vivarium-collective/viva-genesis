"""Module K — heredity as an agent-based LINEAGE, not a mean-field concentration.

The og-06 mean-field quasispecies (``HeredityReplicatorProcess``) tracks *populations*
of correct vs error templates — it has no individuals and no ancestry, so it cannot
ask the question the campaign actually poses: does an inherited *chemical phenotype*
persist DOWN A LINEAGE, and is heredity necessarily a long high-fidelity template?

This module simulates **individuals that divide into a real lineage tree**. Each
agent carries a chemical phenotype inherited at fission with a MODULE-SPECIFIC
mechanism, so competing heredity modules are compared on the same substrate (the
study's "do NOT presume RNA"):

  - **template** (RNA-like): a sequence of ``length`` sites; function ``phi`` = the
    fraction correct. Replication copies each correct site, which stays correct with
    probability ``per_site_fidelity`` (no back-mutation) — the Eigen ratchet. Whole-
    sequence fidelity ``Q = per_site_fidelity ** length``. A long, high-fidelity
    template retains information but pays a cost ∝ length; drop below the error
    threshold and the lineage ratchets down to noise (the error catastrophe).
  - **compositional** (GARD, Segré 2000; **no template**): a composition vector over
    ``K`` catalyst types. An autocatalytic matrix grows the types the current
    composition catalyses; fission splits molecules multinomially → composition
    drift. Function = similarity to the mutually-autocatalytic attractor. Inheritance
    is of *composition*, length-independent — it escapes the Eigen length catastrophe.
  - **hybrid** (template-assisted composition): a SHORT template whose fidelity
    *focuses* the autocatalytic matrix, damping split drift. Cheap like composition,
    heritable like a template.
  - **non-heritable** control: daughters get a fresh random phenotype — no inheritance.

Every agent ever born is a tree node (id, parent, birth generation, phenotype,
alive). Parent↔offspring phenotype pairs give the *realized heritability* — the
signature that distinguishes true inheritance (slope ≈ 1) from the non-heritable
control (slope ≈ 0). Seeded RNG → reproducible.
"""
from __future__ import annotations

import numpy as np
from process_bigraph import Process

_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_COUNT = {"_type": "integer", "_units": "dimensionless"}

K_TYPES = 6          # catalyst types (compositional / hybrid composition vector)
N_MOL = 40           # molecules per compositional cell — sets the fission split-noise scale
MODULES = ("template", "compositional", "hybrid", "non-heritable")


def _attractor(k: int = K_TYPES) -> np.ndarray:
    """The single mutually-autocatalytic attractor composition — the 'functional' profile
    the compositional lineage must hold against split drift."""
    a = np.zeros(k)
    a[:3] = 1.0
    return a / a.sum()


def _catalytic_matrix(k: int, focus: float) -> np.ndarray:
    """Autocatalytic growth matrix: a diffuse background of mutual catalysis plus a
    ``focus``-weighted block among the attractor types (hybrid raises ``focus`` via its
    template, sharpening the attractor)."""
    a = _attractor(k)
    m = 0.15 * np.ones((k, k))
    m += focus * np.outer(a > 0, a > 0).astype(float)
    return m


def _phi_template(correct: int, length: int) -> float:
    return correct / max(length, 1)


def _phi_comp(counts: np.ndarray, attractor: np.ndarray) -> float:
    c = counts / max(counts.sum(), 1e-9)
    return float(np.dot(c, attractor) / (np.linalg.norm(c) * np.linalg.norm(attractor) + 1e-12))


class _Population:
    """A lineage population advanced one generation per :meth:`step`. Holds the live
    agents (phenotype + resource), the growing tree of all nodes, and the
    parent↔offspring phenotype pairs for heritability. One heredity module per run."""

    def __init__(self, module, *, per_site_fidelity, length, benefit, cost_scale,
                 division_threshold, capacity, focus_hybrid, seed):
        self.module = module if module in MODULES else "template"
        self.f = float(per_site_fidelity)
        self.L = max(int(length), 1)
        self.Lh = max(self.L // 6, 4)                 # short template for hybrid
        self.benefit = float(benefit)
        self.cost_scale = float(cost_scale)
        self.div = float(division_threshold)
        self.capacity = int(capacity)
        self.focus_hybrid = float(focus_hybrid)
        self.rng = np.random.default_rng(int(seed))
        self.attractor = _attractor(K_TYPES)
        self.nodes: list[dict] = []
        self.po_pairs: list[tuple[float, float]] = []
        self._nid = 0
        self.gen = 0
        self.pop: list[dict] = []
        self._seed_founders()

    # -- complexity (maintenance cost driver) differs by module ------------------
    def _complexity(self) -> float:
        if self.module == "hybrid":
            return self.Lh + 0.4 * K_TYPES
        if self.module == "compositional":
            return float(K_TYPES)
        return float(self.L)                          # template + non-heritable

    def _new_phenotype_functional(self) -> tuple[dict, float]:
        if self.module in ("template", "non-heritable"):
            correct = int(round(0.95 * self.L))
            ph = {"correct": correct}
            phi = _phi_template(correct, self.L)
        else:
            counts = np.zeros(K_TYPES)
            idx = np.where(self.attractor > 0)[0]
            counts[idx] = N_MOL / len(idx)
            ph = {"counts": counts}
            phi = _phi_comp(counts, self.attractor)
        if self.module == "hybrid":
            ph["tcorrect"] = int(round(0.95 * self.Lh))
        return ph, phi

    def _seed_founders(self, n: int = 12) -> None:
        for _ in range(n):
            ph, phi = self._new_phenotype_functional()
            self._add(self.pop, parent=-1, ph=ph, phi=phi, r=0.3)

    def _add(self, dest: list, *, parent, ph, phi, r) -> dict:
        """Create an agent, record its tree node, and append it to ``dest``. ``dest``
        is explicit so births during a generation go to a NEW list — never the live
        population being iterated in :meth:`step` (which would never terminate)."""
        a = {"id": self._nid, "parent": parent, "gen": self.gen, "r": r,
             "phi": phi, "ph": ph, "alive": True}
        dest.append(a)
        self.nodes.append({"id": self._nid, "parent": parent, "gen": self.gen,
                           "phi": round(phi, 4)})
        self._nid += 1
        return a

    def _inherit(self, parent: dict) -> tuple[dict, float]:
        """Produce a daughter phenotype from ``parent`` under the module's fidelity."""
        ph = parent["ph"]
        if self.module == "template":
            dc = int(self.rng.binomial(ph["correct"], self.f))     # Eigen ratchet, no back-mutation
            return {"correct": dc}, _phi_template(dc, self.L)
        if self.module == "non-heritable":
            dc = int(self.rng.binomial(self.L, 0.5))               # fresh random — inheritance severed
            return {"correct": dc}, _phi_template(dc, self.L)
        # compositional / hybrid: autocatalytic growth then multinomial fission split
        counts = ph["counts"]
        focus = 0.6
        if self.module == "hybrid":
            focus = 0.6 + self.focus_hybrid * (ph["tcorrect"] / max(self.Lh, 1))
        m = _catalytic_matrix(K_TYPES, focus)
        c = counts / max(counts.sum(), 1e-9)
        rates = np.maximum(m @ c, 0.0) * c                          # present types self-amplify
        rates = rates / max(rates.sum(), 1e-9)
        grown = counts + N_MOL * rates
        p = grown / max(grown.sum(), 1e-9)
        dcounts = self.rng.multinomial(N_MOL, p).astype(float)      # fission split → drift
        dph = {"counts": dcounts}
        if self.module == "hybrid":
            dph["tcorrect"] = int(self.rng.binomial(ph["tcorrect"], self.f))
        return dph, _phi_comp(dcounts, self.attractor)

    def step(self) -> dict:
        """Advance one generation: grow, divide into the tree, die, then cull to the
        carrying capacity (selection-weighted global competition). Returns the
        generation's population summary."""
        self.gen += 1
        complexity = self._complexity()
        nextpop: list[dict] = []                                    # survivors + this gen's births
        for a in list(self.pop):                                    # snapshot: births go to nextpop
            a["r"] += self.benefit * a["phi"] - self.cost_scale * complexity
            if a["r"] <= 0.0 or self.rng.random() < (0.02 + 0.25 * (1.0 - a["phi"])):
                continue                                            # death (starve / non-functional)
            if a["r"] >= self.div:
                a["r"] = 0.0
                for _ in range(2):
                    dph, dphi = self._inherit(a)
                    self._add(nextpop, parent=a["id"], ph=dph, phi=dphi, r=0.3)
                    self.po_pairs.append((a["phi"], dphi))
            else:
                nextpop.append(a)
        self.pop = nextpop
        if len(self.pop) > self.capacity:
            w = np.array([max(x["phi"], 1e-6) for x in self.pop])
            keep = set(int(i) for i in self.rng.choice(
                len(self.pop), size=self.capacity, replace=False, p=w / w.sum()))
            self.pop = [x for i, x in enumerate(self.pop) if i in keep]
        return self.summary()

    def summary(self) -> dict:
        if not self.pop:
            return {"generation": self.gen, "population": 0, "mean_function": 0.0,
                    "functional_fraction": 0.0, "heritability": self.heritability(),
                    "lineage_depth": self.gen}
        phis = np.array([x["phi"] for x in self.pop])
        return {"generation": self.gen, "population": len(self.pop),
                "mean_function": float(phis.mean()),
                "functional_fraction": float((phis > 0.5).mean()),
                "heritability": self.heritability(),
                "lineage_depth": self.gen}

    def heritability(self) -> float:
        """Realized heritability = slope of offspring φ on parent φ (≈1 inheritance,
        ≈0 non-heritable control)."""
        if len(self.po_pairs) <= 10:
            return float("nan")
        pp = np.asarray(self.po_pairs)
        if pp[:, 0].std() <= 1e-6:
            return float("nan")
        return float(np.polyfit(pp[:, 0], pp[:, 1], 1)[0])


def simulate_lineage(module="template", *, per_site_fidelity=0.98, length=30,
                     benefit=1.0, cost_scale=0.012, division_threshold=1.0,
                     capacity=220, n_gen=40, seed=0, focus_hybrid=0.9) -> dict:
    """Run a whole lineage headless (for the Decision-view sweep). Returns the tree
    nodes, the per-generation series, the realized heritability and final scalars."""
    pop = _Population(module, per_site_fidelity=per_site_fidelity, length=length,
                      benefit=benefit, cost_scale=cost_scale,
                      division_threshold=division_threshold, capacity=capacity,
                      focus_hybrid=focus_hybrid, seed=seed)
    series = []
    for _ in range(int(n_gen)):
        series.append(pop.step())
        if series[-1]["population"] == 0:
            break
    final = series[-1] if series else {"mean_function": 0.0, "population": 0}
    return {"nodes": pop.nodes, "series": series, "heritability": pop.heritability(),
            "po_pairs": pop.po_pairs, "final_function": final["mean_function"],
            "final_population": final["population"], "n_nodes": len(pop.nodes)}


class LineageReplicatorProcess(Process):
    """Agent-based heredity lineage: individuals carry a chemical phenotype inherited
    at fission with a module-specific mechanism (template Eigen ratchet / compositional
    GARD split / template-focused hybrid / severed non-heritable control), dividing into
    a real lineage tree. Advances ONE generation per tick and emits the population's
    mean function, functional fraction, size, lineage depth and realized heritability
    (overwrite sensors). ``lineage_state()`` exposes the tree for the Decision view.

    This is a coarse-grained agent-based reproduction (the study's proposed primary
    method — SSA/agent heredity with explicit fidelity/cost/competition), not a wrapped
    ALife engine, and is labelled as such."""

    contract = {
        "summary": "Agent-based heredity lineage — individuals inherit a chemical phenotype at fission into a real lineage tree; template / compositional / hybrid / non-heritable modules compared on realized heritability + functional persistence.",
        "description": (
            "Simulates individuals that divide into a lineage tree, each carrying a "
            "chemical phenotype inherited with a MODULE-SPECIFIC mechanism: a template "
            "Eigen ratchet (correct sites stay correct w.p. per_site_fidelity, Q=f^length), "
            "a compositional GARD split (multinomial fission of an autocatalytic composition "
            "vector — length-independent), a template-focused hybrid, or a severed "
            "non-heritable control. Advances one generation per tick; emits population mean "
            "function, functional fraction, size, lineage depth and the realized heritability "
            "(offspring↔parent φ slope). Reproduces the Eigen error catastrophe at the agent "
            "level AND shows compositional heredity escaping the length catastrophe."
        ),
        "inputs": {"temperature": "temperature (K; Arrhenius window on the replication benefit)"},
        "outputs": {
            "mean_function": "population mean phenotype function φ (dimensionless, 0-1)",
            "functional_fraction": "fraction of the live population above the functional threshold (dimensionless)",
            "population": "live population size (integer)",
            "lineage_depth": "deepest lineage generation reached (integer)",
            "heritability": "realized heritability — offspring↔parent φ regression slope (dimensionless)",
        },
        "assumptions": [
            "Coarse-grained agent-based reproduction (the proposed primary method; not a wrapped ALife engine).",
            "Template inheritance ratchets (Eigen, no back-mutation); compositional inheritance drifts by multinomial fission (GARD).",
            "Selection-weighted carrying capacity (global competition / dilution); seeded RNG → reproducible.",
        ],
        "math": [
            "template: daughter correct ~ Binomial(parent_correct, per_site_fidelity); Q = f^length",
            "compositional: daughter counts ~ Multinomial(N, grown/Σgrown); φ = cos(composition, attractor)",
            "heritability = slope(offspring_φ ~ parent_φ)",
        ],
        "symbols": {"phi": "phenotype function (0-1)", "Q": "whole-sequence fidelity f^L",
                    "N": "molecules per compositional cell", "focus": "hybrid attractor sharpening"},
        "references": ["segre2000compositional", "huber1998peptides", "sutherland2017opinion"],
    }

    config_schema = {
        "module": {"_type": "string", "_default": "template"},
        "per_site_fidelity": {"_type": "float", "_default": 0.99, "_units": "dimensionless"},
        "length": {"_type": "integer", "_default": 30, "_units": "dimensionless"},
        "benefit": {"_type": "float", "_default": 1.0, "_units": "dimensionless"},
        "cost_scale": {"_type": "float", "_default": 0.012, "_units": "dimensionless"},
        "division_threshold": {"_type": "float", "_default": 1.0, "_units": "dimensionless"},
        "capacity": {"_type": "integer", "_default": 220, "_units": "dimensionless"},
        "focus_hybrid": {"_type": "float", "_default": 0.9, "_units": "dimensionless"},
        "seed": {"_type": "integer", "_default": 1, "_units": "dimensionless"},
        "t_opt": {"_type": "float", "_default": 353.15, "_units": "kelvin"},
        "t_width": {"_type": "float", "_default": 80.0, "_units": "kelvin"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._pop = None

    def inputs(self):
        return {"temperature": {"_type": "float", "_units": "kelvin"}}

    def outputs(self):
        return {
            "mean_function": {"_type": "overwrite[float]", "_units": "dimensionless"},
            "functional_fraction": {"_type": "overwrite[float]", "_units": "dimensionless"},
            "population": {"_type": "overwrite[integer]", "_units": "dimensionless"},
            "lineage_depth": {"_type": "overwrite[integer]", "_units": "dimensionless"},
            "heritability": {"_type": "overwrite[float]", "_units": "dimensionless"},
        }

    def initial_state(self):
        return {"temperature": 353.15}

    def _ensure(self):
        if self._pop is None:
            c = self.config
            self._pop = _Population(
                str(c["module"]), per_site_fidelity=float(c["per_site_fidelity"]),
                length=int(c["length"]), benefit=float(c["benefit"]),
                cost_scale=float(c["cost_scale"]), division_threshold=float(c["division_threshold"]),
                capacity=int(c["capacity"]), focus_hybrid=float(c["focus_hybrid"]),
                seed=int(c["seed"]))

    def update(self, state, interval):
        import math
        self._ensure()
        # Arrhenius-like window: outside the vent band the replication benefit falls off,
        # slowing growth (temperature enters the SAME benefit the phenotype earns).
        temp_k = float(state.get("temperature", 353.15))
        t_opt, t_w = float(self.config["t_opt"]), max(float(self.config["t_width"]), 1.0)
        self._pop.benefit = float(self.config["benefit"]) * math.exp(-((temp_k - t_opt) ** 2) / (2.0 * t_w ** 2))
        s = self._pop.step()
        return {"mean_function": s["mean_function"],
                "functional_fraction": s["functional_fraction"],
                "population": int(s["population"]),
                "lineage_depth": int(s["lineage_depth"]),
                "heritability": 0.0 if s["heritability"] != s["heritability"] else s["heritability"]}

    def lineage_state(self) -> dict:
        """The accumulated lineage tree + heritability pairs for the viz — every node a
        real agent (id, parent, birth generation, phenotype φ)."""
        self._ensure()
        return {"module": self._pop.module, "nodes": self._pop.nodes,
                "po_pairs": [[round(p, 4), round(o, 4)] for p, o in self._pop.po_pairs],
                "heritability": self._pop.heritability()}
