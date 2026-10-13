"""Module J — heredity as a quasispecies replicator via the REAL libRoadRunner engine.

Campaign-VI transition: does an inherited (replicable) polymer state improve a
lineage's persistence/throughput despite replication fidelity and cost? This is the
Eigen quasispecies **error threshold**: a template of length L replicates with
whole-sequence fidelity Q = per_site_fidelity^L; correct copies (C) carry function,
mutational errors (E) do not and propagate. Above the threshold (Q high enough) the
functional information is retained; below it, errors win and information is lost
(the error catastrophe) — so inheritance only pays where fidelity beats the length.

``HeredityReplicatorProcess`` **drives the genuine libRoadRunner integrator** (via
tellurium ``te.loada``) on a logistic quasispecies ODE:

    C -> 2C   at krep·Q·C·(1 − (C+E)/K)      (correct replication)
    C -> E    at krep·(1 − Q)·C·(1 − (C+E)/K) (mutation to error)
    E -> 2E   at krep·qe·E·(1 − (C+E)/K)       (errors replicate, lower fidelity)
    C -> ∅, E -> ∅ at kdeg                      (degradation)

It emits the information retention C/(C+E), the functional template level, the
polymer length and the lineage fitness = benefit·(retention·C) − cost·krep (the
throughput of the retained function net of the replication budget). Different
heredity modules (RNA-like: long, high-fidelity, costly; peptide-assisted: short,
lower-fidelity, cheaper) are compared head-to-head; a non-heritable control
(krep=0) carries no inheritance.
"""
from __future__ import annotations

from process_bigraph import Process

_K = {"_type": "float", "_units": "kelvin"}
_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_COUNT = {"_type": "integer", "_units": "dimensionless"}

# Logistic quasispecies (Eigen) — correct (C) vs error (E) templates. Q (whole-
# sequence fidelity) and krep are set from config each build.
_MODEL = """
model heredity
  Rrep: C -> 2 C; krep*Q*C*(1 - (C+E)/K);
  Rmut: C -> E;   krep*(1-Q)*C*(1 - (C+E)/K);
  Rerr: E -> 2 E; krep*qe*E*(1 - (C+E)/K);
  DdC:  C -> ;    kdeg*C;
  DdE:  E -> ;    kdeg*E;
  Q = 0.7; qe = 0.5; krep = 1.0; kdeg = 0.1; K = 1.0;
  C = 0.05; E = 0.0;
end
"""


class HeredityReplicatorProcess(Process):
    """Real libRoadRunner quasispecies replicator for the Eigen error threshold.
    Reads temperature (Arrhenius on the replication rate); advances the genuine
    SBML ODE each tick; and emits the information retention, functional template
    level, polymer length and lineage fitness (overwrite sensors — the current
    population state). A heredity MODULE is a (fidelity, length, rate, cost) set;
    the non-heritable control sets krep=0."""

    contract = {
        "summary": "Real libRoadRunner quasispecies replicator (Eigen error threshold): does inherited polymer state improve fitness despite fidelity + cost? Heredity modules compared head-to-head.",
        "description": (
            "Drives the genuine libRoadRunner integrator on a logistic quasispecies ODE "
            "(correct templates C vs mutational errors E; whole-sequence fidelity "
            "Q = per_site_fidelity^length). Emits information retention C/(C+E), the "
            "functional template level, polymer length and lineage fitness = "
            "benefit*(retention*C) - cost*krep. Above the error threshold the functional "
            "information is retained and inheritance pays; below it errors win (catastrophe). "
            "RNA-like (long, high-fidelity, costly) vs peptide-assisted (short, cheaper, "
            "lower-fidelity) are compared; krep=0 is the non-heritable control."
        ),
        "inputs": {"temperature": "temperature (K; Arrhenius on replication rate)"},
        "outputs": {
            "information_retention": "C/(C+E) — functional-information retention (dimensionless, 0-1)",
            "functional_templates": "correct template level C (dimensionless)",
            "polymer_length": "heredity-module polymer length (integer)",
            "lineage_fitness": "benefit*(retention*C) - cost*krep (dimensionless)",
        },
        "assumptions": [
            "Eigen quasispecies error threshold: whole-sequence fidelity Q = per_site_fidelity^length.",
            "Logistic carrying capacity bounds growth; errors replicate with reduced fidelity qe.",
            "Lineage fitness nets the retained functional throughput against the replication budget.",
        ],
        "math": [
            "Q = per_site_fidelity ^ polymer_length",
            "dC/dt = krep*Q*C*(1-(C+E)/K) - kdeg*C ;  dE/dt = krep*(1-Q)*C*(..) + krep*qe*E*(..) - kdeg*E",
            "lineage_fitness = benefit*(C/(C+E))*C - cost*krep",
        ],
        "symbols": {"Q": "whole-sequence fidelity", "qe": "error-copy fidelity", "krep": "replication rate", "K": "carrying capacity"},
        "references": ["huber1998peptides", "muchowska2019synthesis", "sutherland2017opinion"],
    }

    config_schema = {
        "per_site_fidelity": {"_type": "float", "_default": 0.99, "_units": "dimensionless"},
        "polymer_length": {"_type": "integer", "_default": 30, "_units": "dimensionless"},
        "k_rep": {"_type": "float", "_default": 1.0, "_units": "1/second"},
        "k_deg": {"_type": "float", "_default": 0.1, "_units": "1/second"},
        "error_fidelity": {"_type": "float", "_default": 0.06, "_units": "dimensionless"},
        "capacity": {"_type": "float", "_default": 1.0, "_units": "dimensionless"},
        "benefit": {"_type": "float", "_default": 1.6, "_units": "dimensionless"},
        "cost_per_rep": {"_type": "float", "_default": 0.10, "_units": "dimensionless"},
        "t_opt": {"_type": "float", "_default": 353.15, "_units": "kelvin"},
        "t_width": {"_type": "float", "_default": 60.0, "_units": "kelvin"},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._rr = None

    def inputs(self):
        return {"temperature": _K}

    def outputs(self):
        return {
            "information_retention": {"_type": "overwrite[float]", "_units": "dimensionless"},
            "functional_templates": {"_type": "overwrite[float]", "_units": "dimensionless"},
            "polymer_length": {"_type": "overwrite[integer]", "_units": "dimensionless"},
            "lineage_fitness": {"_type": "overwrite[float]", "_units": "dimensionless"},
        }

    def initial_state(self):
        return {"temperature": 353.15}

    def _build(self, krep_eff):
        import tellurium as te
        rr = te.loada(_MODEL)
        L = max(int(self.config["polymer_length"]), 1)
        rr.Q = float(self.config["per_site_fidelity"]) ** L          # whole-sequence fidelity
        rr.qe = float(self.config["error_fidelity"])
        rr.krep = krep_eff
        rr.kdeg = float(self.config["k_deg"])
        rr.K = float(self.config["capacity"])
        self._rr = rr

    def update(self, state, interval):
        import math
        temp_k = float(state.get("temperature", 353.15))
        # Arrhenius-like temperature window on the replication rate.
        t_opt, t_w = float(self.config["t_opt"]), max(float(self.config["t_width"]), 1.0)
        t_window = math.exp(-((temp_k - t_opt) ** 2) / (2.0 * t_w ** 2))
        krep_eff = float(self.config["k_rep"]) * t_window

        if self._rr is None:
            self._build(krep_eff)
        else:
            self._rr.krep = krep_eff
        self._rr.simulate(0, max(interval, 1e-3), 2)

        C = max(float(self._rr.C), 0.0)
        E = max(float(self._rr.E), 0.0)
        retention = C / (C + E) if (C + E) > 1e-30 else 0.0
        L = max(int(self.config["polymer_length"]), 1)
        fitness = (float(self.config["benefit"]) * retention * C
                   - float(self.config["cost_per_rep"]) * float(self.config["k_rep"]))

        return {
            "information_retention": retention,
            "functional_templates": C,
            "polymer_length": L,
            "lineage_fitness": fitness,
        }
