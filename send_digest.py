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
    "🚀 New Launch / Feature":    "Fresh tools, APIs & features you can use right now",
    "🔬 R&D / Research":          "What labs & universities are building behind the scenes",
    "✅ Good News / Wins":         "Funding, partnerships & breakthroughs worth celebrating",
    "⚠️ Bad News / Risk":          "Risks, failures & controversies to keep an eye on",
    "💡 AI Awareness / Must Know": "Big-picture trends every tech person should know",
    "📰 General AI Update":        "Everything else worth knowing today",
}

ROLE_COLORS = {
    "👨‍💻 Developer":              ("#eff6ff", "#1d4ed8"),
    "🧪 Tester / QA":             ("#f0fdf4", "#15803d"),
    "🧠 AI Engineer / ML Engineer":("#faf5ff", "#7e22ce"),
    "🏗️ Architect / Tech Lead":   ("#fff7ed", "#c2410c"),
    "📈 Product / Business":       ("#fefce8", "#a16207"),
    "🌍 AI Awareness (Everyone)":  ("#f8fafc", "#475569"),
    "🌍 General Awareness":        ("#f8fafc", "#475569"),
}


# ══════════════════════════════════════════════════════════════════════════════
#  HTML EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def _role_badge(role: str) -> str:
    bg, color = ROLE_COLORS.get(role, ("#f1f5f9", "#334155"))
    return (
        f'<span style="display:inline-block;background:{bg};color:{color};'
        f'border:1px solid {color}33;font-size:11px;font-weight:600;'
        f'padding:2px 9px;border-radius:20px;margin:2px 3px 2px 0;'
        f'white-space:nowrap;">{role}</span>'
    )


def _cat_section(category: str, items: list, idx: int) -> str:
    bg, accent, light = CAT_STYLE.get(category, ("#1e293b", "#94a3b8", "#f8fafc"))
    tagline = CAT_TAGLINES.get(category, "")

    cards_html = ""
    for i, it in enumerate(items):
        badges = "".join(_role_badge(r) for r in it.get("roles", []))
        ai_tag = (
            '<span style="background:#7c3aed;color:#fff;font-size:10px;'
            'padding:1px 7px;border-radius:10px;margin-left:6px;">🤖 AI</span>'
            if it.get("ai_powered") else ""
        )
        separator = "" if i == len(items) - 1 else (
            f'<div style="height:1px;background:{accent}22;margin:14px 0;"></div>'
        )
        cards_html += f"""
        <div>
          <div style="display:flex;justify-content:space-between;align-items:flex-start;">
            <div style="font-size:14px;font-weight:700;color:#111;line-height:1.4;
                        flex:1;margin-right:8px;">
              <a href="{it['link']}" style="color:#111;text-decoration:none;">{it['title']}</a>
            </div>
          </div>
          <div style="font-size:13.5px;color:#374151;line-height:1.55;margin:6px 0 8px;">
            {it['summary']}
          </div>
          <div style="margin-bottom:8px;">{badges}</div>
          <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;">
            <span style="font-size:11.5px;color:#6b7280;">
              📰 {it['source']}{ai_tag}
            </span>
            <a href="{it['link']}"
               style="display:inline-block;background:{accent};color:#fff;
                      font-size:12px;font-weight:600;padding:5px 14px;
                      border-radius:6px;text-decoration:none;margin-top:4px;">
              Read more →
            </a>
          </div>
          {separator}
        </div>
        """

    return f"""
    <div style="margin-bottom:24px;border-radius:12px;overflow:hidden;
                box-shadow:0 1px 6px rgba(0,0,0,0.09);">
      <!-- Category header -->
      <div style="background:{bg};padding:14px 20px;">
        <div style="font-size:16px;font-weight:800;color:#fff;">{category}</div>
        <div style="font-size:12px;color:{light};opacity:0.85;margin-top:2px;">{tagline}</div>
      </div>
      <!-- Cards -->
      <div style="background:#fff;padding:18px 20px;">
        {cards_html}
      </div>
    </div>
    """


def build_html(digest: dict) -> str:
    today     = date.today().strftime("%A, %B %d %Y")
    date_short= date.today().strftime("%b %d")
    total     = sum(len(v) for v in digest.values())

    # Stats bar
    stats_items = "".join(
        f'<span style="margin:0 12px;font-size:13px;">'
        f'<b style="color:#111;">{len(v)}</b>'
        f'<span style="color:#6b7280;"> {cat}</span></span>'
        for cat, v in digest.items()
    )

    sections = "".join(_cat_section(cat, items, i)
                       for i, (cat, items) in enumerate(digest.items()))

    if not sections:
        sections = '<p style="color:#6b7280;text-align:center;padding:40px;">Quiet AI day — nothing major today. Check back tomorrow!</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
<div style="max-width:640px;margin:0 auto;padding:24px 16px 40px;">

  <!-- ── HEADER ── -->
  <div style="background:linear-gradient(135deg,#0f172a 0%,#1e1b4b 60%,#312e81 100%);
              border-radius:16px;padding:32px 28px 24px;margin-bottom:20px;text-align:center;">
    <div style="font-size:36px;margin-bottom:6px;">🧠</div>
    <div style="font-size:24px;font-weight:900;color:#fff;letter-spacing:-0.5px;">
      Daily AI Briefing
    </div>
    <div style="font-size:13px;color:#a5b4fc;margin-top:6px;">{today}</div>
    <div style="margin-top:16px;display:inline-block;background:rgba(255,255,255,0.1);
                border-radius:20px;padding:6px 18px;">
      <span style="color:#e0e7ff;font-size:13px;font-weight:600;">
        {total} stories · 3-min read · PDF attached 📎
      </span>
    </div>
  </div>

  <!-- ── STATS BAR ── -->
  <div style="background:#fff;border-radius:10px;padding:12px 16px;margin-bottom:20px;
              text-align:center;box-shadow:0 1px 4px rgba(0,0,0,0.07);overflow-x:auto;">
    {stats_items}
  </div>

  <!-- ── SECTIONS ── -->
  {sections}

  <!-- ── FOOTER ── -->
  <div style="text-align:center;padding-top:16px;border-top:1px solid #e2e8f0;margin-top:8px;">
    <div style="font-size:13px;color:#64748b;">
      📎 Full digest PDF attached — save, print, or share it
    </div>
    <div style="font-size:11px;color:#94a3b8;margin-top:6px;">
      Delivered daily at 9 AM · AI News Digest Bot · {date_short}
    </div>
  </div>

</div>
</body>
</html>"""


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
    msg["Subject"] = f"🧠 AI Briefing {today_str} — {item_count} updates inside"
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
