"""Campaign UQ layer: LHS sampling from a package, Morris + Sobol on the Ishigami
function, ABC-rejection conditioning, the Feasibility / Robustness /
Discrimination report triple and the decision-discipline audit."""

from __future__ import annotations

import numpy as np
import pytest

from viva_genesis import provenance as P
from viva_genesis import uq
from viva_genesis.uq import calibration as C
from viva_genesis.uq import report as R
from viva_genesis.uq import sensitivity as S


def _pkg():
    return P.ParameterPackage.from_dict({
        "name": "toy", "parameters": [
            {"id": "a", "units": "dimensionless", "provenance": "measured",
             "distribution": {"kind": "uniform", "low": 0.0, "high": 1.0}},
            {"id": "b", "units": "dimensionless", "provenance": "hypothetical",
             "distribution": {"kind": "loguniform", "low": 1e-2, "high": 1.0}},
            {"id": "c", "units": "kelvin", "provenance": "inferred", "value": 300.0},
        ]})


def test_lhs_sampling_stratifies_each_free_parameter():
    draws = uq.sample_package(_pkg(), 20, np.random.default_rng(0))
    a = np.array([d["a"] for d in draws])
    # one point per stratum of width 1/20
    assert sorted(np.floor(a * 20).astype(int)) == list(range(20))
    assert all(d["c"] == 300.0 for d in draws)
    assert all(1e-2 <= d["b"] <= 1.0 for d in draws)


def _ishigami(x, a=7.0, b=0.1):
    return np.sin(x["x1"]) + a * np.sin(x["x2"]) ** 2 + b * x["x3"] ** 4 * np.sin(x["x1"])


_ISH_BOUNDS = {"x1": (-np.pi, np.pi), "x2": (-np.pi, np.pi), "x3": (-np.pi, np.pi)}


def test_morris_ranks_ishigami():
    res = S.morris(_ishigami, _ISH_BOUNDS, r=10, levels=4, rng=np.random.default_rng(3))
    assert res.n_evaluations == 10 * 4
    assert set(res.ranking) == {"x1", "x2", "x3"}
    # x2 (sin^2 with a=7) and x1 dominate; all mu_star finite and x3 is not the top-ranked one
    assert all(np.isfinite(res.mu_star[n]) for n in res.names)
    assert res.ranking[0] != "x3"


def test_sobol_matches_ishigami_analytic():
    # analytic (a=7, b=0.1): S1 = 0.3139, 0.4424, 0.0 ; ST = 0.5576, 0.4424, 0.2437
    res = S.sobol(_ishigami, _ISH_BOUNDS, n=2048, rng=np.random.default_rng(0), n_boot=20)
    assert res.n_evaluations == 2048 * 5
    assert abs(res.S1["x1"] - 0.3139) < 0.06
    assert abs(res.S1["x2"] - 0.4424) < 0.06
    assert abs(res.S1["x3"] - 0.0) < 0.06
    assert abs(res.ST["x3"] - 0.2437) < 0.06
    assert res.ST["x1"] > res.S1["x1"]          # x1 interacts with x3


def test_abc_rejection_and_requirements():
    obs = [C.Observation("T", "T", low=40, high=91), C.Observation("pH", "pH", low=9.0, high=10.8)]
    outcomes = [{"T": 50, "pH": 9.5}, {"T": 30, "pH": 9.5}, {"T": 60, "pH": 8.0}, {"T": float("nan"), "pH": 9.2}]
    abc = C.abc_rejection(outcomes, obs)
    assert abc.n_posterior == 1 and abc.mask.tolist() == [True, False, False, False]
    assert abc.per_observation == {"T": 2, "pH": 3}
    w = C.gaussian_weights(outcomes, [C.Observation("T", "T", low=40, high=91, mean=50, sd=5)])
    assert w[0] > w[2] > 0 and w[1] == 0.0 and w[3] == 0.0
    summ = C.posterior_summary([{"a": 1.0}, {"a": 3.0}], np.array([1.0, 1.0]))
    assert summ["a"]["mean"] == 2.0


def test_report_triple_and_decision_discipline():
    rep = R.TransitionReport(
        transition="toy", tier=R.EvidenceTier.MECHANISTIC_PREDICTION,
        feasibility=R.Feasibility(True, 10, 4, {"x": 1}, "T in window"),
        robustness=R.Robustness(0.4, {"a": 0.4, "b": 0.3}, 0.9, 0.1, 10, 20, "T"),
        discrimination=R.Discrimination(["b"], [{"readout": "T", "d": 1.2}], ["pH"]),
        numerical_verification={"ok": True, "mass_residual": 0.0},
    )
    d = rep.to_dict()
    assert d["language"] == "predicts under stated assumptions"
    assert "feasible=yes" in d["headline"] and "T (d=1.20)" in d["headline"]
    assert R.decision_discipline(rep) == []
    bad = R.TransitionReport("toy", R.EvidenceTier.REPRODUCTION,
                             R.Feasibility(True, 1, 1), R.Robustness(0.2, structure_agreement=0.3),
                             R.Discrimination(), numerical_verification={"ok": False, "mass_residual": 1e-3})
    problems = R.decision_discipline(bad)
    assert len(problems) == 4
    assert R.verdict_language("conceptual_demonstration") == "demonstrates in a coarse-grained model"
