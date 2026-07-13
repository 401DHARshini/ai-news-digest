"""
Cross-article signal mining for the digest's "Pulse" dashboard.

Runs over EVERY article fetched today (before the per-category trim), so the
dashboard reflects the whole day's news surface, not just the stories shown:

  - models: which model families the industry is talking about most
  - topics: which themes are trending (agents, chips, funding, policy, ...)
  - stats:  scanned volume + distinct sources

Pure keyword counting — no network, no LLM, safe to run always.
"""

from collections import Counter

# Model families an AI enthusiast tracks. Fixed display order = chart order
# for ties; counts decide the ranking. Keywords are matched per-article
# (an article mentioning a family five times still counts once).
MODEL_FAMILIES = [
    ("GPT / OpenAI", ("gpt-", "gpt4", "gpt 4", "gpt5", "gpt 5", "chatgpt",
                      " o3", " o4", "openai o")),
    ("Claude",       ("claude",)),
    ("Gemini",       ("gemini",)),
    ("Llama",        ("llama",)),
    ("Mistral",      ("mistral", "mixtral", "ministral")),
    ("DeepSeek",     ("deepseek",)),
    ("Qwen",         ("qwen",)),
    ("Grok",         ("grok",)),
    ("Nemotron",     ("nemotron",)),
    ("Phi",          ("phi-3", "phi-4", "phi-5", "microsoft phi")),
]

# Themes worth a weekly pulse-check. First-listed wins display order on ties.
TOPICS = [
    ("Agents",             ("agent", "agentic")),
    ("Chips & Compute",    ("gpu", "chip", "semiconductor", "data center",
                            "datacenter", "compute", "tsmc", "nvidia")),
    ("Open Source",        ("open source", "open-source", "open weights",
                            "open model")),
    ("Funding & Deals",    ("funding", "raises", "valuation", "acquisition",
                            "acquire", "ipo", "investment", "billion")),
    ("Policy & Regulation", ("regulat", "policy", "ban ", "banned", "law",
                             "governance", "compliance", "export control")),
    ("Safety & Risk",      ("safety", "alignment", "deepfake", "misinformation",
                            "hallucinat", "jailbreak", "security flaw")),
    ("Coding & Dev Tools", ("coding", "code assistant", "copilot", "sdk",
                            "developer", "ide ", "cursor", "cli")),
    ("Robotics",           ("robot", "humanoid", "self-driving", "autonomous vehicle")),
    ("Research",           ("research", "paper", "arxiv", "study", "benchmark",
                            "breakthrough")),
    ("Enterprise AI",      ("enterprise", "adoption", "productivity",
                            "workforce", "business ai")),
]


def _count_per_article(texts, defs):
    """[(name, n_articles_mentioning)] sorted by count desc, zeros dropped."""
    counts = Counter()
    for name, kws in defs:
        n = sum(1 for t in texts if any(kw in t for kw in kws))
        if n:
            counts[name] = n
    return counts.most_common()


def mine_insights(items: list) -> dict:
    texts = [f" {it.get('title', '')} {it.get('summary', '')} ".lower()
             for it in items]
    sources = Counter(it.get("source", "unknown") for it in items)
    return {
        "scanned": len(items),
        "models": _count_per_article(texts, MODEL_FAMILIES)[:6],
        "topics": _count_per_article(texts, TOPICS)[:8],
        "sources": len(sources),
        "top_sources": sources.most_common(5),
    }


if __name__ == "__main__":
    from fetch_news import fetch_rss_items
    import json
    ins = mine_insights(fetch_rss_items())
    print(json.dumps(ins, indent=2, ensure_ascii=False))
