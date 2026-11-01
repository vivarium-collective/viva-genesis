#!/usr/bin/env python3
"""Render a standalone investigation report SPA from investigation.yaml + member studies.

Reads the closed eukaryogenesis investigation (executive, scientific_argument, synthesis
evidence chain) and each member study's finding/verdict, and emits a self-contained,
shareable report.html — the "report = interactive page" deliverable, generated from the
canonical data so it never drifts from the YAML.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

import yaml

INV = Path("workspace/investigations/eukaryogenesis")


def _studies():
    out = []
    for slug in yaml.safe_load((INV / "investigation.yaml").read_text())["studies"]:
        for cand in (Path("workspace/studies") / slug / "study.yaml",
                     INV / "studies" / slug / "study.yaml"):
            if cand.is_file():
                out.append((slug, yaml.safe_load(cand.read_text())))
                break
    return out


def main():
    inv = yaml.safe_load((INV / "investigation.yaml").read_text())
    e = inv.get("executive", {})
    sa = inv.get("scientific_argument", {})
    syn = inv.get("synthesis", {})
    studies = _studies()

    def esc(x):
        return html.escape(str(x))

    chain_rows = "".join(
        f"<tr><td><code>{esc(c.get('model',''))}</code></td><td>{esc(c.get('study',''))}</td>"
        f"<td>{esc(c.get('result',''))}</td></tr>"
        for c in syn.get("evidence_chain", [])
    )

    study_cards = ""
    for slug, s in studies:
        if not s.get("findings"):
            continue
        f = s["findings"][0]
        verdict = esc(s.get("verdict", "—"))
        conf = esc(s.get("confidence", ""))
        study_cards += (
            f'<div class="study"><div class="sh"><h3>{esc(s.get("title", slug))}</h3>'
            f'<span class="badge b-{verdict}">{verdict} · {conf}</span></div>'
            f'<p class="q">{esc(s.get("question",""))}</p>'
            f'<p class="find">{esc(f.get("statement",""))}</p>'
            f'<p class="scope"><b>Inferential scope:</b> {esc(f.get("inferential_scope",""))}</p></div>'
        )

    data = {
        "title": inv.get("title", "eukaryogenesis"),
        "question": inv.get("question", ""),
        "executive": {k: e.get(k) for k in ("what_is_this", "verdict", "verdict_status", "verdict_detail", "central_gap")},
        "argument": sa,
        "synthesis_headline": syn.get("headline", ""),
    }
    page = _HTML
    page = page.replace("__DATA__", json.dumps(data))
    page = page.replace("__CHAIN__", chain_rows)
    page = page.replace("__STUDIES__", study_cards)
    (INV / "report.html").write_text(page, encoding="utf-8")
    print(f"report -> {INV/'report.html'} ({len((INV/'report.html').read_text())} bytes, {len(studies)} studies)")


_HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Eukaryogenesis — Investigation Report</title>
<style>
:root{--bg:#0f1221;--panel:#171a2e;--ink:#e8ebff;--mut:#9aa3c7;--line:#2a2f52;--accent:#6b8bff;--ok:#3ecf8e;--warn:#e0a44a}
:root:not([data-theme="light"]){color-scheme:dark}
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]){--bg:#f6f7fb;--panel:#fff;--ink:#1a1c2e;--mut:#5a6187;--line:#e2e5f0;--accent:#3b4bd8;color-scheme:light}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15.5px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:34px 18px 80px}
h1{font-size:27px;margin:0 0 6px;letter-spacing:-.4px}
.status{display:inline-block;font-size:12px;font-weight:600;padding:3px 10px;border-radius:999px;background:var(--ok);color:#06231a;margin-bottom:16px}
h2{font-size:17px;margin:30px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}
h3{font-size:15px;margin:0}
.q{color:var(--mut);font-size:14px;margin:4px 0 20px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:12px 0}
.verdict{border-left:3px solid var(--accent)}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin-top:8px}
td{border-top:1px solid var(--line);padding:8px 8px;vertical-align:top}
td:first-child{white-space:nowrap;color:var(--accent)}
ul{margin:6px 0;padding-left:20px}li{margin:4px 0}
.study{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:10px 0}
.sh{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.find{margin:8px 0 6px}.scope{color:var(--mut);font-size:12.5px;margin:0}
.badge{font-size:11px;font-weight:600;padding:2px 9px;border-radius:999px;background:var(--line);color:var(--ink);white-space:nowrap}
.b-supported{background:var(--ok);color:#06231a}
.fig a{display:inline-block;margin-top:8px;color:var(--accent);font-weight:600;text-decoration:none}
.fig a:hover{text-decoration:underline}
code{background:var(--line);padding:1px 6px;border-radius:5px;font-size:12.5px}
.mut{color:var(--mut)}.caveat{color:var(--warn)}
</style></head><body><div class="wrap">
<div id="app"></div>
<script>
const D=__DATA__;
const esc=s=>(s==null?"":String(s)).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const li=a=>(a||[]).map(x=>`<li>${esc(x)}</li>`).join("");
const A=D.argument||{};
document.getElementById("app").innerHTML=`
<h1>${esc(D.title)}</h1>
<div class="status">${esc(D.executive.verdict_status||"complete").toUpperCase()}</div>
<p class="q">${esc(D.question)}</p>

<div class="panel verdict"><b>Verdict.</b> ${esc(D.executive.verdict)}
<p class="mut" style="font-size:13px;margin:8px 0 0">${esc(D.executive.verdict_detail)}</p></div>

<h2>Main claim</h2>
<p>${esc(A.main_claim)}</p>
<p class="mut" style="font-size:13.5px">${esc(D.synthesis_headline)}</p>

<h2>Evidence chain — six coupled models (M1–M7)</h2>
<table><tr><th></th><th></th><th></th></tr>__CHAIN__</table>
<div class="fig panel" style="margin-top:14px">Three-axis phase diagram (242 real runs): establishment (selection × enclosure barrier; selection × persistence) + evolutionary stability (fidelity × loss).
<a href="figures/transition_phase_diagram.html">Open the phase diagram →</a></div>

<h2>Evidence for</h2><ul>${li(A.evidence_for)}</ul>
<h2>Evidence against / boundary conditions</h2><ul>${li(A.evidence_against)}</ul>

<h2>Member studies</h2>
__STUDIES__

<h2>Caveats &amp; inferential scope</h2>
<ul class="caveat">${li(A.caveats)}</ul>
<p class="mut" style="font-size:12.5px;margin-top:24px">Generated from investigation.yaml + member study findings. Resolved via the feedback-driven discovery cycle: reopen → discriminating studies → coupled models that measure → registered runs → synthesis.</p>
`;
</script></div></body></html>"""


if __name__ == "__main__":
    main()
