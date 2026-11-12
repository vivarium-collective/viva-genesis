"""S05 differentiation — germ/soma pattern along the O2 gradient + out-of-sample performance gain.

``DifferentiationViz`` re-runs the real ``s05_differentiation`` composite (fate_mode="oxygen",
default params, pinned 40 updates) at render time and reads ``world.snapshot()``,
``world.cell_types()`` and ``world.field_conc(0)``; nothing is drawn by hand.

* Time-lapse (slider + play): the Potts lattice at every 2nd update. Germ cells (type 1) teal,
  soma (type 2) amber, cell borders dark; the medium is shaded by the live O2 field so soma can
  be seen emerging where the cluster interior goes hypoxic. The soma count in each frame is
  asserted equal to the emitted ``fate_counts["2"]``.
* Live trace: germ/soma counts per update with a cursor synced to the frame.
* Performance gain: seed-mean net viable biomass of the four arms (oxygen / none / random /
  clamped) on held-out env B, read from the study's ``runs.db`` (same reduction as
  ``analysis/grade_specialization.py``). If runs.db is unreadable the arms are re-run, with a
  loud warning; the bars are never hardcoded.
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
_STUDY_DIR = _ROOT / "workspace/studies/s05-differentiation"
_MODES = ["oxygen", "none", "random", "clamped"]
_ENV_B = 0.025
GERM, SOMA = 1, 2
_BORDER = "#0f172a"
_MEDIUM_LO, _MEDIUM_HI = "#f8fafc", "#bfdbfe"   # hypoxic (light) -> oxygenated (blue)
_MODE_COLORS = {"oxygen": S.TEAL, "none": S.SLATE, "random": S.RUST, "clamped": S.VIOLET}


class _Run:
    def __init__(self, fate_mode="oxygen", o2_source=None, seed=1):
        from process_bigraph import Composite
        from ..core import build_core
        from ..composites.multicellularity_world import s05_differentiation
        core = build_core()
        kw = {"fate_mode": fate_mode, "seed": seed}
        if o2_source is not None:
            kw["o2_source"] = o2_source
        self.sim = Composite({"state": s05_differentiation(core=core, **kw)}, core=core)
        self.world = self.sim.state["cpm"]["instance"].world

    def update(self):
        self.sim.run(1)
        return {"fate_counts": dict(self.sim.state["fate_counts"]),
                "viable_biomass": float(self.sim.state["viable_biomass"])}


def _picture(labels, ctypes, o2, nx, ny):
    """z-grid: medium in [0,1] = normalised O2; 2 germ; 3 soma; 4 border."""
    top = max(max(o2), 1e-12)
    z = [[0.0] * nx for _ in range(ny)]
    n_soma = set()
    for i, v in enumerate(labels):
        y, x = divmod(i, nx)
        if v == 0:
            z[y][x] = min(max(o2[i] / top, 0.0), 1.0) * 0.98
            continue
        border = False
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            x2, y2 = x + dx, y + dy
            if 0 <= x2 < nx and 0 <= y2 < ny:
                o = labels[x2 + y2 * nx]
                if o != v and o != 0:
                    border = True; break
        t = int(ctypes[v])
        z[y][x] = 4 if border else (3 if t == SOMA else 2)
        if t == SOMA:
            n_soma.add(int(v))
    return z, len(n_soma)


def _frames(n_steps=40, every=2):
    run = _Run("oxygen")
    nx, ny, _ = run.world.dims()
    frames, germ, soma = {}, [], []
    ct0 = list(run.world.cell_types())
    germ.append(sum(1 for t in ct0[1:] if t == GERM)); soma.append(sum(1 for t in ct0[1:] if t == SOMA))
    frames[0] = _picture(list(run.world.snapshot()), ct0, list(run.world.field_conc(0)), nx, ny)[0]
    last = {}
    for t in range(1, n_steps + 1):
        last = run.update()
        ct = list(run.world.cell_types())
        fc = last["fate_counts"]
        germ.append(int(fc.get("1", 0))); soma.append(int(fc.get("2", 0)))
        if t % every == 0 or t == n_steps:
            z, n_soma = _picture(list(run.world.snapshot()), ct, list(run.world.field_conc(0)), nx, ny)
            assert n_soma == int(fc.get("2", 0)), (t, n_soma, fc)
            assert sum(1 for x in ct[1:] if x == SOMA) == int(fc.get("2", 0)), (t, fc)
            frames[t] = z
    return dict(frames=frames, germ=germ, soma=soma, final=last, dims=(nx, ny))


def _gain_from_db(db_path, env=_ENV_B):
    db = sqlite3.connect(str(db_path))
    by = {}
    for rid, pj, n in db.execute("select run_id, params_json, n_steps from runs_meta where status='completed'"):
        p = json.loads(pj)
        if abs(float(p["o2_source"]) - env) > 1e-9:
            continue
        first = db.execute("select min(step) from history where simulation_id=? and step>=1", (rid,)).fetchone()[0]

        def vb(step):
            r = db.execute("select state from history where simulation_id=? and step=?", (rid, step)).fetchone()
            return float(json.loads(r[0])["viable_biomass"])
        by.setdefault(p["fate_mode"], []).append((int(p["seed"]), vb(n) - vb(first)))
    if not all(m in by for m in _MODES):
        raise ValueError(f"runs.db lacks env-B arms: have {sorted(by)}")
    return by


def _gain_from_rerun(n_steps=40, seeds=(1, 2, 3)):
    by = {}
    for m in _MODES:
        for s in seeds:
            r = _Run(m, _ENV_B, s)
            vals = []
            for _ in range(n_steps):
                vals.append(r.update()["viable_biomass"])
            by.setdefault(m, []).append((s, vals[-1] - vals[0]))
    return by


class DifferentiationViz(Visualization):
    """S05: germ/soma pattern over the O2 gradient (real composite) + out-of-sample gain bars."""
    config_schema = {
        "title": {"_type": "string", "_default": "Hypoxic interiors differentiate to soma; O2-gated fate beats its nulls out of sample"},
        "n_steps": {"_type": "integer", "_default": 40},
        "runs_db": {"_type": "string", "_default": ""},
    }

    def inputs(self): return {}
    def outputs(self): return {"html": "string"}

    def update(self, state=None):
        import plotly.graph_objects as go

        cfg = self.config
        n_steps = int(cfg["n_steps"])
        run = _frames(n_steps)
        nx, ny = run["dims"]
        steps = sorted(run["frames"])
        db_path = Path(cfg.get("runs_db") or _STUDY_DIR / "runs.db")
        try:
            by = _gain_from_db(db_path)
            src = "study runs.db"
        except Exception as exc:
            warnings.warn(f"viz_s05_differentiation: could not read env-B arms from {db_path} ({exc!r}); "
                          "RE-RUNNING the four arms (3 seeds) instead -- numbers come from fresh real runs",
                          stacklevel=2)
            by = _gain_from_rerun(n_steps)
            src = "fresh re-run"
        mean = {m: statistics.mean(v for _, v in by[m]) for m in _MODES}

        # z in [0,.98] medium, 2 germ, 3 soma, 4 border -> zmax 5 maps 2->.4? remap explicitly below
        zmax = 5.0
        cs = [[0.0, _MEDIUM_LO], [1.0 / zmax, _MEDIUM_HI], [1.0 / zmax, _MEDIUM_HI], [2.0 / zmax, _MEDIUM_HI],
              [2.0 / zmax, S.TEAL], [3.0 / zmax, S.TEAL], [3.0 / zmax, S.AMBER], [4.0 / zmax, S.AMBER],
              [4.0 / zmax, _BORDER], [1.0, _BORDER]]

        figA = go.Figure(go.Heatmap(z=run["frames"][steps[0]], zmin=0, zmax=zmax, colorscale=cs,
                                    showscale=False, xgap=0, ygap=0, hoverinfo="skip"))
        figA.update_xaxes(visible=False, range=[-0.5, nx - 0.5], constrain="domain")
        figA.update_yaxes(visible=False, range=[-0.5, ny - 0.5], scaleanchor="x")
        figA.update_layout(**S.base_layout(height=380, margin=dict(l=8, r=8, t=34, b=8), showlegend=False,
                           title=dict(text="Germ (teal) / soma (amber) over the O2 field (blue = oxygenated medium)",
                                      font=dict(size=12), x=0.5)))

        figC = go.Figure()
        tx = list(range(n_steps + 1))
        figC.add_trace(go.Scatter(x=tx, y=run["germ"], mode="lines", name="germ", line=dict(color=S.TEAL, width=2.2)))
        figC.add_trace(go.Scatter(x=tx, y=run["soma"], mode="lines", name="soma", line=dict(color=S.AMBER, width=2.2)))
        for col, key in ((S.TEAL, "germ"), (S.AMBER, "soma")):
            figC.add_trace(go.Scatter(x=[0], y=[run[key][0]], mode="markers", showlegend=False, hoverinfo="skip",
                                      marker=dict(size=11, color=col, line=dict(color="#fff", width=2))))
        figC.update_layout(**S.base_layout(
            height=330, margin=dict(l=62, r=12, t=38, b=96),
            title=dict(text="Cell types over time (emitted fate_counts)", font=dict(size=12), x=0.5),
            xaxis=dict(title="CPM update", gridcolor=S.GRID, zeroline=False),
            yaxis=dict(title="cells", rangemode="tozero", gridcolor=S.GRID, zeroline=False),
            legend=dict(orientation="h", y=-0.3, x=0.5, xanchor="center", font=dict(size=10))))

        figB = go.Figure()
        figB.add_trace(go.Bar(x=_MODES, y=[mean[m] for m in _MODES], marker_color=[_MODE_COLORS[m] for m in _MODES],
                              text=[f"{mean[m]:.0f}" for m in _MODES], textposition="outside", name="seed mean",
                              hovertemplate="%{x}<br>mean net biomass %{y:.1f}<extra></extra>"))
        figB.add_trace(go.Scatter(x=[m for m in _MODES for _ in by[m]], y=[v for m in _MODES for _, v in by[m]],
                                  mode="markers", marker=dict(size=6, color=S.INK, opacity=0.6), name="seeds",
                                  text=[f"seed {s}" for m in _MODES for s, _ in by[m]],
                                  hovertemplate="%{x} %{text}<br>%{y:.1f}<extra></extra>"))
        best_ctrl = max(mean[m] for m in _MODES[1:])
        figB.update_layout(**S.base_layout(
            height=330, margin=dict(l=62, r=12, t=38, b=60),
            title=dict(text=f"Held-out env B (O2 source {_ENV_B}): net viable biomass", font=dict(size=12), x=0.5),
            xaxis=dict(title="fate arm", zeroline=False),
            yaxis=dict(title="net viable biomass (update 40 - 1)", rangemode="tozero", gridcolor=S.GRID, zeroline=False),
            showlegend=False))

        cfgp = {"responsive": True, "displayModeBar": False}
        a_html = figA.to_html(full_html=False, include_plotlyjs="cdn", div_id="s05_lattice", config=cfgp)
        b_html = figB.to_html(full_html=False, include_plotlyjs=False, div_id="s05_gain", config=cfgp)
        c_html = figC.to_html(full_html=False, include_plotlyjs=False, div_id="s05_counts", config=cfgp)
        payload = json.dumps({"steps": steps, "z": [run["frames"][t] for t in steps],
                              "g": run["germ"], "s": run["soma"]}, separators=(",", ":"))
        controls = (
            '<div style="display:flex;align-items:center;gap:10px;padding:4px 10px;font-size:12px">'
            '<button id="s05_play" type="button" style="padding:4px 14px;border:1px solid #cbd5e1;border-radius:6px;'
            'background:#f8fafc;cursor:pointer">Play</button>'
            f'<input id="s05_rng" type="range" min="0" max="{len(steps) - 1}" value="0" style="flex:1">'
            '<span id="s05_lab" style="min-width:92px;text-align:right;font-variant-numeric:tabular-nums">update 0</span>'
            '</div>')
        sync = ("<script>(function(){var D=" + payload + ";var A=document.getElementById('s05_lattice');"
                "var C=document.getElementById('s05_counts');var R=document.getElementById('s05_rng');"
                "var L=document.getElementById('s05_lab');var B=document.getElementById('s05_play');var timer=null;"
                "function show(i){var t=D.steps[i];R.value=i;L.textContent='update '+t;"
                "Plotly.restyle(A,{z:[D.z[i]]},[0]);"
                "Plotly.restyle(C,{x:[[t]],y:[[D.g[t]]]},[2]);Plotly.restyle(C,{x:[[t]],y:[[D.s[t]]]},[3]);}"
                "function stop(){if(timer){clearInterval(timer);timer=null;B.textContent='Play'}}"
                "R.addEventListener('input',function(){stop();show(parseInt(R.value,10))});"
                "B.addEventListener('click',function(){if(timer){stop();return}"
                "if(parseInt(R.value,10)>=D.steps.length-1){show(0)}B.textContent='Pause';"
                "timer=setInterval(function(){var i=parseInt(R.value,10)+1;if(i>=D.steps.length){stop();return}show(i)},260)});"
                "})();</script>")
        inner = (a_html + controls + '<div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:0">'
                 f'<div style="min-width:0;overflow:hidden">{c_html}</div>'
                 f'<div style="min-width:0;overflow:hidden">{b_html}</div></div>' + sync)

        fc = run["final"]["fate_counts"]
        cap = (f"Real CPM run of s05_differentiation (fate_mode oxygen, seed 1, pinned {n_steps}-update window): at update "
               f"{n_steps} the patch holds <b>{fc.get('1', 0)}</b> germ and <b>{fc.get('2', 0)}</b> soma cells; each frame's "
               f"soma count is asserted equal to the emitted fate_counts. Right: seed-mean net viable biomass on held-out env B "
               f"({src}); oxygen {mean['oxygen']:.0f} vs best control {best_ctrl:.0f} "
               f"(gain {mean['oxygen'] - best_ctrl:+.0f}), dots = seeds. Transient window, one CPM backend.")
        return {"html": S.frame(inner, title=cfg.get("title"), tier="first fidelity", view="Mechanism",
                                tone="neutral", max_width=980, caption_text=cap)}
