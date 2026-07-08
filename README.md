# 🧠 Daily AI News Digest

Pulls fresh AI news from **30+ RSS feeds** + NewsAPI, boils each story down to one crisp line, 
and emails you a **beautiful PDF + HTML digest every day at 9 AM** via GitHub Actions — no server needed.

## What it does

- **Scans 30+ AI news sources** (TechCrunch, VentureBeat, MIT Tech Review, The Verge, arXiv, 
  Google AI, OpenAI, Anthropic, DeepMind, HuggingFace, Mistral, and more).
  
- **Filters to fresh content** — only the last ~26 hours so it stays "today's news."

- **Auto-categorizes stories** into:
  - 🤖 Model Updates — new versions, capabilities, benchmarks
  - 🚀 New Launch / Feature — fresh tools, APIs, features you can use now
  - 🔬 R&D / Research — what labs & universities are building
  - ✅ Good News / Wins — funding, partnerships, breakthroughs
  - ⚠️ Bad News / Risk — risks, failures, controversies to watch
  - 💡 AI Awareness / Must Know — big-picture trends everyone should know

- **Tags stories by role** — each article gets tagged with who it's useful for:
  - 👨‍💻 Developer, 🧪 Tester/QA, 🧠 AI Engineer/ML Engineer, 🏗️ Architect/Tech Lead, 
  - 📈 Product/Business, 🌍 General Awareness (stories can have multiple tags)

- **Sends beautiful HTML email** with color-coded cards, summaries, and "Read more" links.

- **Attaches a professional PDF** with:
  - ✨ Gradient cover page with stats
  - 📑 Table of contents & key highlights
  - 🎯 Top 3 stories of the day
  - 📊 Organized by category with proper typography
  - 🎨 Professional color scheme, proper spacing & layout
  - 💾 Easy to save, print, or share

## 1. Get a Gmail App Password (2 min)
You can't use your normal Gmail password for this — Google requires an "App Password."
1. Turn on 2-Step Verification on your Google account (if not already on): https://myaccount.google.com/security
2. Go to https://myaccount.google.com/apppasswords
3. Create one for "Mail" → copy the 16-character password it gives you.

## 2. (Optional) Get a free NewsAPI key
Go to https://newsapi.org/register — free tier gives you enough calls for one
request/day. Skip this if RSS feeds alone are enough for you; the script works fine without it.

## 3. Push this folder to a GitHub repo
```bash
cd ai-news-digest
git init
git add .
git commit -m "Daily AI news digest bot"
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

## 4. Add your secrets in GitHub
In your repo: **Settings → Secrets and variables → Actions → New repository secret**, add:

| Secret name          | Value                                  |
|-----------------------|-----------------------------------------|
| `GMAIL_USER`           | your_address@gmail.com                 |
| `GMAIL_APP_PASSWORD`   | the 16-character app password          |
| `TO_EMAIL`             | the address you want digests sent to   |
| `NEWSAPI_KEY`          | (optional) your NewsAPI key            |
| `ROLE_FILTER`          | (optional) e.g. `Developer,AI Engineer` to only get news relevant to your role(s). Leave the secret unset to get everything across all roles. |

## 5. Done — it runs daily automatically

The workflow in `.github/workflows/daily.yml` runs **every day at 3:30 AM UTC (9:00 AM IST)**.

✅ **Each day at 9 AM, the system will:**
1. Fetch latest AI news from 30+ sources
2. Categorize and summarize each story
3. Generate an attractive PDF digest
4. Send HTML email + PDF attachment to your inbox

**To change the time**: Edit the `cron: "30 3 * * *"` line in `.github/workflows/daily.yml`
- Cron format: `minute hour * * *` (times in UTC)
- Examples: `0 9 * * *` = 9:00 AM UTC, `30 13 * * *` = 1:30 PM UTC

You can also trigger it manually any time: go to **Actions** tab → "Daily AI News Digest" → **Run workflow**.

## Run locally to test first
```bash
pip install -r requirements.txt
export GMAIL_USER="you@gmail.com"
export GMAIL_APP_PASSWORD="xxxxxxxxxxxxxxxx"
export TO_EMAIL="you@gmail.com"
python send_digest.py
```
Or just preview what gets collected without sending an email:
```bash
python fetch_news.py
```

## 📋 What's Included

### HTML Email
- Beautiful, responsive design with gradient header
- Color-coded category sections
- Role badges for each story (developer, architect, etc.)
- "Read more" links with source attribution
- Estimated read time

### Professional PDF
- **Cover page**: gradient background, date, stats box
- **Table of contents**: quick overview of all categories
- **Top 3 stories**: quick highlight of the most important news
- **Categorized sections**: organized by news type with proper typography
- **Smart spacing**: readable line-height, proper margins
- **Metadata**: source attribution, role tags, read-more links per story
- **Footer**: consistent branding, generation timestamp

## Customize

- **Email time**: Edit `cron: "30 3 * * *"` in `.github/workflows/daily.yml` (UTC).
  - Change to `"0 9 * * *"` for 9:00 AM UTC, etc.
  
- **News sources**: Edit `RSS_FEEDS` in `fetch_news.py` — add/remove RSS URLs.

- **Categories**: Edit `CATEGORY_RULES` in `fetch_news.py` to change how stories are sorted.

- **Stories per category**: Change `max_per_category` in `collect_digest()` function.

- **PDF/Email design**: 
  - PDF: Edit `build_pdf()` in `send_digest.py` (fonts, colors, layout)
  - Email HTML: Edit `build_html()` in `send_digest.py`
  
- **Role filter**: Set `ROLE_FILTER` GitHub secret to only get news for specific roles
  - Example: `"Developer,AI Engineer"` will only show stories relevant to these roles
  - Leave unset to get all stories
