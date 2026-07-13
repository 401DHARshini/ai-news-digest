"""
Fetches recent AI-related news from RSS feeds + NewsAPI, dedupes,
categorizes (New Tech / R&D / Good News / Bad News), and trims each
item down to one crisp "explain it to a friend before the exam" line.
"""

import os
import re
import html
import feedparser
import requests
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

RSS_FEEDS = [
    # ── Tech News ──────────────────────────────────────────────────
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
    "https://www.artificialintelligence-news.com/feed/",
    "https://www.wired.com/feed/tag/artificial-intelligence/rss",
    "https://thenextweb.com/neural/feed/",
    "https://www.zdnet.com/topic/artificial-intelligence/rss.xml",
    "https://www.businessinsider.com/sai/feed",

    # ── Research / Papers ──────────────────────────────────────────
    "https://arxiv.org/rss/cs.AI",
    "https://arxiv.org/rss/cs.LG",       # machine learning
    "https://arxiv.org/rss/cs.CL",       # NLP / LLMs
    "https://www.technologyreview.com/feed/",
    "https://paperswithcode.com/latest.rss",

    # ── Company Blogs (model launches live here) ───────────────────
    "https://openai.com/blog/rss.xml",
    "https://www.anthropic.com/rss.xml",
    "https://blog.google/technology/ai/rss/",
    "https://ai.googleblog.com/feeds/posts/default",
    "https://deepmind.google/blog/rss.xml",
    "https://huggingface.co/blog/feed.xml",          # model releases
    "https://mistral.ai/feed.rss",
    "https://blogs.microsoft.com/ai/feed/",
    "https://ai.meta.com/blog/rss/",
    "https://stability.ai/news/rss.xml",
    "https://cohere.com/blog/rss",
    "https://www.nvidia.com/en-us/about-nvidia/blogs/feed/",

    # ── Developer / Engineering Focus ──────────────────────────────
    "https://github.blog/category/ai-ml/feed/",
    "https://aws.amazon.com/blogs/machine-learning/feed/",
    "https://azure.microsoft.com/en-us/blog/tag/ai/feed/",
    "https://cloud.google.com/blog/products/ai-machine-learning/rss",

    # ── Cloud / Data / Platform AI ─────────────────────────────────
    "https://www.databricks.com/blog/feed",
    "https://www.snowflake.com/en/blog/feed/",
    "https://aws.amazon.com/blogs/big-data/feed/",
    "https://developer.nvidia.com/blog/feed/",
    "https://blog.langchain.dev/rss/",
    "https://www.pinecone.io/learn/rss.xml",
]

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "")  # optional, free tier key
NEWSAPI_URL = "https://newsapi.org/v2/everything"

AI_KEYWORDS = [
    "artificial intelligence", " ai ", "ai ", "machine learning", "llm",
    "large language model", "neural network", "openai", "anthropic",
    "claude", "chatgpt", "gemini", "deepmind", "generative ai",
    "agentic", "transformer model", "foundation model",
]

LOOKBACK_HOURS = 26  # slightly over 24h so a daily cron never misses items

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
        "developer tool", "function calling", "mcp ", "model context protocol",
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
    """Strip HTML tags / entities, collapse whitespace."""
    text = re.sub(r"<[^>]+>", "", raw or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


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


def extract_image(entry) -> str:
    """Best-effort thumbnail URL from an RSS entry (media tags, enclosure, inline img)."""
    for key in ("media_thumbnail", "media_content"):
        for m in (entry.get(key) or []):
            url = (m or {}).get("url")
            if url:
                return url
    for link in (entry.get("links") or []):
        if str(link.get("type", "")).startswith("image") and link.get("href"):
            return link["href"]
    blob = ""
    if entry.get("content"):
        try:
            blob = entry["content"][0].get("value", "")
        except Exception:
            blob = ""
    blob = blob or entry.get("summary", "") or entry.get("description", "")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', blob, re.IGNORECASE)
    return m.group(1) if m else ""


def is_ai_related(text: str) -> bool:
    t = f" {text.lower()} "
    return any(kw in t for kw in AI_KEYWORDS)


def within_lookback(published_struct) -> bool:
    if not published_struct:
        return True  # keep items with no date rather than drop them
    pub_dt = datetime(*published_struct[:6], tzinfo=timezone.utc)
    return pub_dt > datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)


# ---------------------------------------------------------------------
# 4. FETCHERS
# ---------------------------------------------------------------------

def fetch_rss_items():
    items = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            source_name = feed.feed.get("title", feed_url)
            for entry in feed.entries[:25]:
                title = clean_text(entry.get("title", ""))
                summary = clean_text(entry.get("summary", entry.get("description", "")))
                link = entry.get("link", "")
                published_struct = entry.get("published_parsed") or entry.get("updated_parsed")

                if not within_lookback(published_struct):
                    continue
                if "arxiv" not in feed_url and not is_ai_related(f"{title} {summary}"):
                    continue
                if not title or not link:
                    continue

                combined = f"{title} {summary}"
                items.append({
                    "title": title,
                    "summary": crisp_summary(title, summary),
                    "link": link,
                    "source": source_name,
                    "image": extract_image(entry),
                    "category": categorize(combined),
                    "roles": tag_roles(combined),
                    "ai_powered": False,
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
            })
    except Exception as e:
        print(f"[warn] NewsAPI fetch failed: {e}")
    return items


def dedupe(items):
    seen = set()
    unique = []
    for it in items:
        key = re.sub(r"\W+", "", it["title"].lower())[:60]
        if key in seen:
            continue
        seen.add(key)
        unique.append(it)
    return unique


# ---------------------------------------------------------------------
# 5. MAIN COLLECT FUNCTION
# ---------------------------------------------------------------------

def enrich_digest(digest: dict) -> None:
    """Rewrite each final story's summary (and role tags) with a free LLM, in place.

    Runs only on the trimmed final set — roughly one API call per shown story —
    so it stays well inside free-tier limits instead of calling the model for
    every fetched item. Any story the model can't handle keeps its keyword summary.
    """
    total = sum(len(v) for v in digest.values())
    powered = 0
    for items in digest.values():
        for it in items:
            if it.get("tracked"):
                continue
            res = ai_enrich(it["title"], it.get("summary", ""))
            if res:
                it["summary"] = res["summary"]
                if res.get("roles"):
                    it["roles"] = res["roles"]
                it["ai_powered"] = True
                powered += 1
    print(f"[ai] enriched {powered}/{total} stories with an LLM summary")


def collect_digest(max_per_category: int = 5):
    tracker_items = []
    try:
        from model_tracker import new_model_items
        tracker_items = new_model_items()[:3]   # keep state; show at most 3 so real news isn't crowded out
    except Exception as e:
        print(f"[tracker] skipped: {e}")

    all_items = tracker_items + fetch_rss_items() + fetch_newsapi_items()
    all_items = dedupe(all_items)

    grouped = {}
    for it in all_items:
        grouped.setdefault(it["category"], []).append(it)

    # category display order — model updates first, awareness last
    order = [
        "🤖 Model Updates",
        "☁️ Cloud AI",
        "🗄️ Data & Databricks",
        "🛠️ Dev Tools & Agents",
        "🧪 Testing & Evals",
        "🚀 New Launch / Feature",
        "🔬 R&D / Research",
        "✅ Good News / Wins",
        "⚠️ Bad News / Risk",
        "💡 AI Awareness / Must Know",
        "📰 General AI Update",
    ]
    final = {}
    for cat in order:
        if cat in grouped:
            final[cat] = grouped[cat][:max_per_category]

    if AI_ENABLED:
        print("Enriching summaries with AI (free multi-model fallback)...")
        enrich_digest(final)

    return final


if __name__ == "__main__":
    digest = collect_digest()
    for cat, items in digest.items():
        print(f"\n=== {cat} ({len(items)}) ===")
        for it in items:
            print(f"- {it['title']}\n  {it['summary']}\n  for: {', '.join(it['roles'])}\n  {it['link']}")
