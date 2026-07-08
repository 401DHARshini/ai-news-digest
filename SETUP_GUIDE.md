# 🚀 Complete Setup Guide - AI News Digest with Daily 9 AM Emails

## ✨ What You Now Have

Your AI News Digest is now set up to:
- ✅ Fetch news from 30+ AI sources daily
- ✅ Send you an email **every day at 9:00 AM** (IST) / 3:30 AM UTC
- ✅ Include a **professional, attractive PDF** with proper formatting
- ✅ Categorize stories by type (Model Updates, R&D, Good News, Bad News, etc.)
- ✅ Tag stories by role (Developer, AI Engineer, Architect, Business, etc.)
- ✅ Generate HTML email + PDF attachment in your inbox

---

## 📧 Setting Up GitHub Actions & Email

### Step 1: Create a GitHub Repository
```bash
cd ai-news-digest
git init
git add .
git commit -m "Initial commit: AI news digest with daily 9 AM emails"
git remote add origin https://github.com/YOUR-USERNAME/ai-news-digest.git
git push -u origin main
```

### Step 2: Add GitHub Secrets
Go to your repo → **Settings → Secrets and variables → Actions** → Click **"New repository secret"**

Add these secrets:

| Secret Name | Value | How to Get |
|---|---|---|
| `GMAIL_USER` | your_email@gmail.com | Your Gmail address |
| `GMAIL_APP_PASSWORD` | 16-char password | See "Get Gmail App Password" below |
| `TO_EMAIL` | recipient@gmail.com | Where to send digests (can be same as GMAIL_USER) |
| `NEWSAPI_KEY` | (optional) | Free from https://newsapi.org |
| `HF_TOKEN` | (optional) | Free from https://huggingface.co |

#### 🔐 Get Gmail App Password (2 min)
1. Go to https://myaccount.google.com/security
2. Enable **2-Step Verification** (if not already on)
3. Go to https://myaccount.google.com/apppasswords
4. Select "Mail" and "Windows Computer" (or your device)
5. Copy the 16-character password → paste into GitHub secret

**Note**: This is NOT your Gmail password. It's a special app-only password.

#### 🆓 Optional: NewsAPI Key (for extra news sources)
1. Go to https://newsapi.org/register
2. Sign up free (no credit card needed)
3. Copy your API key → add as `NEWSAPI_KEY` secret
4. Free tier: 100 requests/day (enough for 1 daily run)

#### 🤖 Optional: HuggingFace Token (for AI-powered summaries)
1. Go to https://huggingface.co/join
2. Sign up free
3. Go to https://huggingface.co/settings/tokens
4. Create a token with "Read" permission
5. Copy → add as `HF_TOKEN` secret

---

## ⏰ Daily 9 AM Email Schedule

**The workflow runs at:** 3:30 AM UTC = 9:00 AM IST (India Standard Time)

### To Change the Time:
Edit `.github/workflows/daily.yml` line 6:
```yaml
cron: "30 3 * * *"
```

Replace with your preferred time (format: `"minute hour * * *"`, times in UTC):
- `"0 9 * * *"` = 9:00 AM UTC
- `"30 8 * * *"` = 8:30 AM UTC  
- `"0 14 * * *"` = 2:00 PM UTC
- `"0 18 * * *"` = 6:00 PM UTC

**IST Conversion**: IST = UTC + 5:30 hours
- 3:30 AM UTC = 9:00 AM IST
- 8:30 AM UTC = 2:00 PM IST

---

## 🎨 The New Professional PDF

Your PDF now includes:

### 📑 Cover Page
- Gradient header with date
- Statistics box (total stories, categories, read time)
- Professional typography

### 📊 Table of Contents
- Quick overview of all categories
- Story count per category
- Organized layout

### ⭐ Top 3 Stories
- Highlights the most important news of the day
- Full titles and quick scan

### 📰 Full Digest
- Organized by category (color-coded sections)
- Each story includes:
  - Story number and title (bold)
  - One-line summary
  - Source attribution
  - Relevant roles (Developer, AI Engineer, etc.)
  - "Read full article" link
- Visual separators between stories

### 📝 Footer
- Generation timestamp
- "Delivered daily at 9 AM" message
- Professional branding

---

## 🎯 How Stories Are Categorized & Tagged

### 7 News Categories
1. **🤖 Model Updates** — GPT, Claude, Gemini, Llama releases
2. **🚀 New Launch / Feature** — APIs, tools, features going live
3. **🔬 R&D / Research** — Academic papers, breakthroughs
4. **✅ Good News / Wins** — Funding, partnerships, success
5. **⚠️ Bad News / Risk** — Lawsuits, bans, vulnerabilities
6. **💡 AI Awareness / Must Know** — Trends, policy, ethics, jobs
7. **📰 General AI Update** — Everything else

### 6 Audience Roles
Each story is tagged with who should care:
- 👨‍💻 **Developer** — APIs, SDKs, tools, code examples
- 🧪 **Tester / QA** — Testing, benchmarks, reliability
- 🧠 **AI Engineer / ML Engineer** — Models, training, inference
- 🏗️ **Architect / Tech Lead** — Infrastructure, scale, deployment
- 📈 **Product / Business** — Funding, strategy, market news
- 🌍 **AI Awareness (Everyone)** — Policy, ethics, trends

---

## 🚀 Test Before Going Live

### Test Locally (Recommended)
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (or create .env file)
export GMAIL_USER="your_email@gmail.com"
export GMAIL_APP_PASSWORD="your16charpassword"
export TO_EMAIL="recipient@gmail.com"

# Test the full workflow
python send_digest.py

# Or just see what gets collected (no email)
python fetch_news.py
```

### Verify PDF & Email
- The script will save `AI-Briefing-2024-01-15.pdf` locally (for testing)
- If Gmail secrets are set, it'll send an email too
- Check your inbox for the beautiful digest!

### Manual Test in GitHub
1. Go to your repo → **Actions** tab
2. Click "Daily AI News Digest"
3. Click **"Run workflow"** button
4. Check your email in ~1 minute

---

## 📊 Customization Options

### Filter by Role (Advanced)
Only get news relevant to your job:
```bash
# In GitHub secrets, add ROLE_FILTER
ROLE_FILTER="Developer,AI Engineer"
```

Leave empty to get all stories.

### Add/Remove News Sources
Edit `fetch_news.py` → `RSS_FEEDS` list:
```python
RSS_FEEDS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://your-custom-feed.com/rss",  # Add your own!
]
```

### Change Stories Per Category
Edit `send_digest.py` → `collect_digest()`:
```python
def collect_digest(max_per_category: int = 6):  # Change 6 to another number
```

### Customize PDF Colors & Design
Edit `send_digest.py` → `build_pdf()` function:
```python
CAT_PDF_COLOR = {
    "🤖 Model Updates": colors.HexColor("#6366f1"),  # Change hex colors
}
```

---

## 🔍 Troubleshooting

### Email not received?
1. ✅ Check GitHub Actions "Send daily digest" succeeded (green checkmark)
2. ✅ Verify Gmail secrets are correct (use app password, not regular password)
3. ✅ Check spam/promotions folder
4. ✅ Test manually: `python send_digest.py`

### No stories in digest?
1. ✅ Check news sources are responding (RSS feeds sometimes go down)
2. ✅ Verify AI keywords match your news (edit `AI_KEYWORDS` in fetch_news.py)
3. ✅ Check time window (default: 26 hours, edit `LOOKBACK_HOURS`)

### PDF looks wrong?
- Run locally first: `python send_digest.py` to debug
- Check terminal output for errors
- Verify reportlab is installed: `pip install reportlab==4.4.10`

### Workflow not running at 9 AM?
- GitHub Actions uses UTC only (not your timezone)
- Cron `"30 3 * * *"` = 3:30 AM UTC
- Adjust based on your timezone/IST conversion

---

## 📞 Support & Next Steps

### Current Setup Status:
✅ Code updated with enhanced PDF design
✅ GitHub Actions set to 9:00 AM IST (3:30 AM UTC)
✅ Email template updated with new timing message
✅ README updated with full documentation

### What to do now:
1. Push code to GitHub
2. Add GitHub secrets
3. Test manually via GitHub Actions (Run workflow)
4. Wait for 9 AM tomorrow to receive your first automated digest! 🎉

---

**Questions?** Edit the code, run locally to test, then push to GitHub. GitHub Actions will handle the daily scheduling!
