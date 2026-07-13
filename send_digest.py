"""
Builds a beautiful HTML email + PDF attachment and sends via Gmail SMTP.
- HTML email: full UI with color-coded cards, role badges, stats bar
- PDF: clean, print-ready digest with contextual summaries and role checklists
"""

import os
import io
import re
import sys
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from fetch_news import collect_digest

# Make console prints (emoji, arrows) safe on Windows terminals too.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ── Load .env for local testing (real env vars / GitHub secrets win) ────────
def _load_dotenv(path):
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass


_load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ── Config ─────────────────────────────────────────────────────────────────
GMAIL_USER         = (os.environ.get("GMAIL_USER") or "").strip()
# App passwords are shown as "abcd efgh ijkl mnop" — strip the display spaces
# so a copy-paste that kept them still authenticates correctly.
GMAIL_APP_PASSWORD = (os.environ.get("GMAIL_APP_PASSWORD") or "").replace(" ", "").strip()
TO_EMAIL           = (os.environ.get("TO_EMAIL") or GMAIL_USER).strip()
ROLE_FILTER       = os.environ.get("ROLE_FILTER", "")

# ── Category colours (header bg, accent, text) ──────────────────────────────
CAT_STYLE = {
    "🤖 Model Updates":           ("#0f172a", "#6366f1", "#e0e7ff"),
    "🚀 New Launch / Feature":    ("#0c2340", "#3b82f6", "#dbeafe"),
    "🔬 R&D / Research":          ("#0d2a1f", "#10b981", "#d1fae5"),
    "✅ Good News / Wins":         ("#0f2a0f", "#22c55e", "#dcfce7"),
    "⚠️ Bad News / Risk":          ("#2a0f0f", "#ef4444", "#fee2e2"),
    "💡 AI Awareness / Must Know": ("#1a1400", "#f59e0b", "#fef9c3"),
    "📰 General AI Update":        ("#1a1a2e", "#8b5cf6", "#ede9fe"),
}

CAT_TAGLINES = {
    "🤖 Model Updates":           "fresh model drops, glow-ups and benchmark bragging rights",
    "☁️ Cloud AI":                "what sprouted overnight on Azure, AWS and Google Cloud",
    "🗄️ Data & Databricks":       "the data layer — lakehouses, vectors, RAG and other plumbing",
    "🛠️ Dev Tools & Agents":      "new toys for builders: agents, SDKs, copilots and friends",
    "🧪 Testing & Evals":         "who's actually measuring this stuff (bless them)",
    "🚀 New Launch / Feature":    "shipped today — things you can go poke at right now",
    "🔬 R&D / Research":          "seeds the labs are planting for next season",
    "✅ Good News / Wins":         "sunshine: funding rounds, wins and feel-good ships",
    "⚠️ Bad News / Risk":          "storm clouds worth watching (umbrella optional)",
    "💡 AI Awareness / Must Know": "the big-picture stuff to casually drop at lunch",
    "📰 General AI Update":        "everything else that grew in the garden today",
}

# Emoji-free category labels + modern accent colours (email UI)
CAT_LABEL = {
    "🤖 Model Updates":           "Model Updates",
    "☁️ Cloud AI":                "Cloud AI",
    "🗄️ Data & Databricks":       "Data & Databricks",
    "🛠️ Dev Tools & Agents":      "Dev Tools & Agents",
    "🧪 Testing & Evals":         "Testing & Evals",
    "🚀 New Launch / Feature":    "New Launches",
    "🔬 R&D / Research":          "R&D / Research",
    "✅ Good News / Wins":         "Good News",
    "⚠️ Bad News / Risk":          "Risks & Concerns",
    "💡 AI Awareness / Must Know": "Must Know",
    "📰 General AI Update":        "General Updates",
}
CAT_ACCENT = {
    "🤖 Model Updates":           "#6366F1",
    "🚀 New Launch / Feature":    "#0EA5E9",
    "🔬 R&D / Research":          "#8B5CF6",
    "✅ Good News / Wins":         "#10B981",
    "⚠️ Bad News / Risk":          "#EF4444",
    "💡 AI Awareness / Must Know": "#F59E0B",
    "📰 General AI Update":        "#64748B",
}

# Shared font stacks (render reliably across email clients)
SANS  = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
SERIF = "Georgia,'Iowan Old Style','Times New Roman',serif"

# "Morning Canopy" palette — serene, natural, hopeful. Shared by email AND PDF.
E_PAPER   = "#F3F5EC"   # misty morning air behind the card
E_CARD    = "#FFFFFF"   # the page itself
E_PANEL   = "#F6F9EE"   # dew-tinted panels (dashboard, chips)
E_INK     = "#243018"   # deep forest ink
E_BODY    = "#4A5540"   # body copy
E_MUTED   = "#8B947E"   # captions / labels
E_RULE    = "#E2E8D4"   # hairlines
E_ACCENT  = "#648741"   # moss — primary accent
E_ACCENT2 = "#B1E882"   # spring leaf — gradient partner
E_CLAY    = "#EA965C"   # warm clay — sparing warm touch
E_GRAD    = f"linear-gradient(90deg,{E_ACCENT},{E_ACCENT2})"

# Natural tone per category (numbers, section kickers) — email + PDF.
# Each always appears beside its printed name, never as the only identifier.
NEON = {
    "🤖 Model Updates":           "#648741",   # moss
    "☁️ Cloud AI":                "#2E7DB3",   # lake
    "🗄️ Data & Databricks":       "#14876B",   # pine
    "🛠️ Dev Tools & Agents":      "#7B5FC0",   # wildflower
    "🧪 Testing & Evals":         "#C77F0A",   # honey
    "🚀 New Launch / Feature":    "#C2417F",   # berry
    "🔬 R&D / Research":          "#5C8A2E",   # sprout
    "✅ Good News / Wins":         "#3F9C5B",   # meadow
    "⚠️ Bad News / Risk":          "#D14B32",   # terracotta storm
    "💡 AI Awareness / Must Know": "#B98514",   # amber
    "📰 General AI Update":        "#7C8577",   # river stone
}


# ══════════════════════════════════════════════════════════════════════════════
#  HTML EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def _he(s: str) -> str:
    """Strip emoji, then HTML-escape text for safe inclusion in the email."""
    return (_clean(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _url(u: str) -> str:
    return (u or "#").replace("&", "&amp;").replace('"', "%22").replace("<", "%3C").replace(">", "%3E")


def _slug(category: str) -> str:
    name = CAT_LABEL.get(category, _clean(category))
    return "sec-" + (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "x")


# Leaf shape: opposite corners rounded, opposite corners pinched.
_LEAF = "16px 4px 16px 4px"
_LEAF_R = "4px 16px 4px 16px"


def _role_chips(roles: list, accent: str) -> str:
    names = [_he(name) for name, on in _role_flags(roles) if on]
    if not names:
        return ""
    chips = "".join(
        f'<span style="display:inline-block;font-family:{SANS};font-size:11px;font-weight:600;'
        f'color:{accent};background:{E_PANEL};border:1px solid {E_RULE};'
        f'border-radius:{_LEAF};padding:5px 12px;margin:0 6px 6px 0;">{n}</span>'
        for n in names)
    return f'<div style="margin:14px 0 0;">{chips}</div>'


def _dashed_rule() -> str:
    return (f'<div style="border-top:1px dashed {E_RULE};'
            f'margin:24px 12px 24px;font-size:0;line-height:0;">&nbsp;</div>')


def _article_hero(it: dict, num: int, accent: str, lead: bool = False) -> str:
    """Section opener: full-width image, big serif headline, drop cap on the lead."""
    link = _url(it.get("link", "#"))
    img = (it.get("image") or "").strip()
    imgtag = ""
    if img.lower().startswith(("http://", "https://")):
        imgtag = (f'<a href="{link}"><img src="{_url(img)}" width="552" alt="" '
                  f'style="width:100%;max-width:100%;height:auto;display:block;'
                  f'border-radius:22px 22px 22px 5px;margin:0 0 16px;"></a>')
    title_size = 27 if lead else 22
    summary = _he(it.get("summary", ""))
    if lead and summary:
        summary = (f'<span style="font-family:{SERIF};font-size:44px;font-weight:700;color:{accent};'
                   f'line-height:0.85;float:left;padding:5px 8px 0 0;">{summary[0]}</span>{summary[1:]}')
    return f"""
    <div style="margin:0 0 6px;">
      {imgtag}
      <div style="margin:0 0 8px;">
        <span style="font-family:{SERIF};font-size:16px;font-weight:700;font-style:italic;color:{accent};">No.{num:02d}</span>
        <span style="font-family:{SANS};font-size:10.5px;font-weight:700;color:{E_MUTED};letter-spacing:1.8px;text-transform:uppercase;">&nbsp;&nbsp;{_he(it.get('source',''))}</span>
      </div>
      <div style="font-family:{SERIF};font-size:{title_size}px;font-weight:700;color:{E_INK};line-height:1.25;letter-spacing:-0.3px;">
        <a href="{link}" style="color:{E_INK};text-decoration:none;">{_he(it.get('title',''))}</a>
      </div>
      <div style="font-family:{SANS};font-size:15px;color:{E_BODY};line-height:1.7;margin:12px 0 0;">
        {summary}
      </div>
      {_role_chips(it.get('roles', []), accent)}
      <a href="{link}" style="display:inline-block;font-family:{SANS};font-size:12.5px;font-weight:700;color:{accent};text-decoration:none;margin-top:13px;">Keep reading &rarr;</a>
    </div>
    """


def _article_row(it: dict, num: int, accent: str) -> str:
    """Compact row. Thumbnails alternate sides so the page breathes naturally."""
    link = _url(it.get("link", "#"))
    img = (it.get("image") or "").strip()
    on_right = num % 2 == 0
    thumb = ""
    if img.lower().startswith(("http://", "https://")):
        pad = "0 0 0 16px" if on_right else "0 16px 0 0"
        radius = _LEAF_R if on_right else _LEAF
        thumb = (f'<td width="128" style="vertical-align:top;padding:{pad};">'
                 f'<a href="{link}"><img src="{_url(img)}" width="128" alt="" '
                 f'style="width:128px;height:auto;display:block;border-radius:{radius};"></a></td>')
    text = f"""
        <td style="vertical-align:top;">
          <div style="margin:0 0 5px;">
            <span style="font-family:{SERIF};font-size:13px;font-weight:700;font-style:italic;color:{accent};">No.{num:02d}</span>
            <span style="font-family:{SANS};font-size:9.5px;font-weight:700;color:{E_MUTED};letter-spacing:1.5px;text-transform:uppercase;">&nbsp;&nbsp;{_he(it.get('source',''))}</span>
          </div>
          <div style="font-family:{SERIF};font-size:17px;font-weight:700;color:{E_INK};line-height:1.3;">
            <a href="{link}" style="color:{E_INK};text-decoration:none;">{_he(it.get('title',''))}</a>
          </div>
          <div style="font-family:{SANS};font-size:13px;color:{E_BODY};line-height:1.6;margin:6px 0 0;">
            {_he(it.get('summary',''))}
          </div>
          <a href="{link}" style="display:inline-block;font-family:{SANS};font-size:12px;font-weight:700;color:{accent};text-decoration:none;margin-top:9px;">Keep reading &rarr;</a>
        </td>"""
    cells = f"{text}{thumb}" if on_right else f"{thumb}{text}"
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr>{cells}</tr>
    </table>
    """


def _section(category: str, items: list, first: bool = False) -> str:
    name = _he(CAT_LABEL.get(category, _clean(category)))
    tagline = _he(CAT_TAGLINES.get(category, ""))
    anchor = _slug(category)
    accent = NEON.get(category, E_ACCENT)
    parts = []
    for i, it in enumerate(items, 1):
        if i > 1:
            parts.append(_dashed_rule())
        parts.append(_article_hero(it, i, accent, lead=(first and i == 1)) if i == 1
                     else _article_row(it, i, accent))
    stories = "".join(parts)
    return f"""
    <a name="{anchor}" id="{anchor}"></a>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:38px 0 4px;"><tr>
      <td style="vertical-align:middle;white-space:nowrap;padding-right:12px;">
        <span style="font-family:{SANS};font-size:13px;font-weight:800;color:{accent};letter-spacing:2.5px;text-transform:uppercase;">&#10047;&nbsp; {name}</span></td>
      <td style="vertical-align:middle;width:100%;"><div style="border-top:1px dashed {E_RULE};font-size:0;line-height:0;">&nbsp;</div></td>
      <td style="vertical-align:middle;white-space:nowrap;padding-left:12px;">
        <span style="font-family:{SERIF};font-size:12px;font-style:italic;color:{E_MUTED};">{len(items)} {'story' if len(items) == 1 else 'stories'}</span></td>
    </tr></table>
    <div style="font-family:{SERIF};font-size:14px;font-style:italic;color:{E_MUTED};margin:2px 0 20px;">{tagline}</div>
    {stories}
    """


def _index(digest: dict) -> str:
    chips = []
    for cat, items in digest.items():
        name = _he(CAT_LABEL.get(cat, _clean(cat)))
        accent = NEON.get(cat, E_ACCENT)
        chips.append(
            f'<a href="#{_slug(cat)}" style="display:inline-block;text-decoration:none;'
            f'font-family:{SANS};font-size:12px;font-weight:600;color:{E_INK};'
            f'background:{E_PANEL};border:1px solid {E_RULE};border-radius:{_LEAF};'
            f'padding:7px 14px;margin:0 5px 8px 0;white-space:nowrap;">{name} '
            f'<span style="font-family:{SERIF};color:{accent};font-weight:700;">{len(items)}</span></a>'
        )
    return (f'<div style="margin:20px 0 4px;text-align:center;line-height:1;">'
            f'{"".join(chips)}</div>')


# Validated light-mode categorical hues (dataviz six-checks, white surface) —
# used where several colors sit side by side (topic chips). Fixed order.
CHIP_COLORS = ["#2E7DB3", "#C77F0A", "#14876B", "#D14B32",
               "#7B5FC0", "#5C8A2E", "#C2417F", "#A0522D"]

# Pebble tints + accents for the stat tiles — each one its own little stone.
_PEBBLES = [("#EFF5E2", "#648741", "26px 10px 22px 12px"),
            ("#E9F2EE", "#2E7DB3", "12px 24px 10px 22px"),
            ("#FBF2E2", "#C77F0A", "22px 12px 26px 10px"),
            ("#F2EFF8", "#7B5FC0", "10px 22px 12px 26px")]


def _label(text: str) -> str:
    return (f'<div style="font-family:{SERIF};font-size:15px;font-style:italic;font-weight:700;'
            f'color:{E_ACCENT};margin:26px 0 12px;">{text}</div>')


def _stat_tiles(pulse: dict, featured: int, read_min: int) -> str:
    tiles = [
        (str(pulse.get("scanned", featured)), "scanned this week"),
        (str(featured),                        "picked for today"),
        (str(pulse.get("sources", "—")),       "sources tended"),
        (str(read_min),                        "minutes to read"),
    ]
    gap = '<td width="8" style="font-size:0;line-height:0;">&nbsp;</td>'
    tds = gap.join(
        f'<td width="25%" style="background:{bg};border-radius:{radius};'
        f'padding:17px 4px 14px;text-align:center;">'
        f'<div style="font-family:{SERIF};font-size:28px;font-weight:700;color:{fg};line-height:1;">{v}</div>'
        f'<div style="font-family:{SANS};font-size:10px;color:{E_MUTED};margin-top:7px;">{l}</div></td>'
        for (v, l), (bg, fg, radius) in zip(tiles, _PEBBLES))
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
            f'<tr>{tds}</tr></table>')


def _model_chart(models: list) -> str:
    """Most talked-about model families — single-hue moss bars, direct labels."""
    if not models:
        return ""
    mx = max(n for _, n in models) or 1
    rows = ""
    for name, n in models:
        pct = max(6, round(n / mx * 100))
        rows += (
            '<tr>'
            f'<td width="118" style="font-family:{SANS};font-size:12.5px;font-weight:600;color:{E_INK};'
            f'padding:6px 10px 6px 0;white-space:nowrap;">{_he(name)}</td>'
            f'<td style="padding:6px 0;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
            f'<td width="{pct}%" style="background:{E_ACCENT};height:12px;border-radius:6px 2px 6px 2px;font-size:0;line-height:0;">&nbsp;</td>'
            f'<td width="{100 - pct}%" style="font-size:0;line-height:0;">&nbsp;</td>'
            '</tr></table></td>'
            f'<td width="30" style="font-family:{SERIF};font-size:13px;font-weight:700;color:{E_ACCENT};'
            f'padding:6px 0 6px 10px;text-align:right;">{n}</td>'
            '</tr>')
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="background:{E_CARD};border-radius:22px 6px 22px 6px;">'
            f'<tr><td style="padding:18px 20px;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>'
            f'<div style="font-family:{SERIF};font-size:11px;font-style:italic;color:{E_MUTED};margin-top:10px;">'
            f'articles mentioning each family across everything we read this week</div>'
            f'</td></tr></table>')


def _radar_chips(topics: list) -> str:
    if not topics:
        return ""
    chips = ""
    for i, (name, n) in enumerate(topics):
        c = CHIP_COLORS[i % len(CHIP_COLORS)]
        radius = _LEAF if i % 2 == 0 else _LEAF_R
        chips += (f'<span style="display:inline-block;font-family:{SANS};font-size:12px;font-weight:600;'
                  f'color:{E_INK};background:{E_CARD};border:1px solid {E_RULE};'
                  f'border-radius:{radius};padding:7px 13px;margin:0 7px 8px 0;">'
                  f'<span style="color:{c};">&#10047;</span>&nbsp; {_he(name)}&nbsp; '
                  f'<span style="font-family:{SERIF};font-weight:700;color:{c};">{n}</span></span>')
    return f'<div>{chips}</div>'


def _pulse_board(pulse: dict, featured: int, read_min: int) -> str:
    """The 'Morning Pulse' dashboard: tiles, model chart, trending topics."""
    if not pulse:
        return ""
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:{E_PANEL};border-radius:26px 8px 26px 8px;"><tr><td style="padding:6px 20px 20px;">'
        + _label("The morning pulse")
        + _stat_tiles(pulse, featured, read_min)
        + _label("Most talked-about models")
        + _model_chart(pulse.get("models", []))
        + _label("Growing this week")
        + _radar_chips(pulse.get("topics", []))
        + '</td></tr></table>'
    )


def build_html(digest: dict, pulse: dict | None = None) -> str:
    today = date.today().strftime("%A, %B %d, %Y").upper()
    total = sum(len(v) for v in digest.values())
    read_min = max(2, round(total * 0.4))

    nav = _index(digest) if digest else ""
    board = _pulse_board(pulse or {}, total, read_min)
    sections = "".join(_section(cat, items, first=(i == 0))
                       for i, (cat, items) in enumerate(digest.items()))
    if not sections:
        sections = (f'<div style="font-family:{SANS};text-align:center;color:{E_MUTED};'
                    f'padding:44px 20px;">Quiet AI day — check back tomorrow.</div>')

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:{E_PAPER};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{E_PAPER};">
<tr><td align="center" style="padding:30px 10px 52px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:{E_CARD};border-radius:30px 30px 30px 8px;">

  <tr><td style="background:{E_ACCENT2};background:linear-gradient(135deg,{E_ACCENT2},{E_ACCENT});height:7px;font-size:0;line-height:0;border-radius:30px 30px 0 0;">&nbsp;</td></tr>

  <tr><td style="padding:40px 26px 0;">
    <div style="font-family:{SANS};font-size:11px;font-weight:700;color:{E_ACCENT};letter-spacing:3.5px;text-transform:uppercase;text-align:center;">&#10047; Artificial Intelligence &middot; Grown Daily &#10047;</div>
    <div style="font-family:{SERIF};font-size:46px;font-weight:700;color:{E_INK};letter-spacing:-0.8px;line-height:1.05;margin:14px 0 8px;text-align:center;">The AI Dispatch</div>
    <div style="font-family:{SERIF};font-size:13.5px;font-style:italic;color:{E_MUTED};text-align:center;">{_he(today.title())} &nbsp;&middot;&nbsp; {total} stories &nbsp;&middot;&nbsp; about {read_min} minutes, tea included</div>
    {nav}
    <div style="text-align:center;margin-top:14px;"><a href="{WEB_URL}" style="display:inline-block;background:{E_ACCENT};color:#FFFFFF;font-family:{SANS};font-size:12px;font-weight:700;letter-spacing:1px;text-decoration:none;padding:12px 28px;border-radius:{_LEAF};">Read the full edition &rarr;</a></div>
  </td></tr>

  <tr><td style="padding:14px 26px;">
    {board}
    <div style="height:8px;font-size:0;line-height:0;">&nbsp;</div>
    {sections}
  </td></tr>

  <tr><td style="padding:16px 26px 36px;">
    <div style="background:{E_ACCENT2};background:{E_GRAD};height:3px;border-radius:3px;font-size:0;line-height:0;margin-bottom:16px;">&nbsp;</div>
    <div style="font-family:{SERIF};font-size:18px;font-weight:700;color:{E_INK};">The AI Dispatch</div>
    <div style="font-family:{SERIF};font-size:12px;font-style:italic;color:{E_MUTED};margin-top:6px;line-height:1.7;">Grown fresh every morning at 9:00 IST from 30+ AI news &amp; research sources &middot; PDF edition attached &#127807;</div>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════════
#  WEB EDITION  ("read online" page, published to GitHub Pages)
# ══════════════════════════════════════════════════════════════════════════════

WEB_URL = "https://401dharshini.github.io/ai-news-digest/"

WEB_ACCENT = {
    "🤖 Model Updates":           "#7C5CFF",
    "☁️ Cloud AI":                "#2563EB",
    "🗄️ Data & Databricks":       "#0D9488",
    "🛠️ Dev Tools & Agents":      "#9333EA",
    "🧪 Testing & Evals":         "#CA8A04",
    "🚀 New Launch / Feature":    "#FF6B4A",
    "🔬 R&D / Research":          "#00B8D9",
    "✅ Good News / Wins":         "#22C55E",
    "⚠️ Bad News / Risk":          "#F43F5E",
    "💡 AI Awareness / Must Know": "#F59E0B",
    "📰 General AI Update":        "#EC4899",
}

_WEB_CSS = r"""
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --green:#5C8A3A;      /* brand green (genai.works family) */
  --green-d:#436627;    /* darker green for hover / emphasis */
  --lime:#B1E882;       /* bright accent */
  --lime-soft:#EAF6DC;  /* pale green wash for chips & tags */
  --ink:#141A12;        /* headline near-black */
  --body:#414A3B;       /* body copy */
  --muted:#889082;      /* meta / captions */
  --line:#E7EBE1;       /* hairlines & card borders */
  --card:#FFFFFF;
  --bg:#F4F7EF;         /* page background */
}
html{scroll-behavior:smooth;scroll-padding-top:92px}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:var(--body);background:var(--bg);line-height:1.62;-webkit-font-smoothing:antialiased;overflow-x:hidden}
.wrap{max-width:760px;margin:0 auto;padding:0 18px 80px}

/* masthead */
.mast{text-align:center;padding:54px 0 20px}
.mast .kick{display:inline-block;font-size:11px;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;color:var(--green-d);background:var(--lime-soft);padding:7px 16px;border-radius:999px}
.mast h1{font-size:52px;font-weight:800;line-height:1.02;color:var(--ink);letter-spacing:-1.8px;margin:18px 0 0}
.mast h1 .dot{color:var(--green)}
.mast .rule{width:60px;height:4px;background:var(--green);border-radius:4px;margin:16px auto 14px}
.mast .sub{font-size:12px;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted)}

/* sticky category nav — the "table of contents" you click to jump */
.nav{position:sticky;top:10px;z-index:20;display:flex;flex-wrap:wrap;gap:8px;justify-content:center;padding:10px;border-radius:16px;background:rgba(255,255,255,.9);backdrop-filter:blur(14px) saturate(1.4);-webkit-backdrop-filter:blur(14px) saturate(1.4);border:1px solid var(--line);box-shadow:0 8px 28px rgba(20,26,18,.09);margin-bottom:12px}
.nav a{display:inline-flex;align-items:center;gap:8px;font-size:13px;font-weight:600;color:var(--ink);text-decoration:none;padding:7px 13px;border-radius:11px;transition:.2s;white-space:nowrap}
.nav a .cdot{width:8px;height:8px;border-radius:50%;background:var(--acc,#5C8A3A);flex:none}
.nav a span{color:var(--muted);font-variant-numeric:tabular-nums}
.nav a:hover{background:var(--lime-soft)}
.nav a.active{background:var(--green);color:#fff}
.nav a.active span{color:rgba(255,255,255,.72)}
.nav a.active .cdot{background:#fff}

/* section header */
section{padding:30px 0 4px;scroll-margin-top:92px}
.sec-h{display:flex;align-items:center;gap:12px;margin-bottom:16px}
.sec-h .chip{display:inline-flex;align-items:center;font-size:12px;font-weight:800;letter-spacing:1.2px;text-transform:uppercase;color:#fff;background:var(--acc);padding:7px 15px;border-radius:999px;white-space:nowrap}
.sec-h .tag{font-size:13px;color:var(--muted);flex:1;line-height:1.4}
.sec-h .cnt{font-size:12px;font-weight:600;color:var(--muted);white-space:nowrap}

/* story card — each news item stands alone */
.story{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--acc);border-radius:14px;padding:22px 24px;margin-bottom:14px;box-shadow:0 1px 2px rgba(20,26,18,.04);transition:transform .25s,box-shadow .25s}
.story:hover{transform:translateY(-2px);box-shadow:0 16px 36px rgba(20,26,18,.10)}
.story .m{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.story .num{font-size:13px;font-weight:800;color:var(--acc);font-variant-numeric:tabular-nums}
.story .src{font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--muted)}
.story h3{font-size:20px;font-weight:700;line-height:1.28;letter-spacing:-.3px;margin:0}
.story h3 a{color:var(--ink);text-decoration:none;transition:color .2s}
.story h3 a:hover{color:var(--green)}
.story img{width:100%;height:auto;display:block;border-radius:10px;margin:14px 0 2px;border:1px solid var(--line)}
.story p{font-size:15px;color:var(--body);margin-top:10px}
.tags{margin-top:12px;display:flex;flex-wrap:wrap;gap:6px}
.tags span{font-size:11px;font-weight:600;color:var(--green-d);background:var(--lime-soft);padding:3px 10px;border-radius:999px}
.more{display:inline-block;margin-top:13px;font-size:13px;font-weight:700;color:var(--green);text-decoration:none;transition:color .2s}
.more:hover{color:var(--green-d)}

/* reveal-on-scroll + footer */
.reveal{opacity:0;transform:translateY(16px);transition:.6s cubic-bezier(.2,.7,.2,1)}
.reveal.in{opacity:1;transform:none}
.foot{text-align:center;padding:40px 10px 0;margin-top:26px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}
.foot b{color:var(--ink);font-size:18px;font-weight:800;display:block;margin-bottom:6px}
.foot b .dot{color:var(--green)}
@media(max-width:560px){.mast h1{font-size:36px}.story{padding:18px 18px}.story h3{font-size:18px}.sec-h{flex-wrap:wrap;gap:8px}.nav{gap:6px;padding:8px}}
"""

_WEB_JS = r"""
const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}}),{threshold:.12});
document.querySelectorAll('.reveal').forEach(el=>io.observe(el));
const links=new Map([...document.querySelectorAll('.nav a')].map(a=>[a.dataset.t,a]));
const spy=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){links.forEach(a=>a.classList.remove('active'));const a=links.get(e.target.id);if(a)a.classList.add('active')}}),{rootMargin:'-46% 0px -50% 0px'});
document.querySelectorAll('section').forEach(s=>spy.observe(s));
"""

_WEB_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>The AI Dispatch</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>__CSS__</style></head>
<body>
<div class="wrap">
  <div class="mast reveal"><div class="kick">Artificial Intelligence &middot; Daily Edition</div><h1>The AI Dispatch<span class="dot">.</span></h1><div class="rule"></div><div class="sub">__DATE__ &middot; __TOTAL__ stories &middot; __READ__ min read</div></div>
  <nav class="nav reveal">__NAV__</nav>
  __SECTIONS__
  <div class="foot"><b>The AI Dispatch<span class="dot">.</span></b>Delivered daily at 9:00 AM IST &middot; Aggregated from 30+ AI news &amp; research sources</div>
</div>
<script>__JS__</script></body></html>"""


def build_web(digest: dict) -> str:
    total = sum(len(v) for v in digest.values())
    read_min = max(2, round(total * 0.4))
    nav = "".join(
        f'<a href="#{_slug(c)}" data-t="{_slug(c)}" style="--acc:{WEB_ACCENT.get(c, "#5C8A3A")}">'
        f'<i class="cdot"></i>{_he(CAT_LABEL.get(c, _clean(c)))}'
        f'<span>{len(v)}</span></a>'
        for c, v in digest.items())
    secs = ""
    for c, items in digest.items():
        acc = WEB_ACCENT.get(c, "#5C8A3A")
        lbl = _he(CAT_LABEL.get(c, _clean(c)))
        tag = _he(CAT_TAGLINES.get(c, ""))
        stories = ""
        for i, it in enumerate(items, 1):
            img = (it.get("image") or "").strip()
            imgtag = (f'<img loading="lazy" src="{_url(img)}" alt="">'
                      if img.lower().startswith(("http://", "https://")) else "")
            roles = "".join(f"<span>{_he(r)}</span>" for r in it.get("roles", [])[:3])
            tags = f'<div class="tags">{roles}</div>' if roles else ""
            link = _url(it.get("link", "#"))
            stories += (
                f'<article class="story reveal">'
                f'<div class="m"><span class="num">{i:02d}</span>'
                f'<span class="src">{_he(it.get("source", ""))}</span></div>'
                f'<h3><a href="{link}" target="_blank" rel="noopener">{_he(it.get("title", ""))}</a></h3>'
                f'{imgtag}<p>{_he(it.get("summary", ""))}</p>{tags}'
                f'<a class="more" href="{link}" target="_blank" rel="noopener">'
                f'Read the full story &rarr;</a></article>')
        secs += (
            f'<section id="{_slug(c)}" style="--acc:{acc}">'
            f'<header class="sec-h reveal"><span class="chip">{lbl}</span>'
            f'<span class="tag">{tag}</span>'
            f'<span class="cnt">{len(items)} stories</span></header>'
            f'{stories}</section>')
    today = date.today().strftime("%A, %B %d, %Y").upper()
    return (_WEB_TEMPLATE
            .replace("__CSS__", _WEB_CSS).replace("__JS__", _WEB_JS)
            .replace("__NAV__", nav).replace("__SECTIONS__", secs)
            .replace("__DATE__", _he(today))
            .replace("__TOTAL__", str(total)).replace("__READ__", str(read_min)))


# ══════════════════════════════════════════════════════════════════════════════
#  PDF GENERATION  (reportlab)
# ══════════════════════════════════════════════════════════════════════════════
#
# reportlab's built-in fonts (Helvetica) only cover Latin-1 — emoji and many
# symbols render as empty boxes. So everything below is emoji-free by design:
# colour + typography carry the visual weight, and a green ZapfDingbats tick
# (a standard PDF font) drives the role checklist.

# Match anything the base fonts can't draw (emoji, dingbats, arrows, flags).
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF"      # emoji, pictographs, symbols & flags
    "\U00002600-\U000027BF"       # misc symbols + dingbats (☀ ✅ ✈ …)
    "\U0001F1E6-\U0001F1FF"       # regional indicator letters
    "←-⇿⬀-⯿"  # arrows / misc symbols
    "️‍⃣]"         # variation selector, ZWJ, keycap
)


def _clean(s: str) -> str:
    """Strip characters the PDF fonts can't render; collapse whitespace."""
    return re.sub(r"\s+", " ", _EMOJI_RE.sub("", s or "")).strip()


def _safe(s: str) -> str:
    """Clean + XML-escape dynamic text for a reportlab Paragraph."""
    return _clean(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _safe_url(u: str) -> str:
    return (u or "#").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "%22")


# Canonical roles shown as a checklist beneath every story.
_PDF_ROLES = [
    ("Developer",          ("developer",)),
    ("Tester / QA",        ("tester", "qa")),
    ("AI / ML Engineer",   ("ai engineer", "ml engineer")),
    ("Architect",          ("architect", "tech lead")),
    ("Product / Business", ("product", "business")),
    ("Everyone",           ("awareness", "everyone", "general")),
]


def _role_flags(roles):
    joined = " ".join(_clean(r).lower() for r in (roles or []))
    return [(name, any(k in joined for k in kws)) for name, kws in _PDF_ROLES]


def _pdf_image(url: str, width: float, ratio: float = 16 / 9, radius: int = 14,
               min_px: int = 480):
    """Download a story image, centre-crop it to a uniform aspect ratio, round
    its corners, and return a reportlab Image of exactly (width, width/ratio).

    Cropping every image to the same ratio is what keeps the layout aligned —
    no more ragged heights. A missing/broken image returns None (no filler box);
    network/format failures degrade quietly.
    """
    import requests
    from reportlab.platypus import Image
    from PIL import Image as PILImage, ImageDraw

    if not (url or "").lower().startswith(("http://", "https://")):
        return None
    try:
        r = requests.get(url, timeout=8,
                         headers={"User-Agent": "Mozilla/5.0 (AI-News-Digest)"})
        r.raise_for_status()
        if "image" not in r.headers.get("Content-Type", "").lower():
            return None
        if len(r.content) > 8_000_000:          # skip absurdly large assets
            return None
        # Pillow decodes AVIF/WebP/PNG/JPEG; reportlab then embeds the PNG.
        pil = PILImage.open(io.BytesIO(r.content)).convert("RGB")
        iw, ih = pil.size
        if not iw or not ih:
            return None
        if iw < min_px or ih < min_px * 0.45:   # low-res badge/logo — upscales terribly
            return None
        if iw / ih > 3 or ih / iw > 3:          # banner ads / skyscrapers, not photos
            return None

        # Centre-crop to the target aspect ratio.
        target = ratio
        if iw / ih > target:                     # too wide → trim sides
            new_w = int(ih * target)
            x0 = (iw - new_w) // 2
            pil = pil.crop((x0, 0, x0 + new_w, ih))
        else:                                    # too tall → trim top/bottom
            new_h = int(iw / target)
            y0 = (ih - new_h) // 2
            pil = pil.crop((0, y0, iw, y0 + new_h))

        # Downscale (cap ~1400px wide) and round the corners via an alpha mask.
        if pil.width > 1400:
            pil = pil.resize((1400, int(1400 / target)), PILImage.LANCZOS)
        rad_px = int(radius * pil.width / max(width, 1))
        mask = PILImage.new("L", pil.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, pil.width - 1, pil.height - 1), radius=rad_px, fill=255)
        rgba = pil.convert("RGBA")
        rgba.putalpha(mask)

        out = io.BytesIO()
        rgba.save(out, format="PNG")
        out.seek(0)
        img = Image(out, width=width, height=width / target)
        img.hAlign = "LEFT"
        return img
    except Exception:
        return None


def build_pdf(digest: dict, pulse: dict | None = None) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
        Table, TableStyle, KeepTogether, PageBreak, Flowable,
    )
    from reportlab.lib.enums import TA_CENTER
    from reportlab.pdfbase.pdfmetrics import stringWidth

    pulse = pulse or {}

    # ── "Morning Canopy" palette — mirrors the email (E_* vars) ──
    VOID    = colors.HexColor("#FBFCF6")  # page paper
    PANEL   = colors.HexColor(E_PANEL)    # tile surfaces
    TRACK   = colors.HexColor("#E7EEDB")  # chart tracks
    INK     = colors.HexColor(E_INK)      # deep forest ink
    BODY    = colors.HexColor(E_BODY)     # body copy
    MUTED   = colors.HexColor(E_MUTED)    # labels / captions
    RULE    = colors.HexColor(E_RULE)     # hairline rules
    ACCENT  = colors.HexColor(E_ACCENT)   # moss
    ACCENT2 = colors.HexColor(E_ACCENT2)  # spring leaf

    # Base-14 fonts: Times = warm serif display, Helvetica = clear body.
    SANS_R, SANS_B = "Helvetica", "Helvetica-Bold"
    SER_R, SER_B, SER_I, SER_BI = ("Times-Roman", "Times-Bold",
                                   "Times-Italic", "Times-BoldItalic")

    S = getSampleStyleSheet()

    def mk(name, **kw):
        return ParagraphStyle(name, parent=S["Normal"], **kw)

    st_kicker  = mk("kick", fontSize=9.5, textColor=ACCENT, alignment=TA_CENTER,
                    fontName=SANS_B, spaceAfter=12, leading=13)
    st_mast    = mk("mast", fontSize=40, textColor=INK, alignment=TA_CENTER,
                    fontName=SER_B, leading=44)
    st_subline = mk("sub", fontSize=10.5, textColor=MUTED, alignment=TA_CENTER,
                    fontName=SER_I, leading=15)
    st_label   = mk("lbl", fontSize=13, textColor=ACCENT, fontName=SER_BI,
                    leading=16, spaceBefore=16, spaceAfter=8)
    st_idx     = mk("idx", fontSize=10, textColor=BODY, alignment=TA_CENTER, leading=17)
    st_seckick = mk("seck", fontSize=12.5, fontName=SANS_B, leading=15)   # colour set per category
    st_seccnt  = mk("secc", fontSize=9.5, textColor=MUTED, fontName=SER_I,
                    alignment=2, leading=15)  # right-aligned
    st_tagline = mk("tag", fontSize=10.5, textColor=MUTED, fontName=SER_I, leading=14)
    st_src     = mk("src", fontSize=9.5, textColor=MUTED, fontName=SANS_R, leading=15)
    st_title   = mk("ttl2", fontSize=18, textColor=INK, fontName=SER_B, leading=22, spaceAfter=2)
    st_rtitle  = mk("rttl", fontSize=12.5, textColor=INK, fontName=SER_B, leading=16, spaceAfter=2)
    st_sum     = mk("sum", fontSize=10.5, textColor=BODY, leading=16.5, spaceBefore=7, spaceAfter=2)
    st_rsum    = mk("rsum", fontSize=9, textColor=BODY, leading=14, spaceBefore=4, spaceAfter=2)
    st_roles   = mk("roles", fontSize=9, textColor=MUTED, fontName=SER_I, leading=13, spaceBefore=9)
    st_more    = mk("more", fontSize=9.5, textColor=ACCENT, fontName=SANS_B, leading=13, spaceBefore=8)
    st_rmore   = mk("rmore", fontSize=8.5, textColor=ACCENT, fontName=SANS_B, leading=11, spaceBefore=5)
    st_foot    = mk("foot", fontSize=9, textColor=MUTED, alignment=TA_CENTER,
                    fontName=SER_I, leading=14)
    st_foot_b  = mk("footb", fontSize=15, textColor=INK, alignment=TA_CENTER,
                    fontName=SER_B, leading=18)

    CONTENT_W = 18.0 * cm  # A4 (21cm) minus 1.5cm margins each side

    # ── Custom dashboard flowables ─────────────────────────────────

    class _Tiles(Flowable):
        """Row of pebble-shaped stat tiles: serif number + soft caption.
        Radii and baselines vary a little so the row reads organic, not gridded."""
        PEBBLES = [("#EFF5E2", "#648741", 14, 0),
                   ("#E9F2EE", "#2E7DB3", 20, 3),
                   ("#FBF2E2", "#C77F0A", 12, 0),
                   ("#F2EFF8", "#7B5FC0", 18, 3)]

        def __init__(self, tiles, width, height=2.0 * cm, gap=0.28 * cm):
            super().__init__()
            self.tiles, self.width, self.height, self.gap = tiles, width, height, gap

        def draw(self):
            c = self.canv
            n = len(self.tiles)
            tw = (self.width - self.gap * (n - 1)) / n
            for i, (value, caption) in enumerate(self.tiles):
                bg, fg, rad, lift = self.PEBBLES[i % len(self.PEBBLES)]
                x = i * (tw + self.gap)
                c.setFillColor(colors.HexColor(bg))
                c.roundRect(x, lift, tw, self.height - 3, rad, stroke=0, fill=1)
                c.setFillColor(colors.HexColor(fg))
                c.setFont(SER_B, 21)
                c.drawCentredString(x + tw / 2, lift + self.height - 0.95 * cm, str(value))
                c.setFillColor(MUTED)
                c.setFont(SANS_R, 7)
                c.drawCentredString(x + tw / 2, lift + 0.34 * cm, caption)

    class _NeonBars(Flowable):
        """Horizontal bar chart: label | rounded track+bar | value. Moss, one hue."""
        ROW_H = 0.62 * cm

        def __init__(self, data, width, label_w=3.4 * cm, val_w=0.9 * cm):
            super().__init__()
            self.data, self.width = data, width
            self.label_w, self.val_w = label_w, val_w
            self.height = self.ROW_H * len(data)

        def draw(self):
            c = self.canv
            mx = max((n for _, n in self.data), default=1)
            track_w = self.width - self.label_w - self.val_w - 0.4 * cm
            bh = 6.5
            for i, (name, n) in enumerate(self.data):
                yc = self.height - (i + 0.5) * self.ROW_H
                c.setFillColor(INK)
                c.setFont(SANS_R, 8.5)
                c.drawString(0, yc - 3, name)
                bx = self.label_w
                c.setFillColor(TRACK)
                c.roundRect(bx, yc - bh / 2, track_w, bh, bh / 2, stroke=0, fill=1)
                c.setFillColor(ACCENT)
                c.roundRect(bx, yc - bh / 2, max(track_w * n / mx, bh), bh,
                            bh / 2, stroke=0, fill=1)
                c.setFillColor(ACCENT)
                c.setFont(SER_B, 10)
                c.drawRightString(self.width, yc - 3.5, str(n))

    class _Chips(Flowable):
        """Wrapping row of leaf-shaped chips: berry dot + topic + count."""
        CHIP_H, PAD_X, GAP = 0.64 * cm, 0.26 * cm, 0.2 * cm
        COLORS = CHIP_COLORS  # validated light-mode categorical set

        def __init__(self, topics, width):
            super().__init__()
            self.topics, self.width = topics, width
            self._layout = []
            x = y = 0
            for i, (name, n) in enumerate(topics):
                w = (stringWidth(name, "Helvetica", 8.5)
                     + stringWidth(f" {n}", "Times-Bold", 10)
                     + 2 * self.PAD_X + 12)
                if x + w > width and x > 0:
                    x, y = 0, y + self.CHIP_H + self.GAP
                self._layout.append((x, y, w, name, n, self.COLORS[i % len(self.COLORS)]))
                x += w + self.GAP
            self.height = y + self.CHIP_H

        def _leaf_rect(self, c, x, y, w, h, r, flip):
            """Rect with two opposite corners rounded — a leaf silhouette."""
            p = c.beginPath()
            k = r * 0.45
            if not flip:            # rounded bottom-right + top-left
                p.moveTo(x, y)
                p.lineTo(x + w - r, y)
                p.curveTo(x + w - k, y, x + w, y + k, x + w, y + r)
                p.lineTo(x + w, y + h)
                p.lineTo(x + r, y + h)
                p.curveTo(x + k, y + h, x, y + h - k, x, y + h - r)
                p.close()
            else:                   # rounded bottom-left + top-right
                p.moveTo(x + w, y)
                p.lineTo(x + r, y)
                p.curveTo(x + k, y, x, y + k, x, y + r)
                p.lineTo(x, y + h)
                p.lineTo(x + w - r, y + h)
                p.curveTo(x + w - k, y + h, x + w, y + h - k, x + w, y + h - r)
                p.close()
            c.drawPath(p, stroke=1, fill=1)

        def draw(self):
            c = self.canv
            for i, (x, y, w, name, n, col) in enumerate(self._layout):
                yy = self.height - y - self.CHIP_H          # flip: first row on top
                c.setFillColor(colors.white)
                c.setStrokeColor(RULE)
                self._leaf_rect(c, x, yy, w, self.CHIP_H, 7, flip=(i % 2 == 1))
                c.setFillColor(colors.HexColor(col))
                c.circle(x + self.PAD_X + 1.5, yy + self.CHIP_H / 2, 2.2, stroke=0, fill=1)
                tx = x + self.PAD_X + 7
                c.setFont("Helvetica", 8.5)
                c.setFillColor(INK)
                c.drawString(tx, yy + 0.21 * cm, name)
                c.setFont("Times-Bold", 10)
                c.setFillColor(colors.HexColor(col))
                c.drawString(tx + stringWidth(name, "Helvetica", 8.5) + 5,
                             yy + 0.2 * cm, str(n))

    def roles_line(roles, accent_hex):
        names = [_safe(name) for name, on in _role_flags(roles) if on]
        if not names:
            return None
        joined = f' <font color="{E_MUTED}">&middot;</font> '.join(
            f'<font color="{accent_hex}">{n}</font>' for n in names)
        return Paragraph(f"Relevant for &mdash; {joined}", st_roles)

    def _draw_leaf(c, x, y, size, angle, color, alpha):
        """A single pointed-oval leaf, drawn with two beziers."""
        c.saveState()
        c.translate(x, y)
        c.rotate(angle)
        c.setFillColor(color)
        try:
            c.setFillAlpha(alpha)
        except Exception:
            pass
        p = c.beginPath()
        p.moveTo(0, 0)
        p.curveTo(size * 0.35, size * 0.38, size * 0.75, size * 0.38, size, 0)
        p.curveTo(size * 0.75, -size * 0.38, size * 0.35, -size * 0.38, 0, 0)
        c.drawPath(p, stroke=0, fill=1)
        c.restoreState()

    # Soft paper page with a hand-drawn branch in the top-right corner and a
    # few seeds bottom-left — quiet nature, no grids, no strips.
    def paint_page(canvas, doc):
        W, H = A4
        canvas.saveState()
        canvas.setFillColor(VOID)
        canvas.rect(0, 0, W, H, fill=1, stroke=0)

        # branch stem arcing out of the top-right corner
        canvas.setStrokeColor(ACCENT)
        try:
            canvas.setStrokeAlpha(0.30)
        except Exception:
            pass
        canvas.setLineWidth(1.0)
        p = canvas.beginPath()
        p.moveTo(W - 3, H - 64)
        p.curveTo(W - 30, H - 52, W - 52, H - 32, W - 78, H - 10)
        canvas.drawPath(p, stroke=1, fill=0)

        leaves = [(W - 16, H - 58, 12, 205, ACCENT2, 0.55),
                  (W - 35, H - 45, 14, 220, ACCENT, 0.28),
                  (W - 50, H - 34, 11, 200, ACCENT2, 0.50),
                  (W - 66, H - 20, 13, 235, ACCENT, 0.25),
                  (W - 76, H - 12, 10, 210, ACCENT2, 0.45)]
        for lx, ly, sz, ang, col, al in leaves:
            _draw_leaf(canvas, lx, ly, sz, ang, col, al)

        # three seeds resting bottom-left
        try:
            canvas.setFillAlpha(0.30)
        except Exception:
            pass
        canvas.setFillColor(ACCENT)
        for sx, sy, r in ((26, 30, 2.4), (37, 24, 1.7), (31, 40, 1.3)):
            canvas.circle(sx, sy, r, stroke=0, fill=1)
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.6 * cm, bottomMargin=1.6 * cm,
        title=f"The AI Dispatch — {date.today().strftime('%B %d %Y')}",
    )

    story = []
    total = sum(len(v) for v in digest.values())
    read_min = max(2, round(total * 0.4))
    today = date.today().strftime("%A, %B %d, %Y").upper()

    # ── Page 1: masthead + Morning Pulse dashboard ─────────────────
    story.append(Spacer(1, 0.35 * cm))
    story.append(Paragraph("&#9679; &nbsp;ARTIFICIAL INTELLIGENCE &middot; GROWN DAILY&nbsp; &#9679;",
                           st_kicker))
    story.append(Paragraph("The AI Dispatch", st_mast))
    story.append(Spacer(1, 0.22 * cm))
    story.append(HRFlowable(width="34%", thickness=2.2, color=ACCENT2, spaceAfter=2.5,
                            hAlign="CENTER"))
    story.append(HRFlowable(width="20%", thickness=1.0, color=ACCENT, spaceAfter=9,
                            hAlign="CENTER"))
    story.append(Paragraph(
        f"{_safe(today.title())} &nbsp;&middot;&nbsp; {total} stories "
        f"&nbsp;&middot;&nbsp; about {read_min} minutes, tea included",
        st_subline))
    story.append(Spacer(1, 0.5 * cm))

    if pulse:
        story.append(Paragraph("The morning pulse", st_label))
        story.append(_Tiles([
            (pulse.get("scanned", total), "scanned this week"),
            (total,                        "picked for today"),
            (pulse.get("sources", "—"),    "sources tended"),
            (read_min,                     "minutes to read"),
        ], CONTENT_W))
        story.append(Spacer(1, 0.1 * cm))
        if pulse.get("models"):
            story.append(Paragraph("Most talked-about models", st_label))
            story.append(_NeonBars(pulse["models"], CONTENT_W))
        if pulse.get("topics"):
            story.append(Paragraph("Growing this week", st_label))
            story.append(_Chips(pulse["topics"], CONTENT_W))

    if digest:
        story.append(Paragraph("In this issue", st_label))
        idx = " &nbsp;&middot;&nbsp; ".join(
            f'{_safe(_clean(CAT_LABEL.get(cat, _clean(cat))))} '
            f'<font color="{NEON.get(cat, E_ACCENT)}"><b>{len(items)}</b></font>'
            for cat, items in digest.items())
        story.append(Paragraph(idx, st_idx))
    story.append(Spacer(1, 0.55 * cm))

    # ── Sections: hero story + compact aligned rows ────────────────
    THUMB_W = 4.2 * cm
    for category, items in digest.items():
        accent_hex = NEON.get(category, E_ACCENT)
        name = _clean(CAT_LABEL.get(category, _clean(category))).upper()
        tagline = _clean(CAT_TAGLINES.get(category, ""))

        head = Table(
            [[Paragraph(f'<font color="{accent_hex}">&#9679;&nbsp; {_safe(name)}</font>', st_seckick),
              Paragraph(f"{len(items)} {'story' if len(items) == 1 else 'stories'}", st_seccnt)]],
            colWidths=[CONTENT_W * 0.72, CONTENT_W * 0.28])
        head.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        # The section intro travels with the first story so a header is never
        # stranded alone at the bottom of a page.
        sec_intro = [head,
                     HRFlowable(width="100%", thickness=0.9, color=RULE, spaceAfter=6)]
        if tagline:
            sec_intro.append(Paragraph(_safe(tagline), st_tagline))
        sec_intro.append(Spacer(1, 0.35 * cm))

        for i, it in enumerate(items, 1):
            meta = Paragraph(
                f'<font color="{accent_hex}" name="{SER_BI}" size="11">No.{i:02d}</font>'
                f'&nbsp;&nbsp;&nbsp;{_safe(it.get("source", "")).upper()}', st_src)
            link_p_style, title_style, sum_style = st_more, st_title, st_sum

            if i == 1:
                # Hero: full-width 16:9 image, big headline.
                block = []
                img = _pdf_image(it.get("image", ""), CONTENT_W, ratio=16 / 9)
                if img is not None:
                    block.append(img)
                    block.append(Spacer(1, 0.3 * cm))
                block += [meta, Paragraph(_safe(it.get("title", "")), title_style),
                          Paragraph(_safe(it.get("summary", "")), sum_style)]
                rl = roles_line(it.get("roles", []), accent_hex)
                if rl is not None:
                    block.append(rl)
                block.append(Paragraph(
                    f'<link href="{_safe_url(it.get("link", "#"))}" color="{accent_hex}">'
                    f'Keep reading &rarr;</link>', link_p_style))
                story.append(KeepTogether(sec_intro + block))
            else:
                # Compact row: uniform 16:9 thumbnail left, text right.
                text_cell = [meta,
                             Paragraph(_safe(it.get("title", "")), st_rtitle),
                             Paragraph(_safe(it.get("summary", "")), st_rsum),
                             Paragraph(
                                 f'<link href="{_safe_url(it.get("link", "#"))}" '
                                 f'color="{E_ACCENT}">Keep reading &rarr;</link>', st_rmore)]
                thumb = _pdf_image(it.get("image", ""), THUMB_W, ratio=16 / 9,
                                   radius=8, min_px=220)
                if thumb is not None:
                    text_w = CONTENT_W - THUMB_W - 0.4 * cm
                    if i % 2 == 0:      # thumbnails alternate sides — no rigid grid
                        cells, widths = [thumb, text_cell], [THUMB_W + 0.4 * cm, text_w]
                        pads = [("RIGHTPADDING", (0, 0), (0, 0), 12)]
                    else:
                        cells, widths = [text_cell, thumb], [text_w, THUMB_W + 0.4 * cm]
                        pads = [("LEFTPADDING", (1, 0), (1, 0), 12)]
                    row = Table([cells], colWidths=widths)
                    row.setStyle(TableStyle([
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ] + pads))
                    story.append(KeepTogether([row]))
                else:
                    story.append(KeepTogether(text_cell))

            story.append(HRFlowable(width="100%", thickness=0.8, color=RULE,
                                    dash=(2, 3),
                                    spaceBefore=0.4 * cm, spaceAfter=0.4 * cm))

        story.append(Spacer(1, 0.4 * cm))

    # ── Footer ─────────────────────────────────────────────────────
    story.append(HRFlowable(width="34%", thickness=2.2, color=ACCENT2, spaceAfter=2.5,
                            hAlign="CENTER"))
    story.append(HRFlowable(width="20%", thickness=1.0, color=ACCENT, spaceAfter=12,
                            hAlign="CENTER"))
    story.append(Paragraph("The AI Dispatch", st_foot_b))
    story.append(Spacer(1, 0.12 * cm))
    story.append(Paragraph(
        "Grown fresh every morning at 9:00 IST &nbsp;&middot;&nbsp; "
        "from 30+ AI news &amp; research sources", st_foot))

    doc.build(story, onFirstPage=paint_page, onLaterPages=paint_page)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
#  ROLE FILTER
# ══════════════════════════════════════════════════════════════════════════════

def filter_by_role(digest: dict) -> dict:
    if not ROLE_FILTER:
        return digest
    wanted = [r.strip().lower() for r in ROLE_FILTER.split(",") if r.strip()]
    filtered = {}
    for cat, items in digest.items():
        kept = [
            it for it in items
            if any(w in role.lower() for role in it.get("roles", []) for w in wanted)
        ]
        if kept:
            filtered[cat] = kept
    return filtered


# ══════════════════════════════════════════════════════════════════════════════
#  SEND
# ══════════════════════════════════════════════════════════════════════════════

def send_email(html_content: str, pdf_bytes: bytes, item_count: int,
               top_title: str = ""):
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        raise RuntimeError("Missing GMAIL_USER or GMAIL_APP_PASSWORD env vars.")

    today_str  = date.today().strftime("%b %d")
    today_file = date.today().strftime("%Y-%m-%d")

    # TO_EMAIL may list several addresses separated by commas or semicolons.
    recipients = [e.strip() for e in re.split(r"[,;]+", TO_EMAIL) if e.strip()]

    # Lead with the day's best story, newsletter-style; fall back to the count.
    if top_title:
        subject = f"🌱 {top_title[:70]}" + ("…" if len(top_title) > 70 else "")
    else:
        subject = f"🌱 The AI Dispatch — {today_str} · {item_count} stories"

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = ", ".join(recipients)

    # HTML body
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html_content, "html", "utf-8"))
    msg.attach(alt)

    # PDF attachment
    pdf_part = MIMEApplication(pdf_bytes, _subtype="pdf")
    pdf_part.add_header(
        "Content-Disposition", "attachment",
        filename=f"AI-Briefing-{today_file}.pdf"
    )
    msg.attach(pdf_part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, recipients, msg.as_string())

    print(f"✅ Sent digest + PDF to {len(recipients)} recipient(s): {', '.join(recipients)}")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Collecting news...")
    digest, pulse = collect_digest(with_insights=True)
    digest = filter_by_role(digest)
    count  = sum(len(v) for v in digest.values())

    print(f"Building HTML email ({count} items)...")
    html_content = build_html(digest, pulse)

    print("Generating PDF...")
    pdf_bytes = build_pdf(digest, pulse)
    print(f"PDF size: {len(pdf_bytes)//1024} KB")

    print("Building web edition...")
    os.makedirs("public", exist_ok=True)
    with open(os.path.join("public", "index.html"), "w", encoding="utf-8") as f:
        f.write(build_web(digest))
    print("Web edition -> public/index.html")

    # Save PDF locally for inspection (great for testing without email)
    today_file = date.today().strftime("%Y-%m-%d")
    local_pdf  = f"AI-Briefing-{today_file}.pdf"
    with open(local_pdf, "wb") as f:
        f.write(pdf_bytes)
    print(f"PDF saved locally -> {local_pdf}")

    if GMAIL_USER and GMAIL_APP_PASSWORD:
        print("Sending email...")
        first_items = next(iter(digest.values()), [])
        top_title = first_items[0].get("title", "") if first_items else ""
        send_email(html_content, pdf_bytes, count, top_title)
    else:
        print("GMAIL_USER / GMAIL_APP_PASSWORD not set — email skipped.")
        print(f"    Open '{local_pdf}' to preview the PDF output.")
