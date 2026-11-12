"""Per-run checks for propagule-toughness-predicted. The cross-run monotonic claim is
the study outcome (cross_run), not asserted here."""


def test_cohesive_at_strong_adhesion(runs):
    r = runs
    adhesion = float(r.params["adhesion"])
    if adhesion >= 0.9:
        assert r.final("n_propagules") == 1
    if adhesion <= 0.1:  # zero-adhesion negative control
        assert r.final("largest_cluster_fraction") < 0.5
