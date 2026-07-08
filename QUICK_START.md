# ⚡ Quick Start - AI News Digest at 9 AM

## 🎯 What You Have (5 minutes to understand)

A fully automated AI news digest system that will **email you daily at 9 AM IST** with:

✅ **Beautiful PDF** (20 pages)
- Gradient cover page
- Table of contents
- Top 3 stories highlighted
- 28-30 categorized stories
- Professional typography & colors

✅ **HTML Email** with:
- Color-coded categories
- Role-based story tags
- "Read more" links
- PDF attachment

✅ **Automatic Updates**
- 30+ AI news sources
- 7 smart categories
- 6 audience roles
- Daily at 9:00 AM IST

---

## 🚀 Setup (10 minutes)

### Step 1: Push to GitHub
```bash
cd ai-news-digest
git add . && git commit -m "AI digest with 9 AM emails"
git push origin main
```

### Step 2: Add Secrets
GitHub → Settings → Secrets → Add these:

```
GMAIL_USER = your_email@gmail.com
GMAIL_APP_PASSWORD = [16-char app password - get from Google]
TO_EMAIL = your_email@gmail.com
```

**Get Gmail App Password:**
1. Go to https://myaccount.google.com/apppasswords
2. Select Mail → Your device
3. Copy the 16-character password

### Step 3: Test
GitHub → Actions → Daily AI News Digest → Run workflow

Check email in 1 minute! ✅

---

## 📧 What You'll Receive

### Time: 9:00 AM IST every day

### Email Subject:
```
🧠 AI Briefing Jul 08 — 28 updates inside
```

### Email Body:
- Colorful category sections
- Story summaries with role tags
- Read more links
- PDF attachment

### PDF Attachment:
```
Page 1: Cover (gradient, stats)
Page 2: TOC + Top 3 Stories
Pages 3+: Full Digest (organized by category)
```

---

## ⏰ Email Schedule

**Current**: 3:30 AM UTC = **9:00 AM IST** ✅

To change:
- Edit `.github/workflows/daily.yml` line 6
- Change `"30 3 * * *"` to your time (UTC)
- Push to GitHub

Examples:
```
"0 9 * * *"   = 9:00 AM UTC (2:30 PM IST)
"30 12 * * *" = 12:30 PM UTC (6:00 PM IST)
"0 14 * * *"  = 2:00 PM UTC (7:30 PM IST)
```

**Tip**: Time = UTC, IST = UTC + 5:30 hours

---

## 📋 What's in Each Story

### Title
The news headline

### Summary
One punchy line (max 160 chars)

### Category (one of 7)
- 🤖 Model Updates - new versions, benchmarks
- 🚀 New Launch/Feature - APIs, tools, features
- 🔬 R&D/Research - papers, breakthroughs
- ✅ Good News/Wins - funding, partnerships
- ⚠️ Bad News/Risk - risks, vulnerabilities
- 💡 AI Awareness - trends, policy, ethics
- 📰 General - everything else

### Role Tags (audience)
- 👨‍💻 Developer
- 🧪 Tester/QA
- 🧠 AI Engineer/ML Engineer
- 🏗️ Architect/Tech Lead
- 📈 Product/Business
- 🌍 General Awareness

### Source
Where the story came from (TechCrunch, arXiv, etc.)

### Link
Click to read full article

---

## 🎨 PDF Design Features

### Cover Page
```
🧠
Daily AI Briefing
Tuesday, July 08, 2026

┌─────────────────────────┐
│ 28 stories | 7 categories│
│        3-min read        │
└─────────────────────────┘
```

### Table of Contents
```
📑 Inside This Briefing

🤖 Model Updates — 6 stories
🚀 New Launch/Feature — 5 stories
🔬 R&D/Research — 4 stories
✅ Good News/Wins — 5 stories
⚠️ Bad News/Risk — 4 stories
💡 AI Awareness — 3 stories
📰 General — 1 story
```

### Top 3 Stories
```
⭐ Top 3 Stories Today

1. OpenAI Releases GPT-5...
2. Claude 3.5 Sonnet Adds...
3. DeepMind's New Reasoning Model...
```

### Story Format
```
1. [Story Title in Bold]

[One-line summary explaining the news]

Source: TechCrunch
For: 👨‍💻 Developer, 🧠 AI Engineer
Read more →
```

---

## 🔍 Sources (30+)

### Tech News
- TechCrunch AI
- VentureBeat AI
- The Verge
- Wired
- Zdnet
- Business Insider

### Research
- arXiv (AI, ML, NLP)
- MIT Tech Review
- Papers with Code

### Company Blogs
- OpenAI
- Anthropic
- Google AI / DeepMind
- Microsoft AI
- Meta AI
- HuggingFace
- Mistral
- Cohere
- Stability AI
- NVIDIA

### Engineering
- GitHub Blog
- AWS ML
- Azure AI
- Google Cloud

---

## 💡 Tips & Tricks

### Only Get News for Your Role
Add GitHub secret:
```
ROLE_FILTER = Developer
```
(or: "AI Engineer", "Architect", etc.)

### Add Custom News Source
Edit `fetch_news.py` → `RSS_FEEDS` list → add your RSS URL → push

### Change Stories Per Email
Edit `send_digest.py` → `collect_digest(max_per_category=8)` → push

### Adjust Lookback Period
Edit `fetch_news.py` → `LOOKBACK_HOURS = 26` → push

### Manual Test
```bash
python send_digest.py
```

---

## ✅ Verification Checklist

- [ ] Code pushed to GitHub
- [ ] GitHub secrets added (3 required)
- [ ] Test run successful (received email)
- [ ] PDF has cover page
- [ ] PDF has table of contents
- [ ] PDF has top 3 stories
- [ ] Email looks good
- [ ] Stories are categorized correctly
- [ ] Ready for 9 AM daily emails!

---

## ❓ Common Questions

**Q: Will I get duplicate emails?**
A: No, the system deduplicates automatically.

**Q: Can I change the time?**
A: Yes, edit `.github/workflows/daily.yml` cron line.

**Q: What if there's no news?**
A: You'll get "Quiet AI day — nothing major today" message.

**Q: How many emails will I get?**
A: 1 per day at 9 AM.

**Q: Can I get news for only certain roles?**
A: Yes, add `ROLE_FILTER` secret with your role(s).

**Q: Can I add my own news source?**
A: Yes, add RSS URL to `fetch_news.py` → push.

**Q: Is there a cost?**
A: Free! GitHub Actions + Gmail = no cost.

---

## 🎉 Next Steps

1. **Push code** to GitHub
2. **Add secrets** (GMAIL_USER, GMAIL_APP_PASSWORD, TO_EMAIL)
3. **Test** via GitHub Actions
4. **Receive** email with beautiful PDF in 1 minute

**Then**: Enjoy daily AI news at 9 AM! 🚀

---

**📚 Full Documentation:**
- `SETUP_GUIDE.md` - Complete step-by-step setup
- `NEXT_STEPS.md` - Detailed action items
- `IMPROVEMENTS.md` - All enhancements explained
- `README.md` - Full features & customization

**You're ready! 🎊**
