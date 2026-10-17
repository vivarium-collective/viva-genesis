"""Explicit amphiphile chain-extension chemistry (study 17 REBUILD chemistry).

Replaces the lumped acetate+formate->one-amphiphile condensation with explicit
2-carbon fatty-acid elongation across MULTIPLE chain lengths, with degradation and
a length-dependent critical aggregation concentration (CAC falls as chains grow).
Decision test: reaches an aggregation-competent composition from the vent-carbon
feed ALONE (no exogenous amphiphile), with losses tracked.
"""
from process_bigraph import allocate_core
from viva_genesis.membranes.amphiphile_chain_extension import AmphiphileChainExtensionProcess


def _p(**cfg):
    return AmphiphileChainExtensionProcess(config=cfg, core=allocate_core())


def _run(p, acetate, n=40):
    out = {}
    for _ in range(n):
        out = p.update({"acetate": acetate, "temperature": 330.0}, 1.0)
    return out


def test_ports_named_distribution_outputs():
    p = _p()
    assert {"acetate", "temperature"} <= set(p.inputs())
    outs = set(p.outputs())
    assert {"mean_chain_length", "amphiphile_total", "long_chain_fraction",
            "aggregation_competent", "degradation_loss"} <= outs


def test_chain_extends_from_feed():
    p = _p(k_extend=0.4, k_seed=0.3)
    out = _run(p, acetate=2.0e-2)
    assert out["amphiphile_total"] > 0.0      # amphiphiles form from the feed
    assert out["mean_chain_length"] >= 4.0    # elongation beyond the C4 seed


def test_no_exogenous_feed_no_amphiphile():
    # No carbon feed -> no amphiphile forms (no exogenous amphiphile pool).
    p = _p(k_extend=0.4, k_seed=0.3)
    out = _run(p, acetate=0.0)
    assert out["amphiphile_total"] < 1e-9
    assert out["aggregation_competent"] <= 1e-9


def test_rich_feed_clears_cac_sparse_does_not():
    rich = _run(_p(k_extend=0.5, k_seed=0.4, k_degrade=0.02), acetate=5.0e-2)
    sparse = _run(_p(k_extend=0.5, k_seed=0.4, k_degrade=0.02), acetate=3.0e-4)
    # Under linear kinetics the chain-length-distribution SHAPE is feed-independent,
    # so long_chain_fraction is ~equal; the discriminator for clearing the CAC is the
    # ABSOLUTE long-chain concentration (scales with feed) vs the CAC.
    assert abs(rich["long_chain_fraction"] - sparse["long_chain_fraction"]) < 0.05
    assert rich["amphiphile_total"] > sparse["amphiphile_total"]
    # aggregation_competent = long-chain / CAC: >= 1 clears, < 1 stays sub-CAC.
    assert rich["aggregation_competent"] >= 1.0        # rich clears (competent)
    assert sparse["aggregation_competent"] < 1.0       # sparse stays below the CAC


def test_degradation_tracked():
    base = _run(_p(k_extend=0.5, k_seed=0.4, k_degrade=0.0), acetate=3.0e-2)
    leaky = _run(_p(k_extend=0.5, k_seed=0.4, k_degrade=0.3), acetate=3.0e-2)
    assert leaky["degradation_loss"] > base["degradation_loss"]
