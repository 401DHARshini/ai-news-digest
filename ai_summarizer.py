"""
Free, multi-model AI enrichment for the news digest.

Rewrites each story's summary into a clear 2-3 sentence explainer (and suggests
role tags) using FREE LLMs. It tries a fallback CHAIN of models across several
providers until one succeeds — so if a model is busy, rate-limited, or retired,
the next one takes over. If no API key is set, or every model fails, the caller
silently falls back to the keyword/extractive logic in fetch_news.py.

Add ONE OR MORE of these as env vars / GitHub Actions secrets (all free tiers):
  GROQ_API_KEY        https://console.groq.com/keys       (recommended - fast + reliable)
  OPENROUTER_API_KEY  https://openrouter.ai/keys          (lots of ":free" models)
  HF_TOKEN            https://huggingface.co/settings/tokens
"""

import os
import re
import json
import requests

GROQ_KEY       = os.environ.get("GROQ_API_KEY", "").strip()
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
HF_TOKEN       = os.environ.get("HF_TOKEN", "").strip()
NVIDIA_KEY     = os.environ.get("NVIDIA_API_KEY", "").strip()

# OpenAI-compatible chat endpoints for each provider.
PROVIDERS = {
    "nvidia":     {"url": "https://integrate.api.nvidia.com/v1/chat/completions", "key": NVIDIA_KEY},
    "groq":       {"url": "https://api.groq.com/openai/v1/chat/completions",   "key": GROQ_KEY},
    "openrouter": {"url": "https://openrouter.ai/api/v1/chat/completions",     "key": OPENROUTER_KEY},
    "hf":         {"url": "https://router.huggingface.co/v1/chat/completions", "key": HF_TOKEN},
}

# Tried top-to-bottom; first success wins. Entries whose provider has no key are
# skipped, so you can enable as few or as many providers as you like. If a model
# is decommissioned or rate-limited, the request fails and the next one is tried.
MODEL_CHAIN = [
    ("nvidia",     "nvidia/nvidia-nemotron-nano-9b-v2"),
    ("nvidia",     "nvidia/llama-3.3-nemotron-super-49b-v1.5"),
    ("groq",       "llama-3.3-70b-versatile"),
    ("groq",       "llama-3.1-8b-instant"),
    ("groq",       "gemma2-9b-it"),
    ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
    ("openrouter", "google/gemma-2-9b-it:free"),
    ("openrouter", "mistralai/mistral-7b-instruct:free"),
    ("openrouter", "meta-llama/llama-3.1-8b-instruct:free"),
    ("hf",         "meta-llama/Llama-3.3-70B-Instruct"),
    ("hf",         "mistralai/Mistral-7B-Instruct-v0.3"),
]

AI_ENABLED = bool(NVIDIA_KEY or GROQ_KEY or OPENROUTER_KEY or HF_TOKEN)

# Model returns short keys; map them back to the digest's canonical labels.
CATEGORY_MAP = {
    "model_updates": "🤖 Model Updates",
    "new_launch":    "🚀 New Launch / Feature",
    "research":      "🔬 R&D / Research",
    "good_news":     "✅ Good News / Wins",
    "bad_news":      "⚠️ Bad News / Risk",
    "awareness":     "💡 AI Awareness / Must Know",
    "general":       "📰 General AI Update",
}
ROLE_MAP = {
    "developer":   "👨‍💻 Developer",
    "tester":      "🧪 Tester / QA",
    "ai_engineer": "🧠 AI Engineer / ML Engineer",
    "architect":   "🏗️ Architect / Tech Lead",
    "product":     "📈 Product / Business",
    "everyone":    "🌍 AI Awareness (Everyone)",
}

SYSTEM_PROMPT = (
    "You are the witty editor of a beloved morning AI newsletter — think a smart "
    "friend explaining the news over coffee. Given a headline and description, "
    "reply with ONLY a JSON object (no markdown, no commentary) with exactly these keys:\n"
    '  "summary": 2-3 conversational sentences. Open with the hook (the thing that '
    "makes this interesting), then what actually happened and why the reader should "
    "care. Plain words, light playfulness, zero snark at the expense of facts. "
    "Banned: 'game-changer', 'revolutionary', 'groundbreaking', 'in the world of', "
    "starting with 'In a'. Numbers and names beat adjectives.\n"
    '  "category": exactly one of '
    '["model_updates","new_launch","research","good_news","bad_news","awareness","general"].\n'
    '  "roles": an array of 1-3 from '
    '["developer","tester","ai_engineer","architect","product","everyone"] - who should care.\n'
    "Output must be valid JSON."
)


def _call(provider: str, model: str, title: str, desc: str) -> str | None:
    cfg = PROVIDERS[provider]
    headers = {"Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json"}
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/401DHARshini/ai-news-digest"
        headers["X-Title"] = "AI News Digest"

    # NVIDIA Nemotron models are reasoning models: by default they burn the token
    # budget on a <think> pass and leave `content` empty. "detailed thinking off"
    # switches them to a direct answer so we get clean JSON in one short response.
    system_prompt = SYSTEM_PROMPT
    if provider == "nvidia" and "nemotron" in model.lower():
        system_prompt = "detailed thinking off\n" + SYSTEM_PROMPT

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Headline: {title}\nDescription: {desc[:700]}"},
        ],
        "temperature": 0.3,
        "max_tokens": 512,
    }
    if provider == "groq":
        payload["response_format"] = {"type": "json_object"}
    resp = requests.post(cfg["url"], headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"].get("content")


def _parse(content: str) -> dict | None:
    if not content:
        return None
    raw = re.sub(r"```(?:json)?", "", content).strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    summary = str(obj.get("summary", "")).strip()
    if not summary:
        return None
    category = CATEGORY_MAP.get(str(obj.get("category", "")).strip().lower(), "📰 General AI Update")
    roles_in = obj.get("roles", [])
    if not isinstance(roles_in, list):
        roles_in = [roles_in]
    roles = [ROLE_MAP[r.strip().lower()] for r in roles_in
             if isinstance(r, str) and r.strip().lower() in ROLE_MAP]
    return {
        "summary": summary[:400],
        "category": category,
        "roles": roles or ["🌍 AI Awareness (Everyone)"],
    }


def ai_enrich(title: str, raw_summary: str) -> dict | None:
    """Try each free model in turn; return {summary, category, roles} or None."""
    if not AI_ENABLED:
        return None
    for provider, model in MODEL_CHAIN:
        if not PROVIDERS[provider]["key"]:
            continue
        try:
            result = _parse(_call(provider, model, title, raw_summary or title))
            if result:
                return result
        except Exception as e:
            print(f"[ai] {provider}:{model} -> {type(e).__name__}: {str(e)[:120]}")
    return None


if __name__ == "__main__":
    active = [p for p, c in PROVIDERS.items() if c["key"]]
    print(f"AI enabled: {AI_ENABLED} | active providers: {active or 'none'}")
    if AI_ENABLED:
        demo = ai_enrich(
            "OpenAI launches GPT-5 with real-time voice and vision",
            "OpenAI released GPT-5, its most capable model yet, featuring real-time "
            "voice, vision, and an agentic mode that can browse the web and run code.",
        )
        print(json.dumps(demo, ensure_ascii=False, indent=2) if demo else "all models failed")
    else:
        print("Set GROQ_API_KEY (or OPENROUTER_API_KEY / HF_TOKEN) to test.")
