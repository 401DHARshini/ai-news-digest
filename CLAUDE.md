# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A serverless daily AI-news digest bot. It scrapes AI news from ~28 RSS feeds + optional NewsAPI, categorizes and role-tags each story, then emails a styled HTML digest with a PDF attachment via Gmail SMTP. It runs entirely on GitHub Actions cron — no server, no database.

## Commands

```bash
pip install -r requirements.txt

# Preview collected/categorized stories in the terminal (no email, no PDF)
python fetch_news.py

# Full run: build HTML + PDF, save PDF locally, send email if creds are set
python send_digest.py

# Test HuggingFace AI enrichment in isolation (needs HF_TOKEN)
python ai_summarizer.py
```

`send_digest.py` always writes `AI-Briefing-<date>.pdf` locally even when email creds are absent, so you can iterate on layout without sending mail. There is no test suite, linter, or build step configured.

## Architecture — data flow

The pipeline is three modules chained by function calls, not a framework:

1. **`fetch_news.py`** — the collection + classification core.
   - `collect_digest(max_per_category=6)` is the single entry point everything else calls. It fetches RSS + NewsAPI items, dedupes by normalized title prefix, groups by category, and returns an **ordered dict** `{category: [items]}`. The category display order is hard-coded in `collect_digest`'s `order` list, not derived from the rules dict.
   - Each item is a plain dict: `title, summary, link, source, category, roles, ai_powered`.
   - Classification is **keyword-based by default** (`CATEGORY_RULES`, `ROLE_RULES` — first matching category wins; roles accumulate). Items are filtered to `LOOKBACK_HOURS` (26h) and to `AI_KEYWORDS` (arxiv feeds bypass the keyword filter).

2. **`ai_summarizer.py`** — optional LLM enrichment layer.
   - Only active when `HF_TOKEN` is set (`HF_ENABLED` in `fetch_news.py`). When active, `ai_enrich()` replaces the keyword summary/category/roles with output from HuggingFace's Mistral-7B (falling back to Zephyr-7B), parsed from a single JSON-returning prompt.
   - **Graceful degradation is load-bearing**: if the token is unset, the import fails, or any HF call/parse fails, the code silently falls back to keyword logic. Preserve this — never make enrichment a hard dependency.

3. **`send_digest.py`** — presentation + delivery.
   - `filter_by_role(digest)` narrows the digest by the `ROLE_FILTER` env var before rendering.
   - `build_html()` and `build_pdf()` (reportlab) are **two independent renderers of the same digest dict** — they duplicate the category color palette and taglines. Any change to categories, roles, colors, or ordering must be mirrored in both renderers (and PDF imports reportlab lazily inside `build_pdf`).

### Cross-cutting invariant: category & role strings are keys, not just labels

Category and role names are emoji-prefixed strings (e.g. `"🤖 Model Updates"`, `"👨‍💻 Developer"`) used as **dict keys** across all three files — in `CATEGORY_RULES`/`ROLE_RULES`, `CAT_STYLE`, `CAT_TAGLINES`, `ROLE_COLORS`, `CAT_PDF_COLOR`, and the `order` list. Renaming one requires updating every occurrence or styling/ordering silently breaks. Note `ROLE_RULES` uses `"🌍 AI Awareness (Everyone)"` while the no-match fallback in `tag_roles` emits `"🌍 General Awareness"` — both are intentionally present in `ROLE_COLORS`.

## Configuration (all via environment variables / GitHub Secrets)

Set these as repo Secrets under **Settings → Secrets and variables → Actions**; the workflow ([.github/workflows/daily.yml](.github/workflows/daily.yml)) passes them through as env vars.

| Var | Required | Purpose |
|-----|----------|---------|
| `GMAIL_USER` | yes (to send) | Gmail address to send from |
| `GMAIL_APP_PASSWORD` | yes (to send) | 16-char Gmail **App Password**, not the account password |
| `TO_EMAIL` | no | Recipient; defaults to `GMAIL_USER` |
| `NEWSAPI_KEY` | no | Enables the NewsAPI source; RSS-only if unset |
| `HF_TOKEN` | no | Enables LLM enrichment; keyword fallback if unset |
| `ROLE_FILTER` | no | Comma-separated roles (e.g. `Developer,AI Engineer`) to restrict the digest; matched case-insensitively as substrings against role names |

Without any secrets, `python send_digest.py` still runs end-to-end and produces a local PDF. The cron schedule (currently `30 2 * * *` UTC = 8:00 AM IST) lives in the workflow file; cron times are UTC.

## Common change points

- Add/remove **sources** → `RSS_FEEDS` in `fetch_news.py`.
- Tune **classification** → `CATEGORY_RULES` / `ROLE_RULES` in `fetch_news.py` (remember: first category match wins; check keyword ordering).
- Change **stories per category** → `max_per_category` in `collect_digest`.
- Change **category order** → `order` list in `collect_digest`.
- Edit **email look** → `build_html` / `_cat_section` / `_role_badge` in `send_digest.py` (email uses inline CSS only — no `<style>` blocks, for client compatibility).
- Edit **PDF look** → `build_pdf` in `send_digest.py`.
