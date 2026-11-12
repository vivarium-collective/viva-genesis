"""S05 differentiation composite: O2 gradient drives interior germ -> soma."""
import pytest

pytest.importorskip("viva_cpm")

from process_bigraph import Composite  # noqa: E402

from viva_genesis.core import build_core  # noqa: E402

GEN_ID = "viva_genesis.composites.multicellularity_world.s05_differentiation"
GRID = 5
IDS = [i * GRID + j + 1 for i in range(GRID) for j in range(GRID)]   # cell id = seed order + 1
INTERIOR = [i * GRID + j + 1 for i in range(1, GRID - 1) for j in range(1, GRID - 1)]
RIM = [c for c in IDS if c not in INTERIOR]
N_UPDATES = 40


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs)


def _build(**kw):
    from viva_genesis.composites.multicellularity_world import s05_differentiation
    core = build_core()
    return Composite({"state": s05_differentiation(core, **kw)}, core=core)


@pytest.fixture(scope="module")
def run():
    comp = _build()
    comp.run(1)
    start = {"vol": list(comp.state["volumes"]), "biomass": comp.state["viable_biomass"],
             "o2": dict(comp.state["field_at_cell"])}
    history = []
    for _ in range(N_UPDATES - 1):
        comp.run(1)
        history.append(dict(comp.state["fate_counts"]))
    return comp, start, history


def test_register_id():
    import viva_genesis  # noqa: F401
    from process_bigraph import composite_spec
    assert composite_spec.get(GEN_ID) is not None


def test_o2_gradient_forms(run):
    comp, start, _ = run
    o2 = comp.state["field_at_cell"]
    assert _mean(o2[str(c)] for c in INTERIOR) < _mean(o2[str(c)] for c in RIM)


def test_interior_differentiates(run):
    comp, _, _ = run
    counts = comp.state["fate_counts"]
    assert counts.get("1", 0) >= 1 and counts.get("2", 0) >= 1
    types = comp.state["types"]
    o2 = comp.state["field_at_cell"]
    soma = [o2[str(c)] for c in IDS if types[c] == 2]
    germ = [o2[str(c)] for c in IDS if types[c] == 1]
    assert _mean(soma) < _mean(germ)


def test_oxygen_arm_grows(run):
    comp, start, _ = run
    assert comp.state["viable_biomass"] > start["biomass"]
    vols = comp.state["volumes"]
    o2 = comp.state["field_at_cell"]
    ranked = sorted(IDS, key=lambda c: o2[str(c)])
    lo, hi = ranked[: len(IDS) // 2], ranked[-(len(IDS) // 2):]
    gain = lambda cs: _mean(vols[c] - start["vol"][c] for c in cs)
    assert gain(hi) > gain(lo)


def test_cell_count_fixed(run):
    comp, start, _ = run
    assert len(comp.state["volumes"]) == len(start["vol"]) == len(IDS) + 1
    assert sum(comp.state["fate_counts"].values()) == len(IDS)


def test_fate_stable_last_window(run):
    _, _, history = run
    last = history[-10:]
    for k in ("1", "2"):
        vals = [h.get(k, 0) for h in last]
        assert max(vals) - min(vals) <= 1


def test_default_n_steps():
    import viva_genesis  # noqa: F401
    from process_bigraph import composite_spec
    assert composite_spec.get(GEN_ID).default_n_steps == N_UPDATES


def _run_mode(**kw):
    comp = _build(**kw)
    history = []
    for _ in range(N_UPDATES):
        comp.run(1)
        history.append(dict(comp.state["fate_counts"]))
    return comp, history


def _soma_fraction(comp):
    types = comp.state["types"]
    return sum(1 for c in IDS if types[c] == 2) / len(IDS)


def test_no_fate_single_type():
    comp, history = _run_mode(fate_mode="none")
    for h in history:
        assert [k for k, v in h.items() if k != "0" and v > 0] == ["1"]
        assert h["1"] == len(IDS)
    assert _soma_fraction(comp) == 0.0


def test_random_fate_matches_oxygen_fraction():
    ox, _ = _run_mode(fate_mode="oxygen")
    rnd, _ = _run_mode(fate_mode="random")
    f_ox, f_rnd = _soma_fraction(ox), _soma_fraction(rnd)
    assert f_ox > 0 and abs(f_rnd - f_ox) <= 0.15
    # oxygen soma sit at lower O2 than germ; random soma are not O2-keyed
    def gap(comp):
        t, o2 = comp.state["types"], comp.state["field_at_cell"]
        soma = [o2[str(c)] for c in IDS if t[c] == 2]
        germ = [o2[str(c)] for c in IDS if t[c] == 1]
        return _mean(germ) - _mean(soma)
    assert gap(ox) > 0
    assert gap(rnd) < gap(ox) / 2
    # soma set is seed-dependent (random), not a fixed O2 pattern
    other, _ = _run_mode(fate_mode="random", seed=2)
    soma = lambda comp: {c for c in IDS if comp.state["types"][c] == 2}
    assert soma(other) != soma(rnd)


def test_clamped_stays_undifferentiated():
    comp, history = _run_mode(fate_mode="clamped")
    o2 = comp.state["field_at_cell"]
    assert _mean(o2[str(c)] for c in INTERIOR) < _mean(o2[str(c)] for c in RIM)
    for h in history:
        assert h.get("2", 0) == 0
    assert history[-1]["1"] == len(IDS)
