"""
Builds a beautiful HTML email + PDF attachment and sends via Gmail SMTP.
- HTML email: full UI with color-coded cards, role badges, stats bar
- PDF: clean downloadable digest people can save/share/print
"""

import os
import io
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from fetch_news import collect_digest


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

def build_pdf(digest: dict) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
        Table, TableStyle, KeepTogether, PageBreak, Image
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader

    buf = io.BytesIO()

    class GradientCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        title=f"AI Briefing {date.today().strftime('%B %d %Y')}",
    )

    # ── Colour palette ────────────────────────────────────────────
    CAT_PDF_COLOR = {
        "🤖 Model Updates":           colors.HexColor("#6366f1"),
        "🚀 New Launch / Feature":    colors.HexColor("#3b82f6"),
        "🔬 R&D / Research":          colors.HexColor("#10b981"),
        "✅ Good News / Wins":         colors.HexColor("#22c55e"),
        "⚠️ Bad News / Risk":          colors.HexColor("#ef4444"),
        "💡 AI Awareness / Must Know": colors.HexColor("#f59e0b"),
        "📰 General AI Update":        colors.HexColor("#8b5cf6"),
    }
    WHITE  = colors.white
    DARK   = colors.HexColor("#0f172a")
    GRAY   = colors.HexColor("#64748b")
    LGRAY  = colors.HexColor("#f1f5f9")
    BORDER = colors.HexColor("#e2e8f0")
    PRIMARY = colors.HexColor("#6366f1")

    # ── Styles ───────────────────────────────────────────────────
    S = getSampleStyleSheet()

    title_style = ParagraphStyle("Title", parent=S["Heading1"],
        fontSize=48, fontName="Helvetica-Bold", textColor=WHITE,
        alignment=TA_CENTER, spaceAfter=8, leading=52)
    subtitle_style = ParagraphStyle("Subtitle", parent=S["Normal"],
        fontSize=14, textColor=colors.HexColor("#c7d2fe"), alignment=TA_CENTER, spaceAfter=4, leading=18)
    date_style = ParagraphStyle("Date", parent=S["Normal"],
        fontSize=12, textColor=colors.HexColor("#a5b4fc"), alignment=TA_CENTER, spaceAfter=16)

    stats_header = ParagraphStyle("StatsHeader", parent=S["Normal"],
        fontSize=9, fontName="Helvetica-Bold", textColor=DARK, spaceAfter=4)
    stats_value = ParagraphStyle("StatsValue", parent=S["Normal"],
        fontSize=24, fontName="Helvetica-Bold", textColor=PRIMARY, spaceAfter=8)

    cat_style = ParagraphStyle("CatHead", parent=S["Normal"],
        fontSize=16, fontName="Helvetica-Bold", textColor=WHITE, leading=18, spaceAfter=4)
    tagline_style = ParagraphStyle("Tagline", parent=S["Normal"],
        fontSize=10, textColor=colors.HexColor("#e2e8f0"), leading=13, spaceAfter=0)

    item_num = ParagraphStyle("ItemNum", parent=S["Normal"],
        fontSize=12, fontName="Helvetica-Bold", textColor=DARK, spaceAfter=0)
    item_title_style = ParagraphStyle("ItemTitle", parent=S["Normal"],
        fontSize=12, fontName="Helvetica-Bold", textColor=DARK,
        spaceAfter=4, leading=16)
    item_sum_style = ParagraphStyle("ItemSum", parent=S["Normal"],
        fontSize=10, textColor=colors.HexColor("#374151"),
        spaceAfter=6, leading=14)
    meta_style = ParagraphStyle("Meta", parent=S["Normal"],
        fontSize=8, textColor=GRAY, spaceAfter=2)
    role_style = ParagraphStyle("Role", parent=S["Normal"],
        fontSize=8, textColor=colors.HexColor("#4338ca"), leading=11)

    toc_header = ParagraphStyle("TOCHeader", parent=S["Normal"],
        fontSize=14, fontName="Helvetica-Bold", textColor=DARK, spaceAfter=12)
    toc_item = ParagraphStyle("TOCItem", parent=S["Normal"],
        fontSize=10, textColor=DARK, spaceAfter=6, leading=13)

    story = []

    # ── COVER PAGE ────────────────────────────────────────────
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("🧠", ParagraphStyle("Icon", parent=S["Normal"],
                                                 fontSize=72, alignment=TA_CENTER, spaceAfter=16)))
    story.append(Paragraph("Daily AI Briefing", title_style))
    story.append(Paragraph(date.today().strftime("%A, %B %d, %Y"), date_style))

    total = sum(len(v) for v in digest.values())
    story.append(Spacer(1, 0.8*cm))

    # Stats box
    stats_data = [
        [Paragraph(f"<b>{total}</b>", stats_value),
         Paragraph(f"<b>{len(digest)}</b>", stats_value),
         Paragraph(f"<b>3–5</b>", stats_value)],
        [Paragraph("Stories", stats_header),
         Paragraph("Categories", stats_header),
         Paragraph("Min Read", stats_header)],
    ]
    stats_table = Table(stats_data, colWidths=[5*cm, 5*cm, 5*cm])
    stats_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,1), LGRAY),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("GRID", (0,0), (-1,-1), 0.5, BORDER),
    ]))
    story.append(KeepTogether([stats_table, Spacer(1, 1.5*cm)]))

    story.append(PageBreak())

    # ── TABLE OF CONTENTS ────────────────────────────────────
    story.append(Paragraph("📑 Inside This Briefing", toc_header))
    story.append(Spacer(1, 0.2*cm))

    toc_items = []
    for cat, items in digest.items():
        toc_items.append(Paragraph(f"<b>{cat}</b> — {len(items)} stories", toc_item))

    for item in toc_items:
        story.append(item)

    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=20, spaceBefore=10))

    # ── KEY HIGHLIGHTS ───────────────────────────────────────
    all_items = []
    for items in digest.values():
        all_items.extend(items)

    if all_items:
        story.append(Paragraph("⭐ Top 3 Stories Today", toc_header))
        for i, item in enumerate(all_items[:3], 1):
            story.append(Paragraph(f"{i}. {item['title']}",
                                  ParagraphStyle("TopStory", parent=S["Normal"],
                                              fontSize=11, fontName="Helvetica-Bold",
                                              textColor=DARK, spaceAfter=8, leading=14)))
        story.append(Spacer(1, 0.5*cm))
        story.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=20, spaceBefore=10))

    story.append(PageBreak())

    # ── SECTIONS ──────────────────────────────────────────────
    for cat_idx, (category, items) in enumerate(digest.items()):
        accent = CAT_PDF_COLOR.get(category, colors.HexColor("#6366f1"))
        tagline = CAT_TAGLINES.get(category, "")

        # Category header with background
        header_data = [[Paragraph(category, cat_style)],
                       [Paragraph(tagline, tagline_style)]]
        header_table = Table(header_data, colWidths=[17.5*cm])
        header_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), accent),
            ("TOPPADDING", (0,0), (-1,-1), 14),
            ("BOTTOMPADDING", (0,0), (-1,-1), 10),
            ("LEFTPADDING", (0,0), (-1,-1), 16),
            ("RIGHTPADDING", (0,0), (-1,-1), 16),
        ]))
        story.append(KeepTogether([header_table, Spacer(1, 0.35*cm)]))

        # Items
        for i, it in enumerate(items, 1):
            roles_text = "  ".join(it.get("roles", []))
            ai_label = " 🤖 AI-Powered" if it.get("ai_powered") else ""

            # Story number and title
            story.append(Paragraph(f"<b>{i}.</b> {it['title']}", item_title_style))

            # Summary
            story.append(Paragraph(it["summary"], item_sum_style))

            # Metadata row
            meta_row = f"<b>Source:</b> {it['source']}{ai_label}"
            story.append(Paragraph(meta_row, meta_style))

            # Roles
            if roles_text:
                story.append(Paragraph(f"<b>For:</b> {roles_text}", role_style))

            # Separator
            if i < len(items):
                story.append(Spacer(1, 0.25*cm))
                story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER,
                                       spaceAfter=0.35*cm, spaceBefore=0.1*cm))

        story.append(Spacer(1, 0.8*cm))

        # Page break between categories (except last)
        if cat_idx < len(digest) - 1:
            story.append(PageBreak())

    # ── FOOTER ─────────────────────────────────────────────────
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=12, spaceBefore=6))

    footer_text = f"AI News Digest  ·  {date.today().strftime('%B %d, %Y')}  ·  Delivered daily at 9 AM"
    story.append(Paragraph(footer_text,
        ParagraphStyle("Footer", parent=S["Normal"],
                      fontSize=9, textColor=GRAY, alignment=TA_CENTER)))
    story.append(Paragraph("Powered by intelligent news aggregation from 30+ AI sources",
        ParagraphStyle("SubFooter", parent=S["Normal"],
                      fontSize=8, textColor=colors.HexColor("#cbd5e1"), alignment=TA_CENTER)))

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
    if len(GMAIL_APP_PASSWORD) != 16:
        print(f"⚠️  GMAIL_APP_PASSWORD is {len(GMAIL_APP_PASSWORD)} chars — a Gmail "
              "App Password is exactly 16. If login fails, make sure you used an "
              "App Password (https://myaccount.google.com/apppasswords), NOT your "
              "normal Gmail password.")

    today_str  = date.today().strftime("%b %d")
    today_file = date.today().strftime("%Y-%m-%d")

    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"🧠 AI Briefing {today_str} — {item_count} updates inside"
    msg["From"]    = GMAIL_USER
    msg["To"]      = TO_EMAIL

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
        server.sendmail(GMAIL_USER, TO_EMAIL, msg.as_string())

    print(f"✅ Sent digest + PDF to {TO_EMAIL}  ({item_count} items)")


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
    print(f"PDF saved locally → {local_pdf}")

    if GMAIL_USER and GMAIL_APP_PASSWORD:
        print("Sending email...")
        send_email(html_content, pdf_bytes, count)
    else:
        print("⚠️  GMAIL_USER / GMAIL_APP_PASSWORD not set — email skipped.")
        print(f"    Open '{local_pdf}' to preview the PDF output.")
