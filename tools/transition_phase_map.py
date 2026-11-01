#!/usr/bin/env python3
"""M4 — transition phase diagram for the reopened eukaryogenesis investigation.

Sweeps the REAL proto_endosymbiosis_coupled model (M3) across 2-D parameter grids spanning
the three transition axes, and at each grid point computes:

  * joint_feasibility_region  — the model observable (fraction reaching high-contact AND
    stable seal), and
  * net_lineage_fitness        — the integrated population-mean fitness, combining the
    frequency-dependent exchange benefit, the adhesion cost, and the sealed-lineage
    (stable internalised exchange) bonus, across the settled compartment distribution.

Two slices tile the three axes:
  A. benefit/cost (selection) x bending barrier (enclosure)   @ low perturbation
  B. benefit/cost (selection) x perturbation (persistence)    @ low bending

The result is rendered to a single interactive Plotly HTML — the real-data phase diagram of
the transition, not a schematic. net_lineage_fitness is computed here (the analysis layer
knows the energetic parameters per grid point), keeping the composite observable pure.

Inferential scope: the fitness integrates the modelled energetics + a sealing-as-stable-
exchange bonus as a transmission proxy; explicit vertical-transmission and conflict/partner-
loss dynamics are named but not separately simulated here (named deferral, not silent).
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite

from viva_genesis.core import build_core
import viva_genesis.composites.proto_endosymbiosis_coupled as P

COST = 0.3
SEALED_BONUS = 0.5         # stable internalised exchange (transmission proxy) for sealed lineages
N_STEPS = 200
GRID = 11                  # grid points per axis


def _settled(rows, key, frac=0.25):
    n = max(1, int(round(len(rows) * frac)))
    t = [float(r.get(key, float("nan"))) for r in rows[-n:]]
    t = [x for x in t if x == x]
    return sum(t) / len(t) if t else float("nan")


def run_point(core, **kw):
    doc = P.proto_endosymbiosis_coupled(core=core, cost_coeff=COST, **kw)
    comp = Composite({"state": doc}, core=core)
    rows = []
    for _ in range(N_STEPS):
        comp.run(1)
        st = comp.state
        rows.append({k: st.get(k) for k in ("n_lc", "n_hc_un", "n_hc_se", "n_hc_st")})
    jf = P.joint_feasibility_region(rows)
    # integrated net lineage fitness over the settled compartment distribution
    lc, hc_un = _settled(rows, "n_lc"), _settled(rows, "n_hc_un")
    hc_se, hc_st = _settled(rows, "n_hc_se"), _settled(rows, "n_hc_st")
    tot = lc + hc_un + hc_se + hc_st
    if not (tot > 0):
        return jf, float("nan")
    freq_high = (hc_un + hc_se + hc_st) / tot
    realized_benefit = kw["benefit_coeff"] * freq_high
    # per-compartment fitness relative to the low-contact baseline (0)
    f_hc_un = realized_benefit - COST                 # contact, pays cost, not sealed
    f_hc_se = realized_benefit - COST + SEALED_BONUS  # sealed -> stable exchange bonus
    f_hc_st = -COST                                   # paid for contact, stalled
    fitness = (hc_un * f_hc_un + hc_se * f_hc_se + hc_st * f_hc_st) / tot
    return jf, fitness


def sweep(core, xkey, xvals, ykey, yvals, fixed):
    jf = [[None] * len(xvals) for _ in yvals]
    fit = [[None] * len(xvals) for _ in yvals]
    for i, yv in enumerate(yvals):
        for j, xv in enumerate(xvals):
            kw = dict(fixed); kw[xkey] = xv; kw[ykey] = yv
            a, b = run_point(core, **kw)
            jf[i][j] = round(a, 4) if a == a else None
            fit[i][j] = round(b, 4) if b == b else None
    return jf, fit


def linspace(a, b, n):
    return [round(a + (b - a) * k / (n - 1), 4) for k in range(n)]


def main():
    core = build_core()
    benefit = linspace(0.2, 1.6, GRID)
    bending = linspace(0.1, 1.0, GRID)
    perturb = linspace(0.0, 1.0, GRID)

    print("sweeping slice A (benefit x bending) ...")
    jfA, fitA = sweep(core, "benefit_coeff", benefit, "bending_modulus", bending,
                      fixed=dict(base_adhesion=0.8, perturbation=0.1))
    print("sweeping slice B (benefit x perturbation) ...")
    jfB, fitB = sweep(core, "benefit_coeff", benefit, "perturbation", perturb,
                      fixed=dict(base_adhesion=0.8, bending_modulus=0.2))

    data = {
        "benefit": benefit, "bending": bending, "perturb": perturb,
        "sliceA": {"jf": jfA, "fit": fitA}, "sliceB": {"jf": jfB, "fit": fitB},
        "meta": {"cost": COST, "sealed_bonus": SEALED_BONUS, "steps": N_STEPS, "grid": GRID},
    }
    out = Path("workspace/investigations/eukaryogenesis/figures")
    out.mkdir(parents=True, exist_ok=True)
    (out / "transition_phase_data.json").write_text(json.dumps(data), encoding="utf-8")
    render_html(data, out / "transition_phase_diagram.html")
    print(f"phase diagram -> {out/'transition_phase_diagram.html'}")


def render_html(data, path):
    tmpl = _HTML.replace("__DATA__", json.dumps(data))
    Path(path).write_text(tmpl, encoding="utf-8")


_HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Transition Phase Diagram</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.35.2/plotly.min.js"></script>
<style>
:root{--bg:#0f1221;--panel:#171a2e;--ink:#e8ebff;--mut:#9aa3c7;--line:#2a2f52}
:root:not([data-theme="light"]){color-scheme:dark}
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]){--bg:#f6f7fb;--panel:#fff;--ink:#1a1c2e;--mut:#5a6187;--line:#e2e5f0;color-scheme:light}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:28px 16px 60px}
h1{font-size:23px;margin:0 0 4px}.sub{color:var(--mut);margin:0 0 22px;max-width:70ch}
.row{display:grid;grid-template-columns:1fr 1fr;gap:18px}@media(max-width:760px){.row{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px}
.card h2{font-size:15px;margin:0 0 2px}.card p{color:var(--mut);font-size:12.5px;margin:0 0 8px}
.plot{width:100%;height:340px}.toggle{display:inline-flex;gap:6px;margin:0 0 16px}
.toggle button{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:6px 12px;cursor:pointer;font-size:13px}
.toggle button.on{background:#3b4bd8;border-color:#3b4bd8;color:#fff}
.note{color:var(--mut);font-size:12px;margin-top:18px;max-width:78ch}
</style></head><body><div class="wrap">
<h1>Eukaryogenesis transition — phase diagram</h1>
<p class="sub">Real sweeps of the coupled <code>proto_endosymbiosis_coupled</code> model (M3). Each cell is one run; colour is the measured outcome. The feasible transition occupies a narrow region where selection-for-contact, enclosure sealing, and persistence all align.</p>
<div class="toggle"><button id="bjf" class="on">joint feasibility</button><button id="bfit">net lineage fitness</button></div>
<div class="row">
<div class="card"><h2>A · selection × enclosure barrier</h2><p>x: exchange benefit (cost=<span id="cost"></span>) · y: bending modulus · perturbation=0.1</p><div id="pA" class="plot"></div></div>
<div class="card"><h2>B · selection × persistence</h2><p>x: exchange benefit · y: perturbation · bending=0.2</p><div id="pB" class="plot"></div></div>
</div>
<p class="note">net_lineage_fitness integrates the frequency-dependent exchange benefit, the adhesion cost, and a sealed-lineage stable-exchange bonus (transmission proxy) over the settled compartment distribution; explicit vertical-transmission and conflict dynamics are named deferrals (M4+). Data embedded from the run; no schematic values.</p>
</div>
<script>
const D=__DATA__;
const css=k=>getComputedStyle(document.documentElement).getPropertyValue(k).trim();
let metric="jf";
const common={margin:{l:46,r:12,t:8,b:40},paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"rgba(0,0,0,0)",font:{color:css("--ink"),size:11}};
document.getElementById("cost").textContent=D.meta.cost;
function heat(div,slice,xv,yv,xt,yt){
  const z=D[slice][metric];
  const scale=metric==="jf"?"Viridis":"RdBu";
  const zmid=metric==="fit"?0:undefined;
  const tr={z:z,x:xv,y:yv,type:"heatmap",colorscale:scale,zmid:zmid,
    colorbar:{thickness:10,len:0.9,title:{text:metric==="jf"?"feasible":"fitness",side:"right",font:{size:10}}},
    hovertemplate:xt+"=%{x}<br>"+yt+"=%{y}<br>"+(metric==="jf"?"feasible":"fitness")+"=%{z}<extra></extra>"};
  Plotly.react(div,[tr],Object.assign({},common,{xaxis:{title:{text:xt,font:{size:11}},color:css("--mut")},yaxis:{title:{text:yt,font:{size:11}},color:css("--mut")}}),{displayModeBar:false,responsive:true});
}
function draw(){
  heat("pA","sliceA",D.benefit,D.bending,"exchange benefit","bending modulus");
  heat("pB","sliceB",D.benefit,D.perturb,"exchange benefit","perturbation");
}
document.getElementById("bjf").onclick=()=>{metric="jf";bjf.classList.add("on");bfit.classList.remove("on");draw();};
document.getElementById("bfit").onclick=()=>{metric="fit";bfit.classList.add("on");bjf.classList.remove("on");draw();};
draw();
matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change",draw);
</script></body></html>"""


if __name__ == "__main__":
    main()
