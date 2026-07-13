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
    "🤖 Model Updates":           "New model versions, capabilities & benchmarks dropped today",
    "☁️ Cloud AI":                "New models and AI services on Azure, AWS and Google Cloud",
    "🗄️ Data & Databricks":       "Databricks, Snowflake, vector search, RAG and the data layer",
    "🛠️ Dev Tools & Agents":      "Coding assistants, agent frameworks, SDKs and new APIs",
    "🧪 Testing & Evals":         "AI testing, benchmarks, evaluations and reliability",
    "🚀 New Launch / Feature":    "Fresh tools, APIs & features you can use right now",
    "🔬 R&D / Research":          "What labs & universities are building behind the scenes",
    "✅ Good News / Wins":         "Funding, partnerships & breakthroughs worth celebrating",
    "⚠️ Bad News / Risk":          "Risks, failures & controversies to keep an eye on",
    "💡 AI Awareness / Must Know": "Big-picture trends every tech person should know",
    "📰 General AI Update":        "Everything else worth knowing today",
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
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
SERIF = "Georgia,'Iowan Old Style','Times New Roman',serif"

# Editorial "AI Dispatch" email palette — one dominant accent, warm paper
E_PAPER  = "#EFEADD"
E_CARD   = "#FCFAF4"
E_INK    = "#1A1712"
E_BODY   = "#4A453B"
E_MUTED  = "#8C8578"
E_RULE   = "#DBD4C4"
E_ACCENT = "#C63F1E"


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


def _img(it: dict) -> str:
    img = (it.get("image") or "").strip()
    if img.lower().startswith(("http://", "https://")):
        return (f'<img src="{_url(img)}" width="600" alt="" '
                f'style="width:100%;max-width:100%;height:auto;display:block;margin:15px 0 2px;">')
    return ""  # editorial flow simply omits missing images — no filler boxes


def _role_line(roles: list) -> str:
    names = [_he(name) for name, on in _role_flags(roles) if on]
    if not names:
        return ""
    txt = " &middot; ".join(names)
    return (f'<div style="font-family:{SANS};font-size:10.5px;font-weight:700;color:{E_MUTED};'
            f'text-transform:uppercase;letter-spacing:1.2px;margin:13px 0 0;">Relevant for&nbsp;&nbsp; {txt}</div>')


def _article(it: dict, num: int, lead: bool = False) -> str:
    link = _url(it.get("link", "#"))
    title_size = 28 if lead else 20
    summary = _he(it.get("summary", ""))
    if lead and summary:
        summary = (f'<span style="font-family:{SERIF};font-size:46px;font-weight:700;color:{E_ACCENT};'
                   f'line-height:0.82;float:left;padding:6px 9px 0 0;">{summary[0]}</span>{summary[1:]}')
    return f"""
    <div style="margin:0 0 22px;">
      <div style="margin:0 0 6px;">
        <span style="font-family:{SERIF};font-size:15px;font-weight:700;color:{E_ACCENT};">{num:02d}</span>
        <span style="font-family:{SANS};font-size:10.5px;font-weight:700;color:{E_MUTED};text-transform:uppercase;letter-spacing:1.2px;margin-left:9px;">{_he(it.get('source',''))}</span>
      </div>
      <div style="font-family:{SERIF};font-size:{title_size}px;font-weight:700;color:{E_INK};line-height:1.22;letter-spacing:-0.4px;">
        <a href="{link}" style="color:{E_INK};text-decoration:none;">{_he(it.get('title',''))}</a>
      </div>
      {_img(it)}
      <div style="font-family:{SANS};font-size:15px;color:{E_BODY};line-height:1.66;margin:12px 0 0;">
        {summary}
      </div>
      {_role_line(it.get('roles', []))}
      <a href="{link}" style="display:inline-block;font-family:{SANS};font-size:12px;font-weight:700;color:{E_ACCENT};text-transform:uppercase;letter-spacing:1px;text-decoration:none;margin-top:12px;">Read the full story &rarr;</a>
    </div>
    <div style="border-top:1px solid {E_RULE};margin:0 0 22px;"></div>
    """


def _section(category: str, items: list, first: bool = False) -> str:
    name = _he(CAT_LABEL.get(category, _clean(category))).upper()
    tagline = _he(CAT_TAGLINES.get(category, ""))
    anchor = _slug(category)
    stories = "".join(_article(it, i, lead=(first and i == 1)) for i, it in enumerate(items, 1))
    return f"""
    <a name="{anchor}" id="{anchor}"></a>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:30px 0 4px;"><tr>
      <td style="vertical-align:middle;white-space:nowrap;padding-right:12px;"><span style="font-family:{SANS};font-size:12px;font-weight:700;color:{E_ACCENT};text-transform:uppercase;letter-spacing:2px;">{name}</span></td>
      <td style="vertical-align:middle;width:100%;"><div style="border-top:1px solid {E_INK};font-size:0;line-height:0;">&nbsp;</div></td>
      <td style="vertical-align:middle;white-space:nowrap;padding-left:12px;"><span style="font-family:{SANS};font-size:11px;color:{E_MUTED};">{len(items)} stories</span></td>
    </tr></table>
    <div style="font-family:{SERIF};font-size:14px;font-style:italic;color:{E_MUTED};margin:0 0 20px;">{tagline}</div>
    {stories}
    """


def _index(digest: dict) -> str:
    links = []
    for cat, items in digest.items():
        name = _he(CAT_LABEL.get(cat, _clean(cat)))
        anchor = _slug(cat)
        links.append(
            f'<a href="#{anchor}" style="text-decoration:none;font-family:{SANS};font-size:12.5px;'
            f'font-weight:600;color:{E_INK};white-space:nowrap;">{name} '
            f'<span style="color:{E_ACCENT};">{len(items)}</span></a>'
        )
    sep = f'<span style="color:{E_RULE};">&nbsp;&nbsp;&middot;&nbsp;&nbsp;</span>'
    return (f'<div style="margin:16px 0 2px;line-height:2.1;text-align:center;">'
            f'<span style="font-family:{SANS};font-size:10px;font-weight:700;color:{E_ACCENT};'
            f'text-transform:uppercase;letter-spacing:2px;">In this issue&nbsp;&nbsp;</span>'
            f'{sep.join(links)}</div>')


def build_html(digest: dict) -> str:
    today = date.today().strftime("%A, %B %d, %Y").upper()
    total = sum(len(v) for v in digest.values())
    read_min = max(2, round(total * 0.4))

    nav = _index(digest) if digest else ""
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
<tr><td align="center" style="padding:0 0 40px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:{E_CARD};">

  <tr><td style="padding:34px 36px 0;">
    <div style="font-family:{SANS};font-size:10px;font-weight:700;color:{E_ACCENT};letter-spacing:3px;text-transform:uppercase;text-align:center;">Artificial Intelligence &middot; Daily Edition</div>
    <div style="font-family:{SERIF};font-size:48px;font-weight:700;color:{E_INK};letter-spacing:-1.2px;line-height:1;margin:10px 0 12px;text-align:center;">The AI Dispatch</div>
    <div style="border-bottom:3px solid {E_INK};font-size:0;line-height:0;">&nbsp;</div>
    <div style="border-bottom:1px solid {E_INK};margin-top:3px;font-size:0;line-height:0;">&nbsp;</div>
    <div style="font-family:{SANS};font-size:10.5px;color:{E_MUTED};letter-spacing:1.5px;text-transform:uppercase;text-align:center;margin-top:10px;">{_he(today)} &nbsp;&middot;&nbsp; {total} stories &nbsp;&middot;&nbsp; {read_min} min read</div>
    {nav}
    <div style="text-align:center;margin-top:2px;"><a href="{WEB_URL}" style="display:inline-block;background:{E_ACCENT};color:#FFFFFF;font-family:{SANS};font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;text-decoration:none;padding:11px 24px;border-radius:7px;">Open the full edition &rarr;</a></div>
  </td></tr>

  <tr><td style="padding:8px 36px;">
    {sections}
  </td></tr>

  <tr><td style="padding:10px 36px 34px;">
    <div style="border-top:3px solid {E_INK};font-size:0;line-height:0;">&nbsp;</div>
    <div style="border-top:1px solid {E_INK};margin-top:3px;margin-bottom:13px;font-size:0;line-height:0;">&nbsp;</div>
    <div style="font-family:{SERIF};font-size:17px;font-weight:700;color:{E_INK};">The AI Dispatch</div>
    <div style="font-family:{SANS};font-size:11px;color:{E_MUTED};margin-top:5px;line-height:1.6;">Delivered daily at 9:00 AM IST &nbsp;&middot;&nbsp; Aggregated from 30+ AI news &amp; research sources &nbsp;&middot;&nbsp; PDF edition attached</div>
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


def build_pdf(digest: dict) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
        Table, TableStyle, KeepTogether, PageBreak,
    )
    from reportlab.lib.enums import TA_CENTER

    ACCENT_HEX = {
        "🤖 Model Updates":           "#6366f1",
        "🚀 New Launch / Feature":    "#3b82f6",
        "🔬 R&D / Research":          "#0ea5e9",
        "✅ Good News / Wins":         "#16a34a",
        "⚠️ Bad News / Risk":          "#dc2626",
        "💡 AI Awareness / Must Know": "#f59e0b",
        "📰 General AI Update":        "#8b5cf6",
    }
    CLEAN_NAME = {
        "🤖 Model Updates":           "MODEL UPDATES",
        "🚀 New Launch / Feature":    "NEW LAUNCHES & FEATURES",
        "🔬 R&D / Research":          "R&D / RESEARCH",
        "✅ Good News / Wins":         "GOOD NEWS & WINS",
        "⚠️ Bad News / Risk":          "RISKS & CONCERNS",
        "💡 AI Awareness / Must Know": "MUST-KNOW / AWARENESS",
        "📰 General AI Update":        "GENERAL AI UPDATES",
    }

    DARK   = colors.HexColor("#0f172a")
    BODY   = colors.HexColor("#334155")
    MUTED  = colors.HexColor("#94a3b8")
    LINE   = colors.HexColor("#e2e8f0")
    WHITE  = colors.white
    INDIGO = colors.HexColor("#6366f1")

    S = getSampleStyleSheet()

    def mk(name, **kw):
        return ParagraphStyle(name, parent=S["Normal"], **kw)

    st_kicker = mk("kick", fontSize=11, textColor=INDIGO, alignment=TA_CENTER,
                   fontName="Helvetica-Bold", spaceAfter=8, leading=14)
    st_title  = mk("ttl", fontSize=42, textColor=DARK, alignment=TA_CENTER,
                   fontName="Helvetica-Bold", leading=46)
    st_cdate  = mk("cdt", fontSize=13, textColor=BODY, alignment=TA_CENTER)
    st_h2     = mk("h2", fontSize=15, textColor=DARK, fontName="Helvetica-Bold", spaceAfter=12)
    st_cat    = mk("cat", fontSize=15, textColor=WHITE, fontName="Helvetica-Bold", leading=18)
    st_ctag   = mk("ctag", fontSize=9.5, textColor=WHITE, leading=12)
    st_ttl2   = mk("t2", fontSize=12.5, textColor=DARK, fontName="Helvetica-Bold",
                   leading=16, spaceAfter=4)
    st_sum    = mk("sum", fontSize=10, textColor=BODY, leading=15, spaceAfter=7)
    st_meta   = mk("meta", fontSize=9, textColor=MUTED)
    st_ron    = mk("ron", fontSize=8.5, textColor=colors.HexColor("#166534"), leading=11)
    st_roff   = mk("roff", fontSize=8.5, textColor=colors.HexColor("#cbd5e1"), leading=11)
    st_toc    = mk("toc", fontSize=11, textColor=BODY, leading=17)
    st_top    = mk("top", fontSize=10.5, textColor=DARK, fontName="Helvetica-Bold",
                   leading=14, spaceAfter=7)
    st_snum   = mk("snum", fontSize=22, textColor=DARK, fontName="Helvetica-Bold", alignment=TA_CENTER)
    st_slbl   = mk("slbl", fontSize=8, textColor=MUTED, alignment=TA_CENTER)
    st_foot   = mk("foot", fontSize=8.5, textColor=MUTED, alignment=TA_CENTER, leading=12)

    def role_checklist(roles):
        flags = _role_flags(roles)
        cells = []
        for name, on in flags:
            if on:
                cells.append(Paragraph(
                    f'<font name="ZapfDingbats" color="#16a34a">4</font> <b>{_safe(name)}</b>',
                    st_ron))
            else:
                cells.append(Paragraph(_safe(name), st_roff))
        t = Table([cells[0:3], cells[3:6]],
                  colWidths=[5.9 * cm, 5.9 * cm, 5.9 * cm], hAlign="LEFT")
        style = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("LINEBELOW", (0, 0), (-1, 0), 4, WHITE),   # gap between the two rows
            ("LINEAFTER", (0, 0), (-2, -1), 4, WHITE),  # gap between columns
        ]
        k = 0
        for r in range(2):
            for c in range(3):
                on = flags[k][1]
                style.append(("BACKGROUND", (c, r), (c, r),
                              colors.HexColor("#dcfce7") if on else colors.HexColor("#f1f5f9")))
                k += 1
        t.setStyle(TableStyle(style))
        return t

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.4 * cm, bottomMargin=1.4 * cm,
        title=f"AI Briefing {date.today().strftime('%B %d %Y')}",
    )

    story = []
    total = sum(len(v) for v in digest.values())
    ncat = len(digest)

    # ── Cover ──────────────────────────────────────────────────────
    story.append(Spacer(1, 3.4 * cm))
    story.append(Paragraph("ARTIFICIAL INTELLIGENCE", st_kicker))
    story.append(Paragraph("Daily AI Briefing", st_title))
    story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph(date.today().strftime("%A, %B %d, %Y"), st_cdate))
    story.append(Spacer(1, 1.1 * cm))

    read_min = max(2, round(total * 0.4))
    stat_tbl = Table(
        [[Paragraph(str(total), st_snum), Paragraph(str(ncat), st_snum), Paragraph(str(read_min), st_snum)],
         [Paragraph("STORIES", st_slbl), Paragraph("CATEGORIES", st_slbl), Paragraph("MIN READ", st_slbl)]],
        colWidths=[4.7 * cm, 4.7 * cm, 4.7 * cm], hAlign="CENTER")
    stat_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("LINEAFTER", (0, 0), (-2, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 12),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ("TOPPADDING", (0, 1), (-1, 1), 0),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 12),
    ]))
    story.append(stat_tbl)
    story.append(Spacer(1, 1.1 * cm))
    story.append(HRFlowable(width="35%", thickness=3, color=INDIGO, hAlign="CENTER"))
    story.append(PageBreak())

    # ── Contents + top stories ─────────────────────────────────────
    story.append(Paragraph("In this briefing", st_h2))
    for cat, items in digest.items():
        hexc = ACCENT_HEX.get(cat, "#6366f1")
        name = CLEAN_NAME.get(cat, _clean(cat).upper())
        story.append(Paragraph(
            f'<font color="{hexc}"><b>•</b></font>&nbsp;&nbsp;'
            f'<b>{_safe(name)}</b>&nbsp;&nbsp;'
            f'<font color="#94a3b8">{len(items)} stories</font>',
            st_toc))
    story.append(Spacer(1, 0.6 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=LINE))
    story.append(Spacer(1, 0.5 * cm))

    all_items = [it for items in digest.values() for it in items]
    if all_items:
        story.append(Paragraph("Top stories today", st_h2))
        for i, it in enumerate(all_items[:3], 1):
            story.append(Paragraph(
                f'<font color="#6366f1"><b>{i:02d}</b></font>&nbsp;&nbsp;{_safe(it.get("title", ""))}',
                st_top))
    story.append(PageBreak())

    # ── Sections ───────────────────────────────────────────────────
    for ci, (category, items) in enumerate(digest.items()):
        hexc = ACCENT_HEX.get(category, "#6366f1")
        accent = colors.HexColor(hexc)
        name = CLEAN_NAME.get(category, _clean(category).upper())
        tagline = _clean(CAT_TAGLINES.get(category, ""))

        header = Table(
            [[Paragraph(_safe(name), st_cat)],
             [Paragraph(_safe(tagline), st_ctag)]],
            colWidths=[18.0 * cm])
        header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), accent),
            ("TOPPADDING", (0, 0), (-1, 0), 12),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
            ("TOPPADDING", (0, 1), (-1, 1), 0),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 12),
            ("LEFTPADDING", (0, 0), (-1, -1), 16),
            ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ]))
        story.append(header)
        story.append(Spacer(1, 0.4 * cm))

        for i, it in enumerate(items, 1):
            block = [
                Paragraph(
                    f'<font color="{hexc}"><b>{i:02d}</b></font>&nbsp;&nbsp;{_safe(it.get("title", ""))}',
                    st_ttl2),
                Paragraph(_safe(it.get("summary", "")), st_sum),
                role_checklist(it.get("roles", [])),
                Spacer(1, 0.18 * cm),
                Paragraph(
                    f'<b>Source:</b> {_safe(it.get("source", ""))}'
                    f'&nbsp;&nbsp;&nbsp;'
                    f'<link href="{_safe_url(it.get("link", "#"))}" color="#2563eb">'
                    f'<b>Read full article »</b></link>',
                    st_meta),
            ]
            story.append(KeepTogether(block))
            if i < len(items):
                story.append(HRFlowable(width="100%", thickness=0.75, color=LINE,
                                        spaceBefore=0.35 * cm, spaceAfter=0.35 * cm))

        story.append(Spacer(1, 0.5 * cm))
        if ci < ncat - 1:
            story.append(PageBreak())

    # ── Footer ─────────────────────────────────────────────────────
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=LINE, spaceAfter=10))
    story.append(Paragraph(
        f"AI News Digest &nbsp;|&nbsp; {date.today().strftime('%B %d, %Y')} "
        f"&nbsp;|&nbsp; Delivered daily at 9:00 AM IST", st_foot))
    story.append(Paragraph(
        "Aggregated from 30+ trusted AI news &amp; research sources", st_foot))

    doc.build(story)
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

def send_email(html_content: str, pdf_bytes: bytes, item_count: int):
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        raise RuntimeError("Missing GMAIL_USER or GMAIL_APP_PASSWORD env vars.")

    today_str  = date.today().strftime("%b %d")
    today_file = date.today().strftime("%Y-%m-%d")

    # TO_EMAIL may list several addresses separated by commas or semicolons.
    recipients = [e.strip() for e in re.split(r"[,;]+", TO_EMAIL) if e.strip()]

    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"AI Briefing // {today_str} — {item_count} updates inside"
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
    digest = collect_digest()
    digest = filter_by_role(digest)
    count  = sum(len(v) for v in digest.values())

    print(f"Building HTML email ({count} items)...")
    html_content = build_html(digest)

    print("Generating PDF...")
    pdf_bytes = build_pdf(digest)
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
        send_email(html_content, pdf_bytes, count)
    else:
        print("GMAIL_USER / GMAIL_APP_PASSWORD not set — email skipped.")
        print(f"    Open '{local_pdf}' to preview the PDF output.")
