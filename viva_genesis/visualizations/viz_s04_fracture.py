"""S04 morphomechanics — watch a clonal CPM cluster grow and snap into propagules.

``ClusterFractureViz`` re-runs the real S04 world (the ``s04_morphomechanics`` generator in a ``Composite``
stepped one update at a time) at render time; nothing is hardcoded or drawn
by hand:

* Time-lapse (animated, slider + play): the Potts lattice (``world.snapshot()``) at every 2nd
  update of the pinned 40-update window for a WEAK-adhesion run and a STRONG-adhesion run (same
  seed). Each cell is coloured by the connected component (propagule) it belongs to, using the
  engine's own adjacency (8-neighbour Moore, same as ``viva_cpm.metrics``); the largest
  propagule is teal, detached propagules take other hues, cell borders are drawn dark.
* Live trace: ``n_propagules`` per update for both runs, with a cursor synced to the frame.
* Toughness curve: ``largest_cluster_fraction`` at update 40 for every adhesion x seed point of
  the study sweep (read from the study's variants), seed dots + seed-mean line + min-max band.
  The two time-lapse conditions are ringed on the curve.

Component counts from the lattice labeling are asserted equal to the process's own emitted
``n_propagules`` so the picture and the scalar cannot diverge.
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph.visualization import Visualization

from . import viz_style as S

_PLOTLY = "https://cdn.plot.ly/plotly-2.27.0.min.js"
_STUDY = Path(__file__).resolve().parents[2] / "workspace/studies/s04-morphomechanics/study.yaml"
_DEFAULT_ADH = [0.0, 0.3, 0.5, 0.62, 0.75, 0.9, 0.95]
_DEFAULT_SEEDS = [1, 2, 3]
_PROP_COLORS = [S.AMBER, S.VIOLET, S.RUST, "#2563eb", "#15803d", "#db2777", "#ca8a04", "#0891b2"]
_BORDER = "#0f172a"
_MEDIUM = "#f1f5f9"


def _sweep_from_study(path):
    try:
        import yaml
        doc = yaml.safe_load(Path(path).read_text())
        adh, seeds = set(), set()
        for v in doc.get("variants", []):
            p = v.get("params", {})
            adh.add(float(p["adhesion"])); seeds.add(int(p["seed"]))
        if adh and seeds:
            return sorted(adh), sorted(seeds)
    except Exception:
        pass
    return list(_DEFAULT_ADH), list(_DEFAULT_SEEDS)


class _Run:
    """The real S04 composite (generator -> Composite); ``world`` is the live CPM lattice owned by
    the composite's CPMProcess instance."""

    def __init__(self, adhesion, seed):
        from process_bigraph import Composite
        from ..core import build_core
        from ..composites.multicellularity_world import s04_morphomechanics
        core = build_core()
        self.sim = Composite({"state": s04_morphomechanics(core=core, adhesion=adhesion, seed=seed)}, core=core)
        self.world = self.sim.state["cpm"]["instance"].world

    def update(self, _state=None, _interval=1.0):
        self.sim.run(1)
        return {"n_propagules": self.sim.state["n_propagules"],
                "largest_cluster_fraction": self.sim.state["largest_cluster_fraction"]}


def _make_proc(adhesion, seed):
    return _Run(adhesion, seed)


def _components(labels, ctypes, nx, ny):
    """Connected components (8-neighbour) of the cell mask. Returns comp-id grid (flat, -1 =
    medium) ordered by size desc (0 = largest) and the size list."""
    mask = [v != 0 and int(ctypes[v]) == 1 for v in labels]
    comp = [-1] * len(labels)
    sizes = []
    for s, m in enumerate(mask):
        if not m or comp[s] != -1:
            continue
        cid = len(sizes); comp[s] = cid; stack = [s]; n = 0
        while stack:
            c = stack.pop(); n += 1
            cy, cx = divmod(c, nx)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    x2, y2 = cx + dx, cy + dy
                    if 0 <= x2 < nx and 0 <= y2 < ny:
                        n2 = x2 + y2 * nx
                        if mask[n2] and comp[n2] == -1:
                            comp[n2] = cid; stack.append(n2)
        sizes.append(n)
    order = sorted(range(len(sizes)), key=lambda i: -sizes[i])
    rank = {old: new for new, old in enumerate(order)}
    return [rank[c] if c >= 0 else -1 for c in comp], sorted(sizes, reverse=True)


def _picture(labels, ctypes, nx, ny):
    """z-grid: 0 medium, 1 cell border, 2 largest propagule, 3.. other propagules."""
    comp, sizes = _components(labels, ctypes, nx, ny)
    z = [[0] * nx for _ in range(ny)]
    for i, c in enumerate(comp):
        if c < 0:
            continue
        y, x = divmod(i, nx)
        v = labels[i]
        border = False
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            x2, y2 = x + dx, y + dy
            if 0 <= x2 < nx and 0 <= y2 < ny:
                o = labels[x2 + y2 * nx]
                if o != v and o != 0:
                    border = True; break
        z[y][x] = 1 if border else (2 if c == 0 else 3 + (c - 1) % len(_PROP_COLORS))
    return z, sizes


def _run_frames(adhesion, seed, n_steps=40, every=2):
    proc = _make_proc(adhesion, seed)
    nx, ny, _ = proc.world.dims()
    frames, npr, lcf = {}, [], []

    z0, sizes0 = _picture(list(proc.world.snapshot()), list(proc.world.cell_types()), nx, ny)
    frames[0] = (z0, len(sizes0), 0)
    npr.append(len(sizes0))
    lcf.append(None)
    last = {}
    for t in range(1, n_steps + 1):
        last = proc.update({}, 1.0)
        labels = list(proc.world.snapshot()); ct = list(proc.world.cell_types())
        if t % every == 0 or t == n_steps:
            z, sizes = _picture(labels, ct, nx, ny)
            frames[t] = (z, len(sizes), len(ct) - 1)
            assert len(sizes) == int(last["n_propagules"]), (adhesion, seed, t, len(sizes), last["n_propagules"])
        npr.append(int(last["n_propagules"])); lcf.append(float(last["largest_cluster_fraction"]))
    return dict(frames=frames, n_prop=npr, lcf=lcf, final=last, dims=(nx, ny))


def _sweep(adh_list, seeds, n_steps=40):
    out = {}
    for a in adh_list:
        for s in seeds:
            proc = _make_proc(a, s)
            last = {}
            for _ in range(n_steps):
                last = proc.update({}, 1.0)
            out[(a, s)] = (float(last["largest_cluster_fraction"]), int(last["n_propagules"]))
    return out


def _fmt_a(a):
    return f"{a:g}"


class ClusterFractureViz(Visualization):
    """S04: animated lattice of a growing clonal cluster at weak vs strong adhesion + the
    propagule-toughness curve across the adhesion sweep (all from fresh real CPM runs)."""
    config_schema = {
        "title": {"_type": "string", "_default": "Weak adhesion lets growth snap a cluster into propagules"},
        "weak_adhesion": {"_type": "float", "_default": 0.0},
        "strong_adhesion": {"_type": "float", "_default": 0.95},
        "seed": {"_type": "integer", "_default": 1},
        "n_steps": {"_type": "integer", "_default": 40},
        "study_yaml": {"_type": "string", "_default": ""},
    }

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        cfg = self.config
        n_steps = int(cfg["n_steps"]); seed = int(cfg["seed"])
        aw, as_ = float(cfg["weak_adhesion"]), float(cfg["strong_adhesion"])
        adh_list, seeds = _sweep_from_study(cfg.get("study_yaml") or _STUDY)
        runs = {"weak": _run_frames(aw, seed, n_steps), "strong": _run_frames(as_, seed, n_steps)}
        sweep = _sweep(adh_list, seeds, n_steps)
        nx, ny = runs["weak"]["dims"]
        steps = sorted(runs["weak"]["frames"])

        k = len(_PROP_COLORS) + 3
        cs = [[0.0, _MEDIUM], [1 / k, _MEDIUM], [1 / k, _BORDER], [2 / k, _BORDER], [2 / k, S.TEAL], [3 / k, S.TEAL]]
        for i, c in enumerate(_PROP_COLORS):
            cs += [[(3 + i) / k, c], [(4 + i) / k, c]]

        def heat(z):
            return go.Heatmap(z=z, zmin=0, zmax=k, colorscale=cs, showscale=False, xgap=0, ygap=0,
                              hoverinfo="skip")

        # --- fig A: animated lattices (two heatmaps) ---------------------------------------
        figA = make_subplots(rows=1, cols=2, horizontal_spacing=0.04,
                             subplot_titles=(f"weak adhesion ({_fmt_a(aw)})", f"strong adhesion ({_fmt_a(as_)})"))
        figA.add_trace(heat(runs["weak"]["frames"][steps[0]][0]), 1, 1)
        figA.add_trace(heat(runs["strong"]["frames"][steps[0]][0]), 1, 2)
        for c in (1, 2):
            figA.update_xaxes(visible=False, row=1, col=c, range=[-0.5, nx - 0.5])
            figA.update_yaxes(visible=False, row=1, col=c, range=[-0.5, ny - 0.5])
        figA.update_layout(**S.base_layout(
            height=290, margin=dict(l=8, r=8, t=34, b=8), showlegend=False))
        for a in figA.layout.annotations:
            a.font = dict(size=12, color=S.INK)

        # --- fig B: toughness curve --------------------------------------------------------
        figB = go.Figure()
        mean_x, mean_y, lo, hi = [], [], [], []
        for a in adh_list:
            v = [sweep[(a, s)][0] for s in seeds]
            mean_x.append(a); mean_y.append(sum(v) / len(v)); lo.append(min(v)); hi.append(max(v))
        figB.add_trace(go.Scatter(x=mean_x + mean_x[::-1], y=hi + lo[::-1], fill="toself", fillcolor=S.BAND_FILL,
                                  line=dict(width=0), hoverinfo="skip", name="seed range"))
        figB.add_trace(go.Scatter(x=mean_x, y=mean_y, mode="lines", line=dict(color=S.INK_SOFT, width=2),
                                  name="seed mean", hovertemplate="adhesion %{x}<br>mean %{y:.3f}<extra></extra>"))
        sx, sy, st = [], [], []
        for a in adh_list:
            for s in seeds:
                lc, npr = sweep[(a, s)]
                sx.append(a); sy.append(lc); st.append(f"seed {s}: {npr} propagule{'s' if npr != 1 else ''}")
        figB.add_trace(go.Scatter(x=sx, y=sy, mode="markers", text=st, name="seeds",
                                  marker=dict(size=7, color=S.SLATE, opacity=0.75),
                                  hovertemplate="adhesion %{x}<br>cohesion %{y:.3f}<br>%{text}<extra></extra>"))
        for a, col, nm in ((aw, S.RUST, "weak"), (as_, S.TEAL, "strong")):
            v = [sweep[(a, s)][0] for s in seeds if (a, s) in sweep]
            if v:
                figB.add_trace(go.Scatter(x=[a], y=[sum(v) / len(v)], mode="markers", name=f"{nm} adhesion (shown above)",
                                          marker=dict(size=17, color="rgba(0,0,0,0)", line=dict(color=col, width=3)),
                                          hoverinfo="skip"))
        figB.update_layout(**S.base_layout(
            height=330, margin=dict(l=62, r=12, t=38, b=96), title=dict(text="Toughness: cohesion vs adhesion (update %d)" % n_steps, font=dict(size=12), x=0.5),
            xaxis=dict(title="adhesion (0 = none, 1 = strong)", gridcolor=S.GRID, zeroline=False),
            yaxis=dict(title="largest cluster fraction", range=[0, 1.08], gridcolor=S.GRID, zeroline=False),
            legend=dict(orientation="h", y=-0.3, x=0.5, xanchor="center", font=dict(size=10))))

        # --- fig C: propagule counts + cursor synced to the animation ---------------------
        figC = go.Figure()
        tx = list(range(0, n_steps + 1))
        for key, col, a in (("weak", S.RUST, aw), ("strong", S.TEAL, as_)):
            figC.add_trace(go.Scatter(x=tx, y=runs[key]["n_prop"], mode="lines", line=dict(color=col, width=2.2),
                                      name=f"adhesion {_fmt_a(a)}",
                                      hovertemplate="update %{x}<br>%{y} propagules<extra></extra>"))
        for key, col in (("weak", S.RUST), ("strong", S.TEAL)):
            figC.add_trace(go.Scatter(x=[0], y=[runs[key]["n_prop"][0]], mode="markers", showlegend=False, hoverinfo="skip",
                                      marker=dict(size=11, color=col, line=dict(color="#fff", width=2))))
        figC.update_layout(**S.base_layout(
            height=330, margin=dict(l=62, r=12, t=38, b=96), title=dict(text="Propagule count over time", font=dict(size=12), x=0.5),
            xaxis=dict(title="CPM update", gridcolor=S.GRID, zeroline=False),
            yaxis=dict(title="propagules (connected clusters)", rangemode="tozero", gridcolor=S.GRID, zeroline=False),
            legend=dict(orientation="h", y=-0.3, x=0.5, xanchor="center", font=dict(size=10))))

        cfgp = {"responsive": True, "displayModeBar": False}
        divA, divB, divC = "s04_lattice", "s04_toughness", "s04_counts"
        a_html = figA.to_html(full_html=False, include_plotlyjs="cdn", div_id=divA, config=cfgp)
        b_html = figB.to_html(full_html=False, include_plotlyjs=False, div_id=divB, config=cfgp)
        c_html = figC.to_html(full_html=False, include_plotlyjs=False, div_id=divC, config=cfgp)
        payload = json.dumps({"steps": steps, "weak": [runs["weak"]["frames"][t][0] for t in steps],
                              "strong": [runs["strong"]["frames"][t][0] for t in steps],
                              "nw": runs["weak"]["n_prop"], "ns": runs["strong"]["n_prop"]},
                             separators=(",", ":"))
        controls = (
            '<div style="display:flex;align-items:center;gap:10px;padding:4px 10px;font-size:12px">'
            '<button id="s04_play" type="button" style="padding:4px 14px;border:1px solid #cbd5e1;border-radius:6px;'
            'background:#f8fafc;cursor:pointer">Play</button>'
            f'<input id="s04_rng" type="range" min="0" max="{len(steps) - 1}" value="0" style="flex:1">'
            '<span id="s04_lab" style="min-width:92px;text-align:right;font-variant-numeric:tabular-nums">update 0</span>'
            '</div>')
        sync = ("<script>(function(){var D=" + payload + ";var A=document.getElementById('" + divA + "');"
                "var C=document.getElementById('" + divC + "');var R=document.getElementById('s04_rng');"
                "var L=document.getElementById('s04_lab');var B=document.getElementById('s04_play');var timer=null;"
                "function show(i){var t=D.steps[i];R.value=i;L.textContent='update '+t;"
                "Plotly.restyle(A,{z:[D.weak[i],D.strong[i]]},[0,1]);"
                "Plotly.restyle(C,{x:[[t]],y:[[D.nw[t]]]},[2]);Plotly.restyle(C,{x:[[t]],y:[[D.ns[t]]]},[3]);}"
                "R.addEventListener('input',function(){stop();show(parseInt(R.value,10))});"
                "function stop(){if(timer){clearInterval(timer);timer=null;B.textContent='Play'}}"
                "B.addEventListener('click',function(){if(timer){stop();return}"
                "if(parseInt(R.value,10)>=D.steps.length-1){show(0)}B.textContent='Pause';"
                "timer=setInterval(function(){var i=parseInt(R.value,10)+1;if(i>=D.steps.length){stop();return}show(i)},260)});"
                "window.s04_show=show;})();</script>")
        inner = (a_html + controls + '<div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:0">'
                 f'<div style="min-width:0;overflow:hidden">{b_html}</div>'
                 f'<div style="min-width:0;overflow:hidden">{c_html}</div></div>' + sync)

        wf, sf = runs["weak"]["final"], runs["strong"]["final"]
        cap = (f"Real CPM runs (viva-cpm, seed {seed}, pinned {n_steps}-update window). Teal = the largest propagule; "
               f"other hues = detached propagules; dark lines = cell borders. At adhesion {_fmt_a(aw)} growth pressure "
               f"fractures the cluster into <b>{int(wf['n_propagules'])}</b> propagules (largest holds "
               f"{wf['largest_cluster_fraction']:.0%} of cells); at {_fmt_a(as_)} it stays <b>{int(sf['n_propagules'])}</b> "
               f"cohesive body. Toughness curve: {len(adh_list)} adhesion levels x {len(seeds)} seeds, dots = individual "
               f"seeds, band = seed range. Transient readout: fracture re-merges past ~80 updates.")
        return {"html": S.frame(inner, title=cfg.get("title"), tier="first fidelity", view="Mechanism",
                                tone="neutral", max_width=980, caption_text=cap)}
