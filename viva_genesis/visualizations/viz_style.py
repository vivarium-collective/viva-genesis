"""viva_genesis.viz_style — the shared visual language for the origins-of-life-vent
investigation.

One source of truth for the "elevated scientific" design system every study figure
uses, so the sixteen studies read as one investigation rather than sixteen notebooks:

- **palette** — a small, fixed token set (``INK``/``TEAL``/``AMBER``/``SLATE``/``RUST``
  plus support tokens). The same five hex values the figures were already copying
  inline, now defined once.
- **typography** — one Inter-based stack (``FONT_STACK``, ``FONT``).
- **evidence tiers** — the campaign's three-quantity standard tiers
  (reproduction / mechanistic_prediction / conceptual_demonstration) plus the
  null-control, rendered as honest badges (``tier_badge``). A figure must never
  claim more than its tier.
- **view tags** — the World / Mechanism / Decision triad kept in sync across studies
  (``view_tag``).
- **honest uncertainty** — shared zone colours + helpers for shading an *agreement*
  region against a *solver-sensitive* / *model-structure* region, and an
  honest-negative tone for a figure whose headline is a failed gate.
- **chrome** — a figure ``header_band`` (title · phase · view · tier) and a one-line
  plain-language ``caption`` footer, composed by :func:`frame` around any inner
  figure HTML (a Plotly ``to_html`` fragment or hand-built SVG/HTML).

Pure-Python, no heavy imports at module load; Plotly is only touched by callers.
"""
from __future__ import annotations

import re
from html import escape

# --------------------------------------------------------------------------- #
# Palette — five load-bearing tokens + support.  Keep this set small; every new
# colour should map to a meaning, not a figure.
# --------------------------------------------------------------------------- #
INK = "#1e293b"      # slate-800 — primary text, axes, strong lines
TEAL = "#0d9488"     # teal-600  — primary / positive / "viable" / agreement
AMBER = "#d97706"    # amber-600 — secondary / gradient / caution / "consistent"
SLATE = "#64748b"    # slate-500 — muted / neutral / "inconsistent"
RUST = "#b91c1c"     # red-700   — negative / failed gate / honest-negative
VIOLET = "#7c3aed"   # violet-600 — a fourth categorical (e.g. "thermodynamic")

INK_SOFT = "#475569"  # slate-600 — secondary text
MUTED = "#94a3b8"     # slate-400 — tertiary text / faint marks
GRID = "#eef2f7"      # axis gridlines
HAIR = "#e2e8f0"      # hairline borders
PAPER = "#ffffff"     # figure background
PANEL = "#f8fafc"     # slate-50 — header-band / caption background

# Honest-uncertainty zone fills (translucent so data reads through them).
AGREE_FILL = "rgba(13,148,136,0.10)"      # teal — solvers / classes agree here
SENSITIVE_FILL = "rgba(217,119,6,0.13)"   # amber — answer depends on model structure
NEG_FILL = "rgba(185,28,28,0.07)"         # rust — honest-negative wash
BAND_FILL = "rgba(100,116,139,0.16)"      # slate — generic uncertainty band

FONT_STACK = "Inter, 'Helvetica Neue', Helvetica, Arial, sans-serif"


# --------------------------------------------------------------------------- #
# Time axis — real units, not abstract ticks.
#
# The engine advances in abstract steps and emits a bare ``global_time`` that is
# just the step index (0, 1, 2, …). Each composite declares its own *real* run
# timescale on ``@composite_generator(preferred_time="6 hours")`` (process-bigraph
# #245) — coarser than its internal processes' per-step intervals. These helpers
# turn the step-index axis into that real timescale so a figure reads "time
# (hours)" / "time (years)" / "generations" instead of the misleading "time (s)".
#
# Per-step real duration is ``preferred_magnitude / default_n_steps`` (both read
# off the generator's registered ``GeneratorEntry``), so the axis stays correct
# even when a visualization renders a different number of steps than the
# composite's canonical run. When ``default_n_steps`` is absent we fall back to
# spreading the declared duration across whatever steps were rendered.
# --------------------------------------------------------------------------- #

# Unit words that are counts, not durations — labelled on their own ("generations")
# rather than as "time (generations)".
_COUNT_TIME_UNITS = {
    "generation", "generations", "step", "steps", "tick", "ticks", "cycle", "cycles",
}


def parse_quantity(s):
    """Split a unit-bearing quantity string into ``(magnitude, unit)``.

    ``"6 hours"`` → ``(6.0, "hours")``; ``"60 generations"`` → ``(60.0,
    "generations")``; ``"1000 years"`` → ``(1000.0, "years")``. Returns
    ``(None, None)`` for anything unparseable.
    """
    if not isinstance(s, str):
        return (None, None)
    m = re.match(r"\s*([0-9]*\.?[0-9]+)\s*(.+?)\s*$", s)
    if not m:
        return (None, None)
    try:
        return (float(m.group(1)), m.group(2).strip())
    except ValueError:
        return (None, None)


def _time_entry(gen):
    """Resolve ``gen`` (a decorated composite-generator fn, a ``GeneratorEntry``,
    or a bare ``preferred_time`` string) to something with ``preferred_time`` /
    ``default_n_steps`` attributes, or ``None``."""
    if gen is None:
        return None
    entry = getattr(gen, "_composite_generator_entry", None)
    return entry if entry is not None else gen


def _time_fields(gen):
    entry = _time_entry(gen)
    if isinstance(entry, str):
        return (entry, None)
    if entry is None:
        return (None, None)
    return (getattr(entry, "preferred_time", None), getattr(entry, "default_n_steps", None))


def time_axis_label(gen):
    """Axis label for ``gen``'s real timescale, e.g. ``"time (hours)"`` /
    ``"generations"``. Falls back to ``"time (steps)"`` when undeclared."""
    pt, _ = _time_fields(gen)
    _, unit = parse_quantity(pt)
    if not unit:
        return "time (steps)"
    return unit if unit.lower() in _COUNT_TIME_UNITS else f"time ({unit})"


def real_time(t, gen):
    """Map a step-index / ``global_time`` sequence onto ``gen``'s real run
    duration. Returns ``(scaled_list, axis_label)``.

    ``t`` is the raw per-row time (step index). When the composite declares a
    ``preferred_time`` the values are rescaled to that unit; otherwise they are
    returned unchanged with a ``"time (steps)"`` label.
    """
    t = [float(x) for x in t] if t is not None else []
    pt, dns = _time_fields(gen)
    mag, unit = parse_quantity(pt)
    if not t or mag is None or not unit:
        return (t, "time (steps)" if t else "time")
    if dns and float(dns) > 0:
        dt = mag / float(dns)
        scaled = [x * dt for x in t]
    else:
        span = t[-1] if t[-1] else (len(t) - 1 or 1)
        scaled = [x / span * mag for x in t]
    label = unit if unit.lower() in _COUNT_TIME_UNITS else f"time ({unit})"
    return (scaled, label)


def FONT(size: int = 12, color: str = INK) -> dict:
    """The shared Plotly font dict."""
    return {"family": FONT_STACK, "color": color, "size": size}


# --------------------------------------------------------------------------- #
# Evidence tiers — the campaign's scientific standard.  A figure's badge states
# what kind of claim it is allowed to make; it must not overclaim.
# --------------------------------------------------------------------------- #
TIERS = {
    "reproduction": {
        "label": "reproduction",
        "long": "reproduces an external measured / established result",
        "color": TEAL,
    },
    "mechanistic_prediction": {
        "label": "mechanistic prediction",
        "long": "a parameterized model's quantitative prediction, under stated assumptions",
        "color": AMBER,
    },
    "conceptual_demonstration": {
        "label": "conceptual demonstration",
        "long": "a reduced model shows an organizational principle is possible",
        "color": SLATE,
    },
    "null_control": {
        "label": "null control",
        "long": "passes by rejection — the discriminating gates reject a non-vent control",
        "color": RUST,
    },
}

VIEWS = {
    "World": {"color": SLATE, "long": "the physical world the study runs in"},
    "Mechanism": {"color": AMBER, "long": "the mechanism at the operating point"},
    "Decision": {"color": TEAL, "long": "the swept phase map the verdict rests on"},
}

# Figure tone — sets the header accent.  "negative" is the honest-negative treatment
# (a failed-gate headline); "caution" flags a solver-/structure-sensitive result.
_TONE_ACCENT = {"neutral": INK, "positive": TEAL, "caution": AMBER, "negative": RUST}
_TONE_BG = {
    "neutral": PANEL,
    "positive": "rgba(13,148,136,0.06)",
    "caution": "rgba(217,119,6,0.07)",
    "negative": NEG_FILL,
}


# --------------------------------------------------------------------------- #
# Small HTML chips.  All inline-styled so a figure HTML file is self-contained.
# --------------------------------------------------------------------------- #
def _chip(text: str, color: str, *, filled: bool = False, title: str = "") -> str:
    text = escape(str(text))
    tip = f' title="{escape(title)}"' if title else ""
    if filled:
        style = (f"background:{color};color:#fff;border:1px solid {color};")
    else:
        style = (f"background:transparent;color:{color};border:1px solid {color};")
    return (
        f'<span{tip} style="display:inline-block;{style}border-radius:999px;'
        f"padding:1px 9px;font:600 11px {FONT_STACK};letter-spacing:.02em;"
        f'white-space:nowrap;vertical-align:middle">{text}</span>'
    )


def tier_badge(tier: str) -> str:
    """An honest evidence-tier badge; unknown tiers render neutral."""
    spec = TIERS.get(str(tier))
    if not spec:
        return _chip(str(tier), SLATE, title="evidence tier")
    return _chip(spec["label"], spec["color"], filled=False, title=spec["long"])


def view_tag(view: str) -> str:
    """A World / Mechanism / Decision view chip (a coloured dot + label)."""
    spec = VIEWS.get(str(view))
    color = spec["color"] if spec else SLATE
    tip = spec["long"] if spec else ""
    dot = (f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;'
           f'background:{color};margin-right:5px;vertical-align:middle"></span>')
    return (
        f'<span title="{escape(tip)}" style="display:inline-block;color:{INK_SOFT};'
        f"border:1px solid {HAIR};border-radius:999px;padding:1px 9px 1px 7px;"
        f'font:600 11px {FONT_STACK};white-space:nowrap;vertical-align:middle">'
        f"{dot}{escape(str(view))}</span>"
    )


def phase_tag(phase: str) -> str:
    """A small neutral phase label, e.g. ``Phase 2`` or ``Campaign III``."""
    return (
        f'<span style="display:inline-block;color:{MUTED};font:600 11px {FONT_STACK};'
        f'letter-spacing:.06em;text-transform:uppercase;vertical-align:middle">'
        f"{escape(str(phase))}</span>"
    )


# --------------------------------------------------------------------------- #
# Chrome — header band + caption + frame.
# --------------------------------------------------------------------------- #
def header_band(
    title: str,
    subtitle: str | None = None,
    *,
    phase: str | None = None,
    view: str | None = None,
    tier: str | None = None,
    tone: str = "neutral",
) -> str:
    """The figure header: a title with an accent rule and a right-aligned chip row
    (phase · view · tier).  ``tone`` sets the left accent / wash."""
    accent = _TONE_ACCENT.get(tone, INK)
    bg = _TONE_BG.get(tone, PANEL)
    # When a view badge is shown, drop a redundant trailing "(… view)" parenthetical
    # that older config titles carry (the badge now conveys it).
    if view and title:
        title = re.sub(r"\s*\([^)]*\bview\)\s*$", "", title).strip()
    # When a phase badge is shown, drop a redundant leading "Phase N —" / "Campaign X —"
    # prefix a config title may carry (the badge conveys it).
    if phase and title:
        title = re.sub(r"^\s*(phase\s+[\w-]+|campaign\s+[\w-]+)\s*[—:-]\s*", "", title, flags=re.I).strip()
    chips = []
    if phase:
        chips.append(phase_tag(phase))
    if view:
        chips.append(view_tag(view))
    if tier:
        chips.append(tier_badge(tier))
    chip_row = (
        f'<div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;'
        f'margin-left:auto">{"".join(chips)}</div>' if chips else ""
    )
    sub = (
        f'<div style="font:400 12.5px {FONT_STACK};color:{INK_SOFT};margin-top:2px">'
        f"{escape(subtitle)}</div>" if subtitle else ""
    )
    return (
        f'<div style="background:{bg};border-left:4px solid {accent};border-radius:8px;'
        f'padding:10px 14px;margin:0 0 10px 0">'
        f'<div style="display:flex;align-items:flex-start;gap:12px">'
        f'<div style="font:700 16px {FONT_STACK};color:{INK};line-height:1.25">'
        f"{escape(title)}</div>{chip_row}</div>{sub}</div>"
    )


def caption(text: str, *, tone: str = "neutral", prefix: str | None = None) -> str:
    """A one-line plain-language figure caption footer.  ``prefix`` (e.g. ``How to read``)
    is rendered bold.  HTML in ``text`` is allowed so callers may embed numbers/emphasis,
    so callers are responsible for escaping untrusted content."""
    color = {"negative": RUST, "caution": AMBER}.get(tone, INK_SOFT)
    pre = (f'<b style="color:{INK}">{escape(prefix)}:</b> ' if prefix else "")
    return (
        f'<div style="background:{PANEL};border-radius:8px;padding:9px 13px;margin:10px 0 0 0;'
        f'font:400 12.5px {FONT_STACK};color:{color};line-height:1.45">{pre}{text}</div>'
    )


def frame(
    inner_html: str,
    *,
    title: str,
    subtitle: str | None = None,
    phase: str | None = None,
    view: str | None = None,
    tier: str | None = None,
    caption_text: str | None = None,
    caption_prefix: str | None = None,
    tone: str = "neutral",
    max_width: int = 1000,
) -> str:
    """Wrap an inner figure (a Plotly ``to_html`` fragment or hand-built SVG/HTML) in
    the shared chrome: header band + figure + optional caption, inside a self-contained
    styled section so typography and spacing match across every study."""
    cap = caption(caption_text, tone=tone, prefix=caption_prefix) if caption_text else ""
    # A charset declaration so the figure decodes as UTF-8 when viewed standalone
    # (opened directly, or in a gallery iframe) — otherwise η / ≈ / — / × / ° mojibake.
    return (
        '<meta charset="utf-8">'
        f'<section style="font-family:{FONT_STACK};color:{INK};background:{PAPER};'
        f"max-width:{max_width}px;margin:0 auto;padding:4px 2px;box-sizing:border-box\">"
        f"{header_band(title, subtitle, phase=phase, view=view, tier=tier, tone=tone)}"
        f'<div style="width:100%">{inner_html}</div>{cap}</section>'
    )


# --------------------------------------------------------------------------- #
# Plotly helpers.
# --------------------------------------------------------------------------- #
def base_layout(**over) -> dict:
    """The shared Plotly layout defaults (font, backgrounds, margins, legend).
    Pass overrides through ``**over``; nested dicts (``legend``, ``margin``, ``font``)
    are shallow-merged."""
    layout = {
        "font": FONT(),
        "plot_bgcolor": PAPER,
        "paper_bgcolor": PAPER,
        "margin": {"l": 60, "r": 24, "t": 54, "b": 56},
        "legend": {"orientation": "h", "y": -0.18, "font": {"size": 11, "family": FONT_STACK}},
        "colorway": [TEAL, AMBER, VIOLET, RUST, SLATE, INK],
    }
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(layout.get(k), dict):
            layout[k] = {**layout[k], **v}
        else:
            layout[k] = v
    return layout


def scene_3d(**over) -> dict:
    """Shared Plotly 3D ``scene`` styling — clean light panes, hairline grids, muted
    axis labels, and a default three-quarter camera — so 3D World views match the 2D
    figures. Pass overrides (e.g. ``aspectmode``, ``camera``) through ``**over``."""
    axis = {"backgroundcolor": PAPER, "gridcolor": GRID, "zerolinecolor": HAIR,
            "showbackground": True, "title_font": {"size": 11, "family": FONT_STACK, "color": INK_SOFT},
            "tickfont": {"size": 9, "family": FONT_STACK, "color": SLATE}}
    scene = {"xaxis": dict(axis), "yaxis": dict(axis), "zaxis": dict(axis),
             "camera": {"eye": {"x": 1.55, "y": 1.55, "z": 0.85}},
             "aspectmode": "data"}
    scene.update(over)
    return scene


def style_axes(fig, **over) -> None:
    """Apply the shared axis styling (hairline grid, ink zeroline off) to a figure."""
    kw = {"showgrid": True, "gridcolor": GRID, "zeroline": False,
          "linecolor": HAIR, "ticks": "outside", "tickcolor": HAIR,
          "title_font": {"size": 12, "family": FONT_STACK, "color": INK_SOFT}}
    kw.update(over)
    fig.update_xaxes(**kw)
    fig.update_yaxes(**kw)


def add_zone(fig, x0, x1, kind="agree", *, label=None, row=None, col=None):
    """Shade a vertical region as an honest-uncertainty zone.

    ``kind`` ∈ {``agree``, ``sensitive``, ``negative``, ``band``}.  Use to mark, e.g.,
    the Péclet region where two solvers agree vs. where the answer is solver-sensitive.
    """
    fill = {"agree": AGREE_FILL, "sensitive": SENSITIVE_FILL,
            "negative": NEG_FILL, "band": BAND_FILL}.get(kind, BAND_FILL)
    kw = {"line_width": 0, "fillcolor": fill, "layer": "below"}
    if row is not None and col is not None:
        kw["row"], kw["col"] = row, col
    fig.add_vrect(x0=x0, x1=x1, **kw)
    if label:
        edge = {"agree": TEAL, "sensitive": AMBER, "negative": RUST}.get(kind, SLATE)
        ann = {"x": (x0 + x1) / 2 if isinstance(x0, (int, float)) else x0, "y": 1.0,
               "yref": "paper", "showarrow": False, "text": label,
               "font": {"size": 10, "color": edge, "family": FONT_STACK},
               "yanchor": "bottom"}
        if row is not None and col is not None:
            ann["row"], ann["col"] = row, col
        fig.add_annotation(**ann)


# Backwards-compatible private aliases (modules historically defined these inline).
_INK, _TEAL, _AMBER, _SLATE, _RUST = INK, TEAL, AMBER, SLATE, RUST
