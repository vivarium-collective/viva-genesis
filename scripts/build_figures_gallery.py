#!/usr/bin/env python
"""Build a single navigable gallery of an investigation's committed figures.

The dashboard's ``↓ figures`` export is a zip of per-study figure files, which is
tedious to browse. This produces one page you can open:

    <out>/index.html   — a sticky-sidebar table of contents (studies in
                         investigation order → their figures), each figure shown
                         inline (HTML via iframe, images via <img>) with its own
                         ⬇ download button.
    <out>/figures/<study>__<name>.<ext>  — flat, clearly-named copies, so an
                         individual download has a sensible filename.

Self-contained to the output folder; interactive HTML figures load Plotly from
their CDN exactly as they already do. Run from the workspace root:

    python scripts/build_figures_gallery.py                       # origins-of-life-vent
    python scripts/build_figures_gallery.py --investigation <name> --out <dir>
"""
from __future__ import annotations

import argparse
import re
import shutil
from html import escape
from pathlib import Path

import yaml

IMG_EXT = {".svg", ".png", ".gif", ".jpg", ".jpeg", ".webp"}


def _member_slugs(inv: dict) -> list[str]:
    """Study slugs in declared order (``studies:`` list, else ``at_a_glance``)."""
    slugs = list(inv.get("studies") or [])
    if not slugs:
        slugs = [s.get("study") for s in (inv.get("at_a_glance") or []) if isinstance(s, dict) and s.get("study")]
    return [s for s in slugs if s]


def _study_title(studies_dir: Path, slug: str) -> str:
    try:
        y = yaml.safe_load((studies_dir / slug / "study.yaml").read_text()) or {}
        return str(y.get("title") or slug)
    except Exception:
        return slug


def _fig_title(html: str, fallback: str) -> str:
    """The header-band title (styled ``line-height:1.25``), else the fallback."""
    m = re.search(r'line-height:1\.25">([^<]+)<', html)
    return (m.group(1).strip() if m else "") or fallback


_HEAD = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>{inv} — figure gallery</title>
<link rel=preconnect href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel=stylesheet>
<style>
:root{{--ink:#1e293b;--soft:#475569;--muted:#94a3b8;--line:#e2e8f0;--bg:#f1f5f9;--teal:#0d9488}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:Inter,system-ui,sans-serif;color:var(--ink);background:var(--bg)}}
.wrap{{display:flex;align-items:flex-start;max-width:1400px;margin:0 auto}}
nav{{position:sticky;top:0;align-self:flex-start;width:300px;height:100vh;overflow:auto;
    padding:20px 14px;border-right:1px solid var(--line);background:#fff;font-size:13px}}
nav h1{{font-size:15px;margin:0 0 4px}} nav .sub{{color:var(--soft);font-size:12px;margin:0 0 14px}}
nav a{{display:block;color:var(--soft);text-decoration:none;padding:3px 8px;border-radius:6px;line-height:1.35}}
nav a:hover{{background:var(--bg);color:var(--ink)}}
nav .s{{margin-top:10px;font-weight:600;color:var(--ink)}} nav .f{{padding-left:18px;font-size:12px}}
main{{flex:1;min-width:0;padding:22px 26px}}
.study{{scroll-margin-top:14px}} .study>h2{{font-size:17px;margin:26px 0 2px}}
.study>.role{{color:var(--soft);font-size:12.5px;margin:0 0 12px}}
.card{{background:#fff;border:1px solid var(--line);border-radius:12px;margin:14px 0;overflow:hidden;scroll-margin-top:14px}}
.card .bar{{display:flex;align-items:center;gap:10px;padding:9px 14px;border-bottom:1px solid var(--line);background:#fcfdfe}}
.card .bar .name{{font-weight:600;font-size:13px}}
.card .bar .dl{{margin-left:auto;font-size:12px;text-decoration:none;color:var(--teal);
     border:1px solid var(--teal);border-radius:999px;padding:3px 11px;white-space:nowrap}}
.card .bar .dl:hover{{background:var(--teal);color:#fff}}
.card iframe,.card img{{width:100%;border:0;display:block}} .card img{{padding:14px;background:#fff}}
.hdr{{padding:24px 26px 0}} .hdr h1{{font-size:22px;margin:0 0 4px}}
.hdr p{{color:var(--soft);font-size:13.5px;max-width:860px;margin:0}}
</style></head><body>
"""


def build(ws_root: Path, inv_name: str, out: Path) -> tuple[int, int]:
    studies_dir = ws_root / "workspace" / "studies"
    inv_file = ws_root / "workspace" / "investigations" / inv_name / "investigation.yaml"
    inv = yaml.safe_load(inv_file.read_text()) if inv_file.is_file() else {}
    order = _member_slugs(inv)
    on_disk = sorted(p.name for p in studies_dir.iterdir() if (p / "study.yaml").exists())
    order += [s for s in on_disk if s not in order]

    figs_dir = out / "figures"
    if out.exists():
        shutil.rmtree(out)
    figs_dir.mkdir(parents=True)

    nav, body = [], []
    n_fig = n_study = 0
    for slug in order:
        vdir = studies_dir / slug / "viz"
        if not vdir.is_dir():
            continue
        items = sorted(p for p in vdir.iterdir() if p.is_file() and p.suffix.lower() in ({".html"} | IMG_EXT))
        if not items:
            continue
        n_study += 1
        title = _study_title(studies_dir, slug)
        nav.append(f'<div class="s"><a href="#{slug}">{escape(title)}</a></div>')
        body.append(f'<section class="study" id="{slug}"><h2>{escape(title)}</h2>'
                    f'<p class="role">{escape(slug)}</p>')
        for p in items:
            is_html = p.suffix.lower() == ".html"
            label = _fig_title(p.read_text(errors="replace"), p.stem) if is_html else p.stem
            flat = f"{slug}__{p.name}"
            shutil.copyfile(p, figs_dir / flat)
            n_fig += 1
            anchor = f"{slug}__{p.stem}"
            nav.append(f'<a class="f" href="#{anchor}">{escape(label)}</a>')
            if is_html:
                tall = any(k in p.stem for k in ("three-view", "energy-budget", "internalization", "window", "network"))
                media = f'<iframe loading="lazy" src="figures/{escape(flat)}" height="{900 if tall else 640}"></iframe>'
            else:
                media = f'<img loading="lazy" src="figures/{escape(flat)}" alt="{escape(label)}">'
            body.append(
                f'<div class="card" id="{anchor}"><div class="bar"><span class="name">{escape(label)}</span>'
                f'<a class="dl" href="figures/{escape(flat)}" download>&#8595; download</a></div>{media}</div>')
        body.append("</section>")

    hdr = (f'<div class="hdr"><h1>{escape(inv_name)} &mdash; figure gallery</h1>'
           f'<p>{n_fig} figures across {n_study} studies, one visual language. Use the list on the left to '
           f'jump to any study; each figure has its own &#8595; download.</p></div>')
    page = (_HEAD.format(inv=escape(inv_name)) + '<div class="wrap">'
            f'<nav><h1>Figures</h1><p class="sub">{n_fig} figures &middot; {n_study} studies</p>'
            + "".join(nav) + '</nav><main>' + hdr + "".join(body) + '</main></div></body></html>')
    (out / "index.html").write_text(page)
    return n_study, n_fig


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--investigation", default="origins-of-life-vent")
    ap.add_argument("--workspace", default=".", help="workspace root (contains workspace/)")
    ap.add_argument("--out", default=None, help="output dir (default: <investigation>-gallery)")
    a = ap.parse_args()
    ws = Path(a.workspace).resolve()
    out = Path(a.out).expanduser() if a.out else (ws / f"{a.investigation}-gallery")
    n_study, n_fig = build(ws, a.investigation, out)
    print(f"gallery: {out / 'index.html'}  ({n_study} studies, {n_fig} figures)")


if __name__ == "__main__":
    main()
