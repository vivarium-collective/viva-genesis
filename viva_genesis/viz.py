"""Workspace visualizations for viva-genesis (live in the workbench Visualizations tab).

``VentReactorTimeseries`` runs the og-00 **real coupled model**
(``serpentinizing_vent_reactor`` — PHREEQC serpentinization + FiPy reactive
transport) via ``build_core()`` and returns ``{"html": <plotly html>}``. As a
``Visualization`` (a Step subclass) it auto-registers through the package walk
and re-runs live with the study.
"""
from __future__ import annotations

from process_bigraph import Composite, gather_emitter_results
from process_bigraph.visualization import Visualization


class VentReactorTimeseries(Visualization):
    """Campaign-0 real vent-reactor trajectory: temperature, pH, reducing power
    (H2 flux + pe), porosity, and the mass/charge + spatial-flux conservation
    witnesses — with the Lost City acceptance windows shaded.

    Drives the genuine PHREEQC + FiPy composite (``viva_genesis.composites``).
    """

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign 0 — real vent reactor (PHREEQC + FiPy)"},
        "n_steps": {"_type": "integer", "_default": 120},
        # Real-composite overrides (kept in sync with the generator parameters).
        "flow_velocity": {"_type": "float", "_default": 1.0e-3},
        "olivine_rate": {"_type": "float", "_default": 0.15},
        "nx": {"_type": "integer", "_default": 40},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from .core import build_core
        from .composites.vent_reactor import serpentinizing_vent_reactor

        core = build_core()
        doc = serpentinizing_vent_reactor(
            core,
            flow_velocity=float(self.config["flow_velocity"]),
            olivine_rate=float(self.config["olivine_rate"]),
            nx=int(self.config["nx"]),
        )
        sim = Composite({"state": doc}, core=core)
        sim.run(float(self.config["n_steps"]))
        rows = gather_emitter_results(sim)[("emitter",)]
        return {"html": self._figure(rows)}

    def _figure(self, rows) -> str:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        def col(k):
            return [r[k] for r in rows if k in r]

        t = [r.get("global_time", i) for i, r in enumerate(rows)]
        temp_c = [v - 273.15 for v in col("temperature")]
        ph = col("pH")
        h2f = col("H2_flux")
        pe = col("pe")
        por = col("porosity")
        ci = [abs(v) for v in col("charge_imbalance")]
        fdr = [abs(v) for v in col("flux_divergence_residual")]

        ink, teal, amber, slate, rust = "#1e293b", "#0d9488", "#d97706", "#64748b", "#b91c1c"
        fig = make_subplots(
            rows=2, cols=3, vertical_spacing=0.17, horizontal_spacing=0.09,
            subplot_titles=(
                "Temperature (°C)", "pH", "H₂ source flux (mol/s)",
                "Redox pe", "Porosity", "Conservation residuals (|·|)",
            ),
        )
        # Temperature + Lost City window 40–91 °C.
        fig.add_hrect(y0=40, y1=91, line_width=0, fillcolor=teal, opacity=0.08, row=1, col=1)
        fig.add_scatter(x=t, y=temp_c, mode="lines", line=dict(color=amber, width=2.5), row=1, col=1)
        # pH + field window 9.0–10.8 (real equilibrium sits below — the open gap).
        fig.add_hrect(y0=9.0, y1=10.8, line_width=0, fillcolor=teal, opacity=0.08, row=1, col=2)
        fig.add_scatter(x=t, y=ph, mode="lines", line=dict(color=teal, width=2.5), row=1, col=2)
        # H2 flux (reducing power).
        fig.add_scatter(x=t, y=h2f, mode="lines", line=dict(color=ink, width=2), row=1, col=3)
        # Redox pe (reducing < 0).
        fig.add_hline(y=0.0, line=dict(color=slate, width=1, dash="dot"), row=2, col=1)
        fig.add_scatter(x=t, y=pe, mode="lines", line=dict(color=rust, width=2), row=2, col=1)
        # Porosity.
        fig.add_scatter(x=t, y=por, mode="lines", line=dict(color=slate, width=2.5), row=2, col=2)
        # Conservation witnesses (log — both hug machine epsilon / zero).
        fig.add_scatter(x=t, y=[max(v, 1e-18) for v in ci], mode="lines",
                        line=dict(color=ink, width=2), name="|charge imbalance|", row=2, col=3)
        fig.add_scatter(x=t, y=[max(v, 1e-18) for v in fdr], mode="lines",
                        line=dict(color=teal, width=2, dash="dot"), name="|flux div. residual|", row=2, col=3)

        fig.update_xaxes(title_text="time", showgrid=True, gridcolor="#eef2f7")
        fig.update_yaxes(showgrid=True, gridcolor="#eef2f7")
        fig.update_yaxes(type="log", row=2, col=3)
        fig.update_layout(
            title=dict(text=self.config.get("title") or "Campaign 0 — real vent reactor",
                       font=dict(size=16, color=ink)),
            template="plotly_white", height=620, showlegend=True,
            legend=dict(orientation="h", y=-0.08, x=0.66, font=dict(size=10)),
            margin=dict(l=60, r=30, t=70, b=60), font=dict(color=ink),
        )
        return fig.to_html(full_html=True, include_plotlyjs="cdn", config={"displayModeBar": False})


class CarbonFixationViz(Visualization):
    """Campaign-I real geology->reduced-carbon trajectory: product yields
    (formate/acetate/pyruvate), the pH-gradient proton-motive force + current,
    the real eQuilibrator ΔG'/feasibility gate, and net organic-carbon flux.

    Drives the genuine eQuilibrator + FiPy composite
    (``viva_genesis.composites.carbon_fixation``).
    """

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign I — geology to reduced carbon"},
        "n_steps": {"_type": "integer", "_default": 120},
        "gradient_efficiency": {"_type": "float", "_default": 1.0},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from .core import build_core
        from .composites.carbon_fixation import hydrothermal_carbon_fixation
        core = build_core()
        doc = hydrothermal_carbon_fixation(
            core, gradient_efficiency=float(self.config["gradient_efficiency"]))
        sim = Composite({"state": doc}, core=core)
        sim.run(float(self.config["n_steps"]))
        rows = gather_emitter_results(sim)[("emitter",)]
        return {"html": self._figure(rows)}

    def _figure(self, rows) -> str:
        from plotly.subplots import make_subplots

        def col(k):
            return [r[k] for r in rows if k in r]

        t = [r.get("global_time", i) for i, r in enumerate(rows)]
        formate = [v * 1000.0 for v in col("formate")]      # mM
        acetate = [v * 1e6 for v in col("acetate")]         # uM
        pyruvate = [v * 1e6 for v in col("pyruvate")]       # uM
        pmf = [v * 1000.0 for v in col("pmf")]              # mV
        jcur = col("current_density")
        ncf = col("net_carbon_flux")
        dgf = col("dg_formate")
        feas = col("feasible_formate")

        ink, teal, amber, slate, rust, violet = "#1e293b", "#0d9488", "#d97706", "#64748b", "#b91c1c", "#7c3aed"
        fig = make_subplots(
            rows=2, cols=3, vertical_spacing=0.17, horizontal_spacing=0.09,
            subplot_titles=(
                "Formate (mM)", "Acetate / pyruvate (µM)", "Net carbon flux (mol/s)",
                "Proton-motive force (mV)", "Current density (A/m²)", "ΔG′ formate & feasibility",
            ),
        )
        fig.add_hrect(y0=0, y1=200, line_width=0, fillcolor=teal, opacity=0.06, row=1, col=1)
        fig.add_scatter(x=t, y=formate, mode="lines", line=dict(color=teal, width=2.5), row=1, col=1)
        fig.add_scatter(x=t, y=acetate, mode="lines", line=dict(color=amber, width=2), name="acetate", row=1, col=2)
        fig.add_scatter(x=t, y=pyruvate, mode="lines", line=dict(color=rust, width=2, dash="dot"), name="pyruvate", row=1, col=2)
        fig.add_scatter(x=t, y=ncf, mode="lines", line=dict(color=ink, width=2), row=1, col=3)
        fig.add_scatter(x=t, y=pmf, mode="lines", line=dict(color=violet, width=2.5), row=2, col=1)
        fig.add_scatter(x=t, y=jcur, mode="lines", line=dict(color=slate, width=2), row=2, col=2)
        fig.add_scatter(x=t, y=dgf, mode="lines", line=dict(color=rust, width=2), name="ΔG′ (kJ/mol)", row=2, col=3)
        fig.add_scatter(x=t, y=[f * 100 for f in feas], mode="lines", line=dict(color=teal, width=2, dash="dot"), name="feasibility ×100", row=2, col=3)
        fig.add_hline(y=0.0, line=dict(color=slate, width=1, dash="dot"), row=2, col=3)

        fig.update_xaxes(title_text="time", showgrid=True, gridcolor="#eef2f7")
        fig.update_yaxes(showgrid=True, gridcolor="#eef2f7")
        fig.update_layout(
            title=dict(text=self.config.get("title") or "Campaign I — geology to reduced carbon",
                       font=dict(size=16, color=ink)),
            template="plotly_white", height=620, showlegend=True,
            legend=dict(orientation="h", y=-0.08, x=0.3, font=dict(size=10)),
            margin=dict(l=60, r=30, t=70, b=60), font=dict(color=ink),
        )
        return fig.to_html(full_html=True, include_plotlyjs="cdn", config={"displayModeBar": False})


class ProtometabolismViz(Visualization):
    """Campaign-II real protometabolic-network trajectory: rTCA-fragment species
    (OAA / acetate / succinate), the net carbon throughput under feed+washout, and
    the autocatalytic gain — the emergent metabolism-like behavior.

    Drives the genuine libRoadRunner/Tellurium composite
    (``viva_genesis.composites.protometabolism``).
    """

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign II — protometabolic network"},
        "n_steps": {"_type": "integer", "_default": 120},
        "feed_CO2": {"_type": "float", "_default": 2.0e-3},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    def update(self, state=None):
        from .core import build_core
        from .composites.protometabolism import protometabolic_network
        core = build_core()
        doc = protometabolic_network(
            core, feed_CO2=float(self.config["feed_CO2"]))
        sim = Composite({"state": doc}, core=core)
        sim.run(float(self.config["n_steps"]))
        rows = gather_emitter_results(sim)[("emitter",)]
        return {"html": self._figure(rows)}

    def _figure(self, rows) -> str:
        from plotly.subplots import make_subplots

        def col(k):
            return [r[k] for r in rows if k in r]

        t = [r.get("global_time", i) for i, r in enumerate(rows)]
        oaa = [v * 1e3 for v in col("OAA")]            # mM
        acetate = [v * 1e3 for v in col("acetate")]   # mM
        succinate = [v * 1e3 for v in col("succinate")]
        ncf = col("net_carbon_flux")
        gain = col("autocatalytic_gain")

        ink, teal, amber, slate, rust = "#1e293b", "#0d9488", "#d97706", "#64748b", "#b91c1c"
        fig = make_subplots(
            rows=1, cols=3, horizontal_spacing=0.08,
            subplot_titles=("rTCA-fragment species (mM)", "Net carbon throughput (mol/s)",
                            "Autocatalytic gain"),
        )
        fig.add_scatter(x=t, y=oaa, mode="lines", line=dict(color=teal, width=2.5), name="OAA", row=1, col=1)
        fig.add_scatter(x=t, y=acetate, mode="lines", line=dict(color=amber, width=2), name="acetate", row=1, col=1)
        fig.add_scatter(x=t, y=succinate, mode="lines", line=dict(color=rust, width=2, dash="dot"), name="succinate", row=1, col=1)
        fig.add_scatter(x=t, y=ncf, mode="lines", line=dict(color=ink, width=2.5), row=1, col=2)
        fig.add_hline(y=1.0, line=dict(color=slate, width=1, dash="dot"), row=1, col=3)
        fig.add_scatter(x=t, y=gain, mode="lines", line=dict(color=rust, width=2.5), row=1, col=3)

        fig.update_xaxes(title_text="time", showgrid=True, gridcolor="#eef2f7")
        fig.update_yaxes(showgrid=True, gridcolor="#eef2f7")
        fig.update_layout(
            title=dict(text=self.config.get("title") or "Campaign II — protometabolic network",
                       font=dict(size=16, color=ink)),
            template="plotly_white", height=380, showlegend=True,
            legend=dict(orientation="h", y=-0.2, x=0.0, font=dict(size=10)),
            margin=dict(l=60, r=30, t=70, b=60), font=dict(color=ink),
        )
        return fig.to_html(full_html=True, include_plotlyjs="cdn", config={"displayModeBar": False})


def render_declared_viz_json(study_dir, run_id, ws_root):
    """Render a study's declared ``visualizations[]`` to
    ``<ws_root>/.pbg/runs/<run_id>/viz.json`` ({viz_name: html}) — the file the
    workbench native viz gallery (study_native_gallery) reads for the latest run.

    Mirrors ``run_runner._render_viz`` for the canonical ``sims/run.py`` path,
    which otherwise leaves the live gallery empty (only the committed
    ``viz/*.html`` disk file surfaces via the auto-discover path).
    """
    import json
    import yaml
    from pathlib import Path
    from .core import build_core

    study_dir = Path(study_dir)
    ws_root = Path(ws_root)
    spec = yaml.safe_load((study_dir / "study.yaml").read_text(encoding="utf-8")) or {}
    core = build_core()
    reg = core.link_registry
    panels = {}
    for entry in (spec.get("visualizations") or []):
        name = entry.get("name") or "viz"
        addr = (entry.get("address") or "").split(":")[-1]  # local:<Class> -> <Class>
        try:
            cls = reg[addr]
        except Exception:  # noqa: BLE001
            continue
        schema_keys = set(getattr(cls, "config_schema", {}) or {})
        cfg = {k: v for k, v in (entry.get("config") or {}).items() if k in schema_keys}
        try:
            out = cls(config=cfg, core=build_core()).update({})
            html = out.get("html") if isinstance(out, dict) else None
            if isinstance(html, str) and html.strip():
                panels[name] = html
        except Exception:  # noqa: BLE001 — one viz must not fail the run
            continue
    run_dir = ws_root / ".pbg" / "runs" / str(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "viz.json").write_text(json.dumps(panels, default=str), encoding="utf-8")
    return list(panels)

class VentCrossSection(Visualization):
    """Campaign-0 REAL 2-D vent cross-section — every pixel a FiPy cell.

    Runs the ``serpentinizing_vent_reactor`` composite step by step and snapshots
    the genuine 2-D finite-volume field each step (temperature, the reducing-power
    solute tracer, and the pH / porosity fields derived from the real transported
    solute). Renders (a) a STATIC settled cross-section of all four fields and
    (b) an ANIMATED temperature field — the vent lighting up and settling into the
    Lost City window. Cold acidic ocean on the left, the hot alkaline conduit on
    the right; the across-wall gradient is the defining vent structure.
    """

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign 0 — real 2-D vent cross-section (FiPy)"},
        "n_steps": {"_type": "integer", "_default": 60},
        "flow_velocity": {"_type": "float", "_default": 1.0e-3},
        "olivine_rate": {"_type": "float", "_default": 0.15},
        "max_frames": {"_type": "integer", "_default": 30},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    @staticmethod
    def _find_reactor(node):
        if isinstance(node, dict):
            inst = node.get("instance")
            if inst is not None and type(inst).__name__ == "FipyReactiveTransportProcess":
                return inst
            for v in node.values():
                r = VentCrossSection._find_reactor(v)
                if r is not None:
                    return r
        return None

    def update(self, state=None):
        from .core import build_core
        from .composites.vent_reactor import serpentinizing_vent_reactor
        from .transport.fipy_reactor import spatial_field

        core = build_core()
        doc = serpentinizing_vent_reactor(
            core,
            flow_velocity=float(self.config["flow_velocity"]),
            olivine_rate=float(self.config["olivine_rate"]),
        )
        sim = Composite({"state": doc}, core=core)
        reactor = self._find_reactor(sim.state)
        # VIZ-ONLY cold start: build the mesh at seawater temperature and mark it
        # seeded so the reactor does NOT warm-start the field to the interface
        # temperature. The animation then shows the field heating up from cold —
        # the wall lighting up — instead of appearing near-settled from frame 1.
        # (The graded composite keeps its own warm-start; this is a separate run.)
        if reactor is not None:
            reactor._build()
            reactor._T.setValue(float(reactor.config["seawater_temp"]))
            reactor._S.setValue(0.0)
            reactor._seeded = True
        n = int(self.config["n_steps"])
        frames = []
        for _ in range(n):
            sim.run(1)
            rows = gather_emitter_results(sim)[("emitter",)]
            last = rows[-1] if rows else {}
            f = spatial_field(reactor, {
                "pH": float(last.get("pH", 9.4)),
                "pH_eq": float(last.get("pH_eq", 0.0) or 0.0),
                "porosity": float(last.get("porosity", 0.35)),
            })
            if f.get("nx"):
                f["t_c"] = [[v - 273.15 for v in row] for row in f["temperature"]]
                f["settled_T"] = float(last.get("temperature", 0.0)) - 273.15
                f["settled_pH"] = float(last.get("pH", 0.0))
                frames.append(f)
        return {"html": self._figure(frames)}

    def _figure(self, frames) -> str:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        if not frames:
            return "<p>No field produced (reactor did not step).</p>"
        last = frames[-1]
        ext = last["extent"]
        nx, ny = last["nx"], last["ny"]
        xs = [(i + 0.5) * (ext[1] / nx) * 100.0 for i in range(nx)]   # cm across the wall
        ys = [(j + 0.5) * (ext[3] / ny) * 100.0 for j in range(ny)]   # cm up the chimney
        ink = "#1e293b"

        # ---- STATIC: the four settled fields as a clean 2x2 ----
        stat = make_subplots(
            rows=2, cols=2, horizontal_spacing=0.17, vertical_spacing=0.15,
            subplot_titles=("Temperature (\u00b0C)", "pH  (acidic \u2192 alkaline)",
                            "Reducing power (H\u2082 + alkalinity)", "Porosity"))
        specs = [
            (last["t_c"], "Inferno", 1, 1, 0.42, 0.80),
            (last["pH"], "Tealgrn", 1, 2, 1.00, 0.80),
            (last["solute"], "Viridis", 2, 1, 0.42, 0.195),
            (last["porosity"], "YlOrBr", 2, 2, 1.00, 0.195),
        ]
        for z, cs, r, c, cbx, cby in specs:
            stat.add_trace(go.Heatmap(z=z, x=xs, y=ys, colorscale=cs,
                                      colorbar=dict(len=0.40, thickness=11, x=cbx, y=cby)),
                           row=r, col=c)
        # Precipitation front: a contour of the REAL porosity field at its midpoint —
        # where the alkaline vent fluid meets the ocean and the carbonate/brucite
        # chimney precipitates. Overlaid on the temperature panel (1,1).
        pz = last["porosity"]
        pflat = [v for rrow in pz for v in rrow]
        lvl = (min(pflat) + max(pflat)) / 2.0
        stat.add_trace(go.Contour(z=pz, x=xs, y=ys, showscale=False,
                                  contours=dict(start=lvl, end=lvl, coloring="lines"),
                                  line=dict(color="#e2e8f0", width=1.6, dash="dot"),
                                  hoverinfo="skip"), row=1, col=1)
        # Upflow: the serpentinized fluid percolates up the conduit — a couple of
        # arrows on the hot (right) side mark the real +y flow direction.
        xr = xs[int(len(xs) * 0.82)]
        for yfrac in (0.30, 0.68):
            y0 = ys[int(len(ys) * (yfrac - 0.12))]; y1 = ys[int(len(ys) * (yfrac + 0.12))]
            stat.add_annotation(x=xr, y=y1, ax=xr, ay=y0, xref="x", yref="y",
                                axref="x", ayref="y", showarrow=True, arrowhead=2,
                                arrowwidth=1.6, arrowcolor="rgba(255,255,255,0.85)", text="")
        stat.add_annotation(x=xr, y=ys[-1], xref="x", yref="y", text="upflow",
                            showarrow=False, yshift=8, font=dict(size=9, color="#fde68a"))
        stat.update_xaxes(showgrid=False, zeroline=False,
                          title_text="across the wall (cm)", title_font=dict(size=10))
        stat.update_yaxes(showgrid=False, zeroline=False,
                          title_text="up (cm)", title_font=dict(size=10))
        stat.update_layout(
            template="plotly_white", height=560, width=820,
            title=dict(text="Settled cross-section  \u00b7  cold acidic OCEAN (left)  \u2192  hot alkaline CONDUIT (right)",
                       font=dict(size=14, color=ink), x=0.5, xanchor="center"),
            margin=dict(l=55, r=20, t=90, b=50), font=dict(color=ink))

        # ---- MOTION: the temperature field heating up (generous, uncramped) ----
        step = max(1, len(frames) // int(self.config["max_frames"]))
        keep = frames[::step] + [frames[-1]]
        zmin = min(min(min(r) for r in f["t_c"]) for f in keep)
        zmax = max(max(max(r) for r in f["t_c"]) for f in keep)
        anim = go.Figure(
            data=[go.Heatmap(z=keep[0]["t_c"], x=xs, y=ys, colorscale="Inferno",
                             zmin=zmin, zmax=zmax, colorbar=dict(title="\u00b0C", thickness=13, len=0.9))],
            frames=[go.Frame(data=[go.Heatmap(z=f["t_c"], x=xs, y=ys, colorscale="Inferno",
                                              zmin=zmin, zmax=zmax)], name=str(i))
                    for i, f in enumerate(keep)])
        anim.update_xaxes(showgrid=False, zeroline=False, title_text="across the wall (cm)")
        anim.update_yaxes(showgrid=False, zeroline=False, title_text="up the chimney (cm)")
        anim.update_layout(
            template="plotly_white", height=460, width=760,
            title=dict(text="Temperature field heating up over the run", x=0.5, xanchor="center",
                       y=0.97, font=dict(size=14, color=ink)),
            margin=dict(l=60, r=20, t=100, b=70), font=dict(color=ink),
            updatemenus=[dict(type="buttons", direction="left", x=0.0, y=1.12, xanchor="left", yanchor="top",
                pad=dict(t=0, r=6), showactive=False, buttons=[
                    dict(label="\u25b6 Play", method="animate",
                         args=[None, dict(frame=dict(duration=90, redraw=True), fromcurrent=True)]),
                    dict(label="\u23f8 Pause", method="animate",
                         args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")]),
                ])],
            sliders=[dict(active=0, x=0.08, len=0.88, y=-0.16, pad=dict(t=0),
                currentvalue=dict(visible=False),
                steps=[dict(method="animate", label="",
                            args=[[str(i)], dict(frame=dict(duration=0, redraw=True), mode="immediate")])
                       for i in range(len(keep))])])

        cap = (
            "<div style='max-width:860px;margin:12px auto 4px;padding:0 16px;color:#334155;"
            "font-size:13.5px;line-height:1.55'>"
            "<b>A cross-section through the chimney wall</b> \u2014 a real 2-D FiPy finite-volume "
            "field, <b>every pixel a solved cell</b>. Cold acidic seawater bathes the outer wall "
            "(left); the hot alkaline serpentinized fluid percolates up the conduit (right). The "
            "<b>gradient across the wall</b> is the engine of the vent. "
            f"<b>Settled: {last['settled_T']:.0f}\u202f\u00b0C, pH {last['settled_pH']:.2f}</b> "
            "(the Lost City window).</div>")
        s_html = stat.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        a_html = anim.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})
        return ("<!doctype html><html><head><meta charset='utf-8'></head>"
                "<body style='margin:0;font-family:-apple-system,system-ui,sans-serif;background:#fff'>"
                f"{cap}"
                "<div style='display:flex;justify-content:center'>" + s_html + "</div>"
                "<div style='display:flex;justify-content:center;margin-top:8px'>" + a_html + "</div>"
                "</body></html>")

class ProtonGradientProfile(Visualization):
    """Campaign-I REAL proton gradient across the Fe/Ni-S barrier — every value a
    FiPy cell. Runs the ``hydrothermal_carbon_fixation`` composite step by step and
    snapshots the genuine 1-D Nernst-Planck proton profile (ocean acidic → vent
    alkaline) each step, beside the molecular products (formate / acetate /
    pyruvate) the gradient drives. Static settled profile + an animated profile;
    the favorable (gradient_efficiency 1.0) vs Tutolo-2026 (~0.1) arm is a config.
    """

    config_schema = {
        "title": {"_type": "string", "_default": "Campaign I — proton gradient → reduced carbon"},
        "n_steps": {"_type": "integer", "_default": 80},
        "gradient_efficiency": {"_type": "float", "_default": 1.0},
        "max_frames": {"_type": "integer", "_default": 30},
    }

    def inputs(self):
        return {}

    def outputs(self):
        return {"html": "string"}

    @staticmethod
    def _find_gradient(node):
        if isinstance(node, dict):
            inst = node.get("instance")
            if inst is not None and type(inst).__name__ == "PhGradientNernstPlanckProcess":
                return inst
            for v in node.values():
                r = ProtonGradientProfile._find_gradient(v)
                if r is not None:
                    return r
        return None

    def update(self, state=None):
        from .core import build_core
        from .composites.carbon_fixation import hydrothermal_carbon_fixation
        from .electrochemistry.ph_gradient import spatial_profile

        core = build_core()
        doc = hydrothermal_carbon_fixation(
            core, gradient_efficiency=float(self.config["gradient_efficiency"]))
        sim = Composite({"state": doc}, core=core)
        grad = self._find_gradient(sim.state)
        n = int(self.config["n_steps"])
        profiles, rows = [], []
        for _ in range(n):
            sim.run(1)
            rows = gather_emitter_results(sim)[("emitter",)]
            p = spatial_profile(grad)
            if p.get("x_cm"):
                profiles.append(p)
        return {"html": self._figure(profiles, rows)}

    def _figure(self, profiles, rows) -> str:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        if not profiles:
            return "<p>No proton profile produced.</p>"
        ink, teal, amber, rust = "#1e293b", "#0d9488", "#d97706", "#b91c1c"
        last = profiles[-1]
        x = last["x_cm"]
        t = [r.get("global_time", i) for i, r in enumerate(rows)]

        def col(k):
            return [r.get(k) for r in rows if k in r]

        # static: settled proton profile (across barrier) + products over time
        stat = make_subplots(rows=1, cols=2, horizontal_spacing=0.13,
            subplot_titles=("Settled pH profile across the barrier",
                            "Reduced-carbon products (M)"))
        stat.add_hrect(y0=9.0, y1=11.0, line_width=0, fillcolor=teal, opacity=0.06, row=1, col=1)
        stat.add_scatter(x=x, y=last["pH"], mode="lines", line=dict(color=teal, width=3),
                         name="pH", row=1, col=1)
        stat.add_annotation(x=x[0], y=last["pH"][0], text="◀ ocean (acidic)", showarrow=False,
                            font=dict(size=10, color="#2563eb"), xanchor="left", row=1, col=1)
        stat.add_annotation(x=x[-1], y=last["pH"][-1], text="vent (alkaline) ▶", showarrow=False,
                            font=dict(size=10, color="#b45309"), xanchor="right", row=1, col=1)
        for k, c in (("formate", teal), ("acetate", amber), ("pyruvate", rust)):
            y = col(k)
            if y:
                stat.add_scatter(x=t, y=y, mode="lines", line=dict(color=c, width=2.5),
                                 name=k, row=1, col=2)
        stat.update_xaxes(title_text="across the barrier (cm)", row=1, col=1, showgrid=False)
        stat.update_xaxes(title_text="time", row=1, col=2, showgrid=True, gridcolor="#eef2f7")
        stat.update_yaxes(title_text="pH", row=1, col=1, showgrid=True, gridcolor="#eef2f7")
        stat.update_yaxes(title_text="concentration (M)", row=1, col=2, showgrid=True, gridcolor="#eef2f7")
        pmf = col("pmf")
        pmf_mv = (pmf[-1] * 1000.0) if pmf else 0.0
        stat.update_layout(
            template="plotly_white", height=420, width=880, showlegend=True,
            legend=dict(orientation="h", y=-0.18, x=0.62, font=dict(size=10)),
            title=dict(text=(self.config.get("title") or "Proton gradient → reduced carbon") +
                       f"   ·   pmf {pmf_mv:.0f} mV",
                       font=dict(size=14, color=ink), x=0.5, xanchor="center"),
            margin=dict(l=55, r=20, t=80, b=70), font=dict(color=ink))

        # motion: the reduced-carbon products ACCUMULATING over the run (the
        # proton profile is a steady solve — nothing to animate there — but the
        # products genuinely build). Normalise each to its own final value so all
        # three (formate ~0.2 M down to pyruvate ~1e-5 M) are visible growing.
        fo, ac, py = col("formate"), col("acetate"), col("pyruvate")
        nmax = [max(fo or [0]) or 1e-30, max(ac or [0]) or 1e-30, max(py or [0]) or 1e-30]
        npts = min(len(fo), len(ac), len(py))
        fstep = max(1, npts // int(self.config["max_frames"]))
        idxs = list(range(0, npts, fstep)) + ([npts - 1] if npts else [])
        cats = ["formate<br>→ %.2g M" % nmax[0], "acetate<br>→ %.2g M" % nmax[1],
                "pyruvate<br>→ %.2g M" % nmax[2]]
        cols = [teal, amber, rust]
        def _frac(k):
            return [fo[k] / nmax[0], ac[k] / nmax[1], py[k] / nmax[2]]
        anim = go.Figure(
            data=[go.Bar(x=cats, y=_frac(idxs[0]) if idxs else [0, 0, 0],
                         marker_color=cols)],
            frames=[go.Frame(data=[go.Bar(x=cats, y=_frac(k), marker_color=cols)], name=str(j))
                    for j, k in enumerate(idxs)])
        anim.update_yaxes(title_text="fraction of final yield", range=[0, 1.08],
                          showgrid=True, gridcolor="#eef2f7")
        anim.update_layout(
            template="plotly_white", height=360, width=560, bargap=0.45,
            title=dict(text="the products accumulating (real eQuilibrator-gated kinetics)",
                       x=0.5, xanchor="center", y=0.97, font=dict(size=13, color=ink)),
            margin=dict(l=55, r=20, t=80, b=60), font=dict(color=ink),
            updatemenus=[dict(type="buttons", direction="left", x=0.0, y=1.14, xanchor="left",
                showactive=False, buttons=[
                    dict(label="▶ Play", method="animate",
                         args=[None, dict(frame=dict(duration=90, redraw=True), fromcurrent=True)]),
                    dict(label="⏸ Pause", method="animate",
                         args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")]),
                ])],
            sliders=[dict(active=0, x=0.08, len=0.88, y=-0.14, currentvalue=dict(visible=False),
                steps=[dict(method="animate", label="",
                            args=[[str(i)], dict(frame=dict(duration=0, redraw=True), mode="immediate")])
                       for i in range(len(idxs))])])

        cap = (
            "<div style='max-width:880px;margin:12px auto 4px;padding:0 16px;color:#334155;"
            "font-size:13.5px;line-height:1.55'>"
            "<b>The proton gradient that powers the first carbon fixation</b> — the real 1-D "
            "Nernst-Planck proton profile across the Fe/Ni-S barrier (every value a FiPy cell), "
            "from the acidic ocean to the alkaline vent. That gradient is the proton-motive force "
            "driving H₂ + CO₂ → formate / acetate / pyruvate (right).</div>")
        s_html = stat.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})
        a_html = anim.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})
        return ("<!doctype html><html><head><meta charset='utf-8'></head>"
                "<body style='margin:0;font-family:-apple-system,system-ui,sans-serif;background:#fff'>"
                f"{cap}"
                "<div style='display:flex;justify-content:center'>" + s_html + "</div>"
                "<div style='display:flex;justify-content:center;margin-top:8px'>" + a_html + "</div>"
                "</body></html>")
