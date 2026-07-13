"""
Detects models NEWLY added to Groq / OpenRouter since the last run.

Each morning it pulls the two providers' model catalogs, diffs them against a
small state file (state/models.json), and returns digest items for anything new
— so you always know when a fresh Gemma / Qwen / Llama / DeepSeek etc. lands on
the free rails you actually use.

State is tiny JSON; in CI it's persisted between runs via actions/cache. On the
very first run (no prior state) nothing is flagged — it just records a baseline.
"""

import os
import json
import requests

STATE_PATH = os.environ.get("MODEL_STATE_PATH", os.path.join("state", "models.json"))


def _groq_models():
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return []
    try:
        r = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {key}"}, timeout=20,
        )
        r.raise_for_status()
        return [m.get("id") for m in r.json().get("data", []) if m.get("id")]
    except Exception as e:
        print(f"[tracker] groq models fetch failed: {e}")
        return []


def _openrouter_models():
    try:
        r = requests.get("https://openrouter.ai/api/v1/models", timeout=20)
        r.raise_for_status()
        return [m.get("id") for m in r.json().get("data", []) if m.get("id")]
    except Exception as e:
        print(f"[tracker] openrouter models fetch failed: {e}")
        return []


_LINK = {
    "Groq": "https://console.groq.com/docs/models",
    "OpenRouter": "https://openrouter.ai/models",
}


def new_model_items(state_path: str = STATE_PATH) -> list:
    """Return digest items for models added since the last run; update state."""
    current = {
        "Groq": sorted(set(_groq_models())),
        "OpenRouter": sorted(set(_openrouter_models())),
    }

    prev = {}
    try:
        with open(state_path, encoding="utf-8") as f:
            prev = json.load(f)
    except Exception:
        prev = {}

    items = []
    for provider, models in current.items():
        old = set(prev.get(provider, []))
        if not old:
            continue  # first run for this provider — set a baseline, flag nothing
        for mid in models:
            if mid in old:
                continue
            items.append({
                "title": f"New model on {provider}: {mid}",
                "summary": (f"{mid} is now available through {provider}'s API — "
                            f"a fresh option to try in the pipeline and benchmark."),
                "link": _LINK.get(provider, "#"),
                "source": f"{provider} Model Catalog",
                "image": "",
                "category": "🤖 Model Updates",
                "roles": ["🧠 AI Engineer / ML Engineer", "👨‍💻 Developer"],
                "ai_powered": False,
                "tracked": True,
            })

    # only overwrite state when we actually fetched something (avoid wiping the
    # baseline on a transient network failure)
    if any(current.values()):
        try:
            os.makedirs(os.path.dirname(state_path) or ".", exist_ok=True)
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(current, f, indent=0)
        except Exception as e:
            print(f"[tracker] could not save state: {e}")

    if items:
        print(f"[tracker] {len(items)} newly-added model(s) detected")
    return items


if __name__ == "__main__":
    for it in new_model_items():
        print("-", it["title"])
