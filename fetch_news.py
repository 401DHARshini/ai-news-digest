"""
Fetches recent AI-related news from RSS feeds + NewsAPI, dedupes,
categorizes (New Tech / R&D / Good News / Bad News), and trims each
item down to one crisp "explain it to a friend before the exam" line.
"""

import os
import re
import html
import time
import calendar
import socket
import feedparser
import requests

# feedparser has no timeout of its own; one hung feed must not stall the run.
socket.setdefaulttimeout(20)
# Some publishers (e.g. blogs.oracle.com) reject feedparser's default agent.
feedparser.USER_AGENT = "Mozilla/5.0 ai-news-digest"
from datetime import datetime, timedelta, timezone

# AI enrichment via HuggingFace (used only when HF_TOKEN is set)
try:
    from ai_summarizer import ai_enrich, AI_ENABLED
except ImportError:
    AI_ENABLED = False
    def ai_enrich(*a, **kw): return None  # noqa: E302

# ---------------------------------------------------------------------
# 1. SOURCES
# ---------------------------------------------------------------------

# Google News search feeds catch announcements from ANY company (Zoho, Cloudflare,
# Oracle, ...) even when that company has no RSS feed of its own.
def _gnews(query: str) -> str:
    from urllib.parse import quote_plus
    return ("https://news.google.com/rss/search?q=" + quote_plus(query)
            + "&hl=en-US&gl=US&ceid=US:en")


RSS_FEEDS = [
    # ── Tech News ──────────────────────────────────────────────────
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://www.wired.com/feed/tag/ai/latest/rss",
    "https://www.zdnet.com/topic/artificial-intelligence/rss.xml",
    "https://www.technologyreview.com/feed/",

    # ── Research / Papers ──────────────────────────────────────────
    "https://arxiv.org/rss/cs.AI",
    "https://arxiv.org/rss/cs.LG",       # machine learning
    "https://arxiv.org/rss/cs.CL",       # NLP / LLMs

    # ── AI Labs (model launches live here) ─────────────────────────
    "https://openai.com/news/rss.xml",
    "https://blog.google/technology/ai/rss/",
    "https://deepmind.google/blog/rss.xml",
    "https://huggingface.co/blog/feed.xml",
    "https://developers.googleblog.com/feeds/posts/default",

    # ── Big Tech / Enterprise platforms ────────────────────────────
    "https://www.microsoft.com/en-us/microsoft-365/blog/feed/",   # Copilot, Work IQ
    "https://devblogs.microsoft.com/foundry/feed/",               # Azure AI Foundry, agents
    "https://azure.microsoft.com/en-us/blog/tag/ai/feed/",
    "https://blog.cloudflare.com/rss/",                           # Workers AI, MCP, Code Mode
    "https://blogs.oracle.com/ai-and-datascience/rss",
    "https://blogs.oracle.com/cloud-infrastructure/rss",
    "https://blogs.oracle.com/database/rss",
    "https://www.salesforce.com/news/feed/",                      # Agentforce
    "https://blog.zoho.com/feed",                                 # Zia, Zoho AI
    "https://blogs.nvidia.com/feed/",
    "https://developer.nvidia.com/blog/feed/",

    # ── Developer / Engineering Focus ──────────────────────────────
    "https://github.blog/feed/",
    "https://aws.amazon.com/blogs/machine-learning/feed/",
    "https://cloudblog.withgoogle.com/products/ai-machine-learning/rss/",
    "https://www.linuxfoundation.org/blog/rss.xml",               # A2A, MCP, AAIF
    "https://simonwillison.net/atom/everything/",                 # sharp daily AI-dev notes
    "https://www.latent.space/feed",                              # AI engineering deep dives

    # ── Cloud / Data / Platform AI ─────────────────────────────────
    "https://www.databricks.com/feed",
    "https://www.snowflake.com/feed/",
    "https://aws.amazon.com/blogs/big-data/feed/",

    # ── Industry-wide catch-all (Google News search) ───────────────
    # Kept last so a company's own blog post wins de-duplication.
    _gnews('Anthropic OR Claude when:2d'),
    _gnews('OpenAI OR ChatGPT when:2d'),
    _gnews('"MCP" OR "Model Context Protocol" OR "A2A" OR "agent-to-agent" when:3d'),
    _gnews('"AI agents" OR "agentic AI" when:2d'),
    _gnews('(Microsoft Copilot OR "Work IQ" OR Google Gemini OR AWS Bedrock) when:2d'),
    _gnews('(Cloudflare OR Oracle OR Zoho OR Salesforce OR ServiceNow OR SAP) AI when:2d'),
]

# ---------------------------------------------------------------------
# 1b. EDITORIAL PRIORITY — what an IT leader AND a junior engineer need
# ---------------------------------------------------------------------
# Companies / topics that move the industry. Stories naming one rank higher,
# and Google News stories MUST name one (keeps out tiny-startup press releases).
WATCHLIST = [
    "openai", "chatgpt", "anthropic", "claude", "google", "gemini", "deepmind",
    "microsoft", "copilot", "azure", "work iq", "aws", "amazon", "bedrock",
    "meta", "llama", "nvidia", "apple", "oracle", "cloudflare", "salesforce",
    "agentforce", "zoho", "servicenow", "sap", "ibm", "databricks", "snowflake",
    "github", "hugging face", "mistral", "deepseek", "qwen", "xai", "grok",
    "mcp", "model context protocol", "a2a", "agent2agent", "linux foundation",
]
WATCH_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in WATCHLIST) + r")\b", re.I)

# Established tech/business press — trusted reporting outranks aggregators.
TOP_PRESS = [
    "techcrunch", "the verge", "wired", "technology review", "zdnet", "venturebeat",
    "reuters", "bloomberg", "the information", "cnbc", "financial times", "wsj",
    "wall street journal", "axios", "ars technica", "the register", "infoworld",
    "computerworld", "geekwire", "siliconangle", "new york times", "the economist",
]

# Paid press-release wires and low-signal aggregators: dropped from Google News.
LOW_VALUE_SOURCES = [
    "ein news", "ein presswire", "einpresswire", "pr newswire", "prnewswire", "globenewswire",
    "business wire", "accesswire", "openpr", "newsfile", "citybiz", "cointribune",
    "biggo", "startup fortune",
    # stock-picking / investor sites: market chatter, not technology news
    "motley fool", "fool.com", "seeking alpha", "benzinga", "zacks", "investorplace",
    "marketbeat", "investing.com", "simply wall", "tipranks", "insidermonkey", "insider monkey",
]

# Share-price chatter ("XYZ stock holds $242 ...") — not technology news.
STOCK_RE = re.compile(r"\b(stock|shares|price target)\b.*\$|\$\d.*\b(stock|shares)\b", re.I)

MAX_PER_COMPANY = 3  # stops one hot topic (e.g. an IPO) filling the whole email
MAX_PER_SOURCE = 3    # stops one prolific blog filling the whole email

ARXIV_MAX = 2   # research papers per digest — enough for the curious, not a flood


def importance(it: dict) -> int:
    """Editorial score: official/trusted sources and industry-moving names first."""
    origin = it.get("origin", "")
    src = (it.get("source") or "").lower()
    score = {"arxiv": 0, "gnews": 1, "feed": 2}.get(origin, 1)
    if it.get("tracked"):
        score += 3
    if any(p in src for p in TOP_PRESS):
        score += 1
    if origin != "arxiv" and WATCH_RE.search(it.get("title", "")):
        score += 2
    return score


NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "")  # optional, free tier key
NEWSAPI_URL = "https://newsapi.org/v2/everything"

AI_KEYWORDS = [
    "artificial intelligence", " ai ", "ai ", "machine learning", "llm",
    "large language model", "neural network", "openai", "anthropic",
    "claude", "chatgpt", "gemini", "deepmind", "generative ai",
    "agentic", "transformer model", "foundation model",
    # agent / protocol / platform terms that often appear without the word "AI"
    "mcp", "model context protocol", "a2a", "agent2agent", "agent-to-agent",
    "ai agent", "agents", "copilot", "work iq", "code mode", "agentforce",
    "workers ai", "inference", "gpt", "llama", "rag ", "vector search",
]

LOOKBACK_HOURS = 26  # slightly over 24h so a daily cron never misses items
INSIGHT_LOOKBACK_HOURS = 168  # the Pulse dashboard mines a trailing week of articles

# ---------------------------------------------------------------------
# 2. CATEGORY KEYWORD RULES
# ---------------------------------------------------------------------

CATEGORY_RULES = {
    "☁️ Cloud AI": [
        "azure ai", "azure openai", "ai foundry", "aws bedrock", "amazon bedrock",
        "sagemaker", "vertex ai", "google vertex", "watsonx", "bedrock", "vertex",
        "azure machine learning", "google cloud ai", "oracle ai", "cloud ai platform",
    ],
    "🗄️ Data & Databricks": [
        "databricks", "snowflake", "lakehouse", "mosaic ai", "unity catalog",
        "delta lake", "vector database", "vector db", "pinecone", "weaviate",
        "qdrant", "chroma", "milvus", "feature store", "mlflow", "dbt ",
        "data warehouse", "data pipeline", "data engineering", "retrieval augmented",
    ],
    "🧪 Testing & Evals": [
        "benchmark", "eval ", "evals", "evaluation", "leaderboard", "red team",
        "red-team", "swe-bench", "mmlu", "hallucination", "guardrail", "robustness",
        "adversarial", "regression test", "test coverage", "qa automation",
        "software testing", "model evaluation", "reliability testing", "safety testing",
    ],
    "🛠️ Dev Tools & Agents": [
        "sdk", "coding assistant", "code assistant", "copilot", "github copilot",
        "cursor", "windsurf", "devin", "agent framework", "agentic framework",
        "langchain", "llamaindex", "llama index", "autogen", "crewai", "cli tool",
        "developer tool", "function calling", "mcp ", "mcp)", "mcp,", "mcp server",
        "model context protocol", "a2a", "agent2agent", "agent-to-agent",
        "ai agent", "code mode", "work iq", "agentforce", "agents sdk", "workers ai",
        "open source library", "new api", "new sdk", "plugin", "ide ",
    ],
    "🤖 Model Updates": [
        "gpt-", "gpt4", "gpt5", "claude 3", "claude 4", "gemini 2", "gemini ultra",
        "llama 3", "llama 4", "mistral ", "phi-", "phi ", "qwen", "deepseek",
        "falcon ", "command r", "grok-", "grok ", "o1 ", "o3 ", "o4 ",
        "new model", "model release", "model update", "model version",
        "foundation model", "multimodal model", "vision model", "reasoning model",
        "weights released", "model weights", "context window",
    ],
    "🔬 R&D / Research": [
        "research", "paper", "study", "arxiv", "breakthrough", "model trained",
        "benchmark", "novel architecture", "preprint", "scientists", "lab",
        "experiment", "dataset released", "evaluating", "outperforms",
    ],
    "🚀 New Launch / Feature": [
        "launch", "released", "unveils", "announces", "introducing",
        "now available", "rolls out", "debuts", "ships", "available today",
        "new feature", "new tool", "new api", "new plugin", "update to",
    ],
    "⚠️ Bad News / Risk": [
        "lawsuit", "ban", "fired", "layoff", "controversy", "backlash",
        "security flaw", "vulnerability", "misinformation", "deepfake scam",
        "data breach", "shut down", "fraud", "outage", "criticized", "fine",
        "regulat", "investigation", "hallucin", "bias", "safety concern",
    ],
    "✅ Good News / Wins": [
        "funding", "raises", "valuation", "partnership", "milestone",
        "record", "approve", "wins", "success", "boosts", "improves",
        "cures", "saves", "open source", "free for", "open weights",
    ],
    "💡 AI Awareness / Must Know": [
        "what is", "how ai", "explained", "understand", "future of ai",
        "ai will", "impact of ai", "ai ethics", "ai policy", "ai regulation",
        "ai safety", "alignment", "existential", "jobs", "economy", "society",
        "ai adoption", "ai strategy", "enterprise ai", "ai trends",
    ],
}

DEFAULT_CATEGORY = "📰 General AI Update"


def categorize(text: str) -> str:
    t = text.lower()
    for category, kws in CATEGORY_RULES.items():
        if any(kw in t for kw in kws):
            return category
    return DEFAULT_CATEGORY


# ---------------------------------------------------------------------
# 2b. ROLE RELEVANCE RULES — "who actually cares about this"
# ---------------------------------------------------------------------
# An item can map to more than one role. Order = display priority.

ROLE_RULES = {
    "👨‍💻 Developer": [
        "sdk", "api", "library", "framework", "open source", "github",
        "code", "coding assistant", "copilot", "ide", "plugin", "cli",
        "integration", "developer", "npm", "pip install", "repo",
        "function calling", "tool use", "webhook", "rest api", "graphql",
        "langchain", "llamaindex", "openai sdk", "anthropic sdk",
    ],
    "🧪 Tester / QA": [
        "test", "testing", "qa", "quality assurance", "bug", "automation testing",
        "regression", "test coverage", "self-healing test", "ci/cd", "reliability",
        "hallucination", "evaluation", "eval", "benchmark", "accuracy",
        "red team", "safety testing", "adversarial", "robustness",
    ],
    "🧠 AI Engineer / ML Engineer": [
        "model", "training", "fine-tun", "inference", "dataset", "embedding",
        "rag", "retrieval", "vector", "gpu", "llm", "neural network", "transformer",
        "weights", "parameters", "agent", "agentic", "prompt engineering", "mlops",
        "quantization", "distillation", "lora", "rlhf", "pretraining",
        "context window", "tokenizer", "multimodal", "vision language",
        "reasoning", "chain of thought", "tool use", "function calling",
    ],
    "🏗️ Architect / Tech Lead": [
        "architecture", "scalab", "infrastructure", "enterprise", "deploy",
        "platform", "system design", "cost", "pricing", "compliance", "security",
        "governance", "on-prem", "cloud", "migration", "integration strategy",
        "latency", "throughput", "rate limit", "sla", "multi-tenant",
        "observability", "monitoring", "production", "at scale",
    ],
    "📈 Product / Business": [
        "funding", "valuation", "revenue", "acquisition", "partnership",
        "market", "customers", "enterprise deal", "ipo", "ceo", "strategy",
        "roi", "adoption", "billion", "million", "startup", "investor",
    ],
    "🌍 AI Awareness (Everyone)": [
        "what is", "explained", "future of", "impact", "society", "jobs",
        "regulation", "policy", "ethics", "safety", "alignment", "risk",
        "awareness", "trends", "2025", "2026",
    ],
}


def tag_roles(text: str) -> list:
    t = text.lower()
    roles = [role for role, kws in ROLE_RULES.items() if any(kw in t for kw in kws)]
    return roles or ["🌍 General Awareness"]


# ---------------------------------------------------------------------
# 3. HELPERS
# ---------------------------------------------------------------------

def clean_text(raw: str) -> str:
    """Strip HTML tags / entities, collapse whitespace, remove arXiv boilerplate."""
    text = re.sub(r"<[^>]+>", "", raw or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    # Strip arXiv raw prefix: "arXiv:2607.12345v1 Announce Type: new Abstract:"
    text = re.sub(r"^arXiv:\S+\s+Announce Type:\s*\S+\s+Abstract:\s*", "", text, flags=re.IGNORECASE)
    # Also strip just "Abstract:" if it starts with it
    text = re.sub(r"^Abstract:\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def crisp_summary(title: str, summary: str, max_chars: int = 340) -> str:
    """A fuller, self-contained summary that keeps context and ends cleanly.

    Uses the article description (falling back to the title), strips common
    RSS boilerplate, and cuts on a sentence boundary instead of mid-word so
    the reader gets the what / who / where without a dangling fragment.
    """
    base = clean_text(summary)
    # Drop trailing RSS boilerplate like "Read more" / "The post … appeared first on …"
    base = re.sub(
        r"\s*(read more.*|continue reading.*|the post .*? appeared first on .*)$",
        "", base, flags=re.IGNORECASE,
    ).strip()
    if len(base) < 45:                       # too thin to be useful → use the title
        base = clean_text(title)
    if len(base) <= max_chars:
        return base
    window = base[:max_chars]
    # Prefer to end at the last full sentence within the limit
    end = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))
    if end >= 140:
        return window[:end + 1].strip()
    return window.rsplit(" ", 1)[0].strip() + "…"


# Promo/ad assets that sneak into RSS bodies — never use them as story art.
_AD_IMAGE_RE = re.compile(r"banner|sponsor|advert|promo|expo|badge|logo|avatar|gravatar",
                          re.IGNORECASE)


def extract_image(entry) -> str:
    """Best-effort thumbnail URL from an RSS entry (media tags, enclosure, inline img)."""
    def ok(url):
        return url and not _AD_IMAGE_RE.search(url)

    for key in ("media_thumbnail", "media_content"):
        for m in (entry.get(key) or []):
            url = (m or {}).get("url")
            if ok(url):
                return url
    for link in (entry.get("links") or []):
        if str(link.get("type", "")).startswith("image") and ok(link.get("href")):
            return link["href"]
    blob = ""
    if entry.get("content"):
        try:
            blob = entry["content"][0].get("value", "")
        except Exception:
            blob = ""
    blob = blob or entry.get("summary", "") or entry.get("description", "")
    for m in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', blob, re.IGNORECASE):
        if ok(m.group(1)):
            return m.group(1)
    return ""


def is_ai_related(text: str) -> bool:
    t = f" {text.lower()} "
    return any(kw in t for kw in AI_KEYWORDS)


def within_lookback(published_struct, hours: int = LOOKBACK_HOURS) -> bool:
    if not published_struct:
        return True  # keep items with no date rather than drop them
    pub_dt = datetime(*published_struct[:6], tzinfo=timezone.utc)
    return pub_dt > datetime.now(timezone.utc) - timedelta(hours=hours)


# ---------------------------------------------------------------------
# 4. FETCHERS
# ---------------------------------------------------------------------

def fetch_rss_items():
    items = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            source_name = feed.feed.get("title", feed_url)
            is_gnews = "news.google.com" in feed_url
            is_arxiv = "arxiv" in feed_url
            if not feed.entries:
                print(f"[warn] no entries from {feed_url}")
            for entry in feed.entries[:25]:
                title = clean_text(entry.get("title", ""))
                item_source = source_name
                if is_gnews:
                    # Google News titles look like "Headline - Publisher"
                    item_source = (entry.get("source") or {}).get("title") or "Google News"
                    if title.endswith(" - " + item_source):
                        title = title[: -len(" - " + item_source)].strip()
                    if (not WATCH_RE.search(title)
                            or any(b in item_source.lower() for b in LOW_VALUE_SOURCES)
                            or STOCK_RE.search(title)):
                        continue
                summary = clean_text(entry.get("summary", entry.get("description", "")))
                link = entry.get("link", "")
                published_struct = entry.get("published_parsed") or entry.get("updated_parsed")

                # Keep a trailing week for trend mining; only items inside the
                # daily window ("fresh") are eligible for the digest itself.
                if not within_lookback(published_struct, INSIGHT_LOOKBACK_HOURS):
                    continue
                if not is_arxiv and not is_ai_related(f"{title} {summary}"):
                    continue
                if not title or not link:
                    continue

                combined = f"{title} {summary}"
                items.append({
                    "title": title,
                    "summary": crisp_summary(title, summary),
                    "link": link,
                    "source": item_source,
                    "image": extract_image(entry),
                    # Papers always live in Research so they never crowd out industry news.
                    "category": "🔬 R&D / Research" if is_arxiv else categorize(combined),
                    "origin": "arxiv" if is_arxiv else ("gnews" if is_gnews else "feed"),
                    "roles": tag_roles(combined),
                    "ai_powered": False,
                    "fresh": within_lookback(published_struct),
                    "ts": calendar.timegm(published_struct) if published_struct else None,
                })
        except Exception as e:
            print(f"[warn] failed to parse {feed_url}: {e}")
    return items


def fetch_newsapi_items():
    if not NEWSAPI_KEY:
        return []
    items = []
    try:
        params = {
            "q": (
                "artificial intelligence OR \"machine learning\" OR OpenAI OR Anthropic "
                "OR Gemini OR Claude OR GPT OR LLM OR \"language model\" OR DeepMind "
                "OR Mistral OR Llama OR \"AI model\" OR \"model release\""
            ),
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 40,
            "apiKey": NEWSAPI_KEY,
        }
        resp = requests.get(NEWSAPI_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for art in data.get("articles", []):
            title = clean_text(art.get("title", ""))
            summary = clean_text(art.get("description", "") or "")
            link = art.get("url", "")
            if not title or not link:
                continue
            ts = None
            try:
                pa = art.get("publishedAt") or ""
                ts = datetime.fromisoformat(pa.replace("Z", "+00:00")).timestamp()
            except Exception:
                pass
            combined = f"{title} {summary}"
            items.append({
                "title": title,
                "summary": crisp_summary(title, summary),
                "link": link,
                "source": (art.get("source") or {}).get("name", "NewsAPI"),
                "image": art.get("urlToImage") or "",
                "category": categorize(combined),
                "roles": tag_roles(combined),
                "ai_powered": False,
                "ts": ts,
            })
    except Exception as e:
        print(f"[warn] NewsAPI fetch failed: {e}")
    return items


_STOP = {"the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with",
         "its", "is", "at", "by", "from", "as", "new", "how", "why", "what", "s"}


def _title_words(title: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", title.lower()) if w not in _STOP}


def dedupe(items):
    """Drop repeats: same title prefix, or the same story under a reworded
    headline (most of the shorter headline's words appear in a kept one).
    First occurrence wins, and feeds are ordered so official sources come first."""
    seen = set()
    kept_words = []
    unique = []
    for it in items:
        key = re.sub(r"\W+", "", it["title"].lower())[:60]
        if key in seen:
            continue
        words = _title_words(it["title"])
        if len(words) >= 5 and any(
                len(words & kw) / min(len(words), len(kw)) >= 0.6
                for kw in kept_words if len(kw) >= 5):
            continue
        seen.add(key)
        kept_words.append(words)
        unique.append(it)
    return unique


# ---------------------------------------------------------------------
# 5. MAIN COLLECT FUNCTION
# ---------------------------------------------------------------------

AI_BUDGET_SECONDS = 240   # cap on total LLM time so a slow provider can't delay the email


def enrich_digest(digest: dict) -> None:
    """Rewrite each final story's summary (and role tags) with a free LLM, in place.

    Runs only on the trimmed final set — roughly one API call per shown story —
    so it stays well inside free-tier limits instead of calling the model for
    every fetched item. Any story the model can't handle keeps its keyword summary.
    """
    total = sum(len(v) for v in digest.values())
    powered = 0
    deadline = time.time() + AI_BUDGET_SECONDS
    for items in digest.values():
        for it in items:
            if it.get("tracked"):
                continue
            if time.time() > deadline:
                print(f"[ai] time budget ({AI_BUDGET_SECONDS}s) used up — "
                      "remaining stories keep their keyword summary")
                print(f"[ai] enriched {powered}/{total} stories with an LLM summary")
                return
            res = ai_enrich(it["title"], it.get("summary", ""))
            if res:
                it["summary"] = res["summary"]
                for key in ("hook", "details", "why"):
                    if res.get(key):
                        it[key] = res[key]
                if res.get("roles"):
                    it["roles"] = res["roles"]
                it["ai_powered"] = True
                powered += 1
    print(f"[ai] enriched {powered}/{total} stories with an LLM summary")


def collect_digest(max_per_category: int = 4, with_insights: bool = False):
    """Collect the trimmed digest; with_insights=True also returns the
    dashboard signals mined from EVERY scanned article (see insights.py),
    as a (digest, insights) tuple."""
    tracker_items = []
    try:
        from model_tracker import new_model_items
        tracker_items = new_model_items()[:3]   # keep state; show at most 3 so real news isn't crowded out
    except Exception as e:
        print(f"[tracker] skipped: {e}")

    all_items = tracker_items + fetch_rss_items() + fetch_newsapi_items()
    all_items = dedupe(all_items)

    # The digest shows only fresh (last ~26h) stories; the full trailing-week
    # set feeds the Pulse dashboard (insights) below.
    for it in tracker_items:
        it.setdefault("ts", time.time())      # tracker finds are brand new
    grouped = {}
    for it in all_items:
        if it.get("fresh", True):
            grouped.setdefault(it["category"], []).append(it)
    # Most important first inside every category (then newest), so the lead story,
    # "Today at a glance" and the email subject all carry what actually matters.
    for items in grouped.values():
        items.sort(key=lambda it: (importance(it), it.get("ts") or 0), reverse=True)

    # Display order: what changed and what to act on first, research and
    # background reading last.
    order = [
        "🤖 Model Updates",
        "🚀 New Launch / Feature",
        "🛠️ Dev Tools & Agents",
        "☁️ Cloud AI",
        "🗄️ Data & Databricks",
        "⚠️ Bad News / Risk",
        "✅ Good News / Wins",
        "🧪 Testing & Evals",
        "🔬 R&D / Research",
        "💡 AI Awareness / Must Know",
        "📰 General AI Update",
    ]
    final = {}
    arxiv_left = ARXIV_MAX
    per_company, per_source = {}, {}
    for cat in order:
        picked = []
        for it in grouped.get(cat, []):
            if len(picked) >= max_per_category:
                break
            src = (it.get("source") or "").lower()
            if it.get("origin") != "arxiv" and per_source.get(src, 0) >= MAX_PER_SOURCE:
                continue
            if it.get("origin") == "arxiv":
                if arxiv_left <= 0:
                    continue
                arxiv_left -= 1
            m = WATCH_RE.search(it.get("title", ""))
            if m:
                company = m.group(1).lower()
                if per_company.get(company, 0) >= MAX_PER_COMPANY:
                    continue
                per_company[company] = per_company.get(company, 0) + 1
            per_source[src] = per_source.get(src, 0) + 1
            picked.append(it)
        if picked:
            final[cat] = picked

    if AI_ENABLED:
        print("Enriching summaries with AI (free multi-model fallback)...")
        enrich_digest(final)

    if with_insights:
        try:
            from insights import mine_insights
            return final, mine_insights(all_items)
        except Exception as e:
            print(f"[insights] skipped: {e}")
            return final, {}
    return final


if __name__ == "__main__":
    digest = collect_digest()
    for cat, items in digest.items():
        print(f"\n=== {cat} ({len(items)}) ===")
        for it in items:
            print(f"- {it['title']}\n  {it['summary']}\n  for: {', '.join(it['roles'])}\n  {it['link']}")
