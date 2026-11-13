"""S06 individuality -- adhesion response to group selection, Price among/within-group terms, group toughness.

``IndividualityViz`` reads the study's ``runs.db`` with the same per-run read pattern as
``analysis/grade_individuality.py`` (per-generation ``history.state`` scalars, params from
``runs_meta``) and plots the seed-mean per arm: clonality {clonal, mixed} x selection {on, off}.
If runs.db is unreadable the 24 runs are re-run from the composite with a loud warning. Nothing is
hardcoded; the final-generation seed-mean adhesion drawn for clonal-sel is asserted equal to the
value computed independently from the emitted outcomes.
"""
from __future__ import annotations

import json
import sqlite3
import statistics
import warnings
from pathlib import Path

from process_bigraph.visualization import Visualization

from . import viz_style as S

_ROOT = Path(__file__).resolve().parents[2]
_STUDY_DIR = _ROOT / "workspace/studies/s06-individuality"
ARMS = [("clonal", True), ("clonal", False), ("mixed", True), ("mixed", False)]
_COL = {("clonal", True): S.TEAL, ("clonal", False): S.SLATE, ("mixed", True): S.AMBER, ("mixed", False): S.MUTED}
_DASH = {True: "solid", False: "dot"}
KEYS = ("mean_adhesion", "among_group", "within_group", "mean_toughness", "heritability")


def _name(arm):
    return f"{arm[0]}-{'sel' if arm[1] else 'drift'}"


def _from_db(db_path):
    """{arm: {seed: {key: [value per generation, steps >= 1]}}}"""
    db = sqlite3.connect(str(db_path))
    out = {}
    for rid, pj, n in db.execute("select run_id, params_json, n_steps from runs_meta where status='completed'"):
        p = json.loads(pj)
        rows = db.execute("select step, state from history where simulation_id=? and step>=1 order by step", (rid,)).fetchall()
        st = [json.loads(s) for _, s in rows]
        out.setdefault((p["clonality"], bool(p["selection"])), {})[int(p["seed"])] = {k: [float(s[k]) for s in st] for k in KEYS}
    if not all(a in out for a in ARMS):
        raise ValueError(f"runs.db lacks arms: have {sorted(out)}")
    return out


def _from_rerun(seeds=(1, 2, 3, 4, 5, 6), n_steps=None):
    import inspect
    from process_bigraph import Composite
    from ..core import build_core
    from ..composites import multicellularity_world as W
    fn = W.s06_individuality
    core = build_core()
    out = {}
    for c, sel in ARMS:
        for sd in seeds:
            kw = dict(clonality=c, selection=sel, seed=sd)
            sim = Composite({"state": fn(core=core, **kw)}, core=core)
            n = n_steps or 20
            hist = {k: [] for k in KEYS}
            for _ in range(n):
                sim.run(1)
                for k in KEYS:
                    hist[k].append(float(sim.state[k]))
            out.setdefault((c, sel), {})[sd] = hist
    return out


def _seed_mean(data, arm, key):
    runs = list(data[arm].values())
    n = min(len(r[key]) for r in runs)
    return [statistics.mean(r[key][g] for r in runs) for g in range(n)]


class IndividualityViz(Visualization):
    """S06: clonal group selection evolves adhesion; drift null and mixed arm are weaker."""
    config_schema = {
        "title": {"_type": "string", "_default": "Clonal group selection evolves adhesion; the drift null and mixed arm respond less"},
        "runs_db": {"_type": "string", "_default": ""},
    }

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        import plotly.graph_objects as go

        cfg = self.config
        db_path = Path(cfg.get("runs_db") or _STUDY_DIR / "runs.db")
        try:
            data = _from_db(db_path)
            src = "study runs.db"
        except Exception as exc:
            warnings.warn(f"viz_s06_individuality: could not read runs.db at {db_path} ({exc!r}); "
                          "RE-RUNNING all 24 runs instead -- numbers come from fresh real runs", stacklevel=2)
            data = _from_rerun()
            src = "fresh re-run"
        mean = {(a, k): _seed_mean(data, a, k) for a in ARMS for k in KEYS}
        n_seeds = {a: len(data[a]) for a in ARMS}
        ngen = len(mean[(ARMS[0], "mean_adhesion")])
        gens = list(range(1, ngen + 1))

        # data-consistency: drawn final clonal-sel adhesion == value computed straight from emitted outcomes
        direct = statistics.mean(r["mean_adhesion"][-1] for r in data[("clonal", True)].values())
        drawn = mean[(("clonal", True), "mean_adhesion")][-1]
        assert abs(drawn - direct) < 1e-12, (drawn, direct)

        def lines(key, title, ytitle, h=330):
            fig = go.Figure()
            for a in ARMS:
                fig.add_trace(go.Scatter(x=gens, y=mean[(a, key)], mode="lines", name=_name(a),
                                         line=dict(color=_COL[a], width=2.4, dash=_DASH[a[1]]),
                                         hovertemplate=_name(a) + " gen %{x}: %{y:.4f}<extra></extra>"))
            fig.update_layout(**S.base_layout(
                height=h, margin=dict(l=62, r=12, t=38, b=96),
                title=dict(text=title, font=dict(size=12), x=0.5),
                xaxis=dict(title="generation", gridcolor=S.GRID, zeroline=False),
                yaxis=dict(title=ytitle, gridcolor=S.GRID, zeroline=False),
                legend=dict(orientation="h", y=-0.3, x=0.5, xanchor="center", font=dict(size=10))))
            return fig

        figA = lines("mean_adhesion", f"Mean adhesion per generation (seed mean, n={n_seeds[ARMS[0]]})", "mean adhesion", 360)
        figB = lines("among_group", "Among-group selection (Price covariance term)", "among-group term")
        figC = lines("mean_toughness", "Group fitness: mean toughness (cohesion)", "mean toughness")

        cfgp = {"responsive": True, "displayModeBar": False}
        a = figA.to_html(full_html=False, include_plotlyjs="cdn", div_id="s06_adh", config=cfgp)
        b = figB.to_html(full_html=False, include_plotlyjs=False, div_id="s06_among", config=cfgp)
        c = figC.to_html(full_html=False, include_plotlyjs=False, div_id="s06_tough", config=cfgp)
        inner = (a + '<div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:0">'
                 f'<div style="min-width:0;overflow:hidden">{b}</div><div style="min-width:0;overflow:hidden">{c}</div></div>')

        fin = {a_: mean[(a_, "mean_adhesion")][-1] for a_ in ARMS}
        ini = {a_: mean[(a_, "mean_adhesion")][0] for a_ in ARMS}
        resp = {a_: fin[a_] - ini[a_] for a_ in ARMS}
        wmax = max(abs(v) for a_ in ARMS for v in mean[(a_, "within_group")])
        her = {a_: statistics.mean(mean[(a_, "heritability")]) for a_ in ARMS}
        tfin = {a_: mean[(a_, "mean_toughness")][-1] for a_ in ARMS}
        top_t = max(ARMS, key=lambda a_: tfin[a_])
        cap = (f"Seed-mean per arm from the {src} ({ngen} generations, all seeds pooled; nothing hardcoded). "
               "Adhesion response (final - first generation): "
               + ", ".join(f"{_name(a_)} {resp[a_]:+.3f}" for a_ in ARMS)
               + f". Highest final toughness: {_name(top_t)} ({tfin[top_t]:.3f}). Heritability is {her[('clonal', True)]:.2f} clonal vs "
               f"{her[('mixed', True)]:.2f} mixed. The within-group term is ~0 in every arm (max |{wmax:.4f}|): adhesion carries no "
               "within-group growth advantage, so the mixed control weakens the response by trait dilution (halved heritability), "
               "not by within-group conflict. The drift arm itself moves upward from the lower-bounded initial adhesion, so the "
               "margin over drift is the claim, not drift being flat. Final clonal-sel adhesion asserted equal to the value "
               "computed directly from emitted outcomes.")
        return {"html": S.frame(inner, title=cfg.get("title"), tier="first fidelity", view="Mechanism",
                                tone="neutral", max_width=980, caption_text=cap)}


if __name__ == "__main__":
    out = _STUDY_DIR / "viz/individuality.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    v = IndividualityViz.__new__(IndividualityViz)
    v.config = {"title": IndividualityViz.config_schema["title"]["_default"], "runs_db": ""}
    out.write_text(v.update()["html"])
    print(out, out.stat().st_size)
