"""
AI-powered summarization, categorization, and role tagging
using the FREE HuggingFace Inference API.

Model used: mistralai/Mistral-7B-Instruct-v0.3
  - Free to use, just needs a HF token
  - Great at following tone/format instructions
  - Handles all 3 tasks in ONE prompt per article (fast + cheap on free tier)

Fallback: if HF_TOKEN is not set, the module does nothing and
fetch_news.py falls back to its original keyword-based logic.

How to get a FREE HuggingFace token:
  1. Sign up at https://huggingface.co/join  (free, no credit card)
  2. Go to https://huggingface.co/settings/tokens
  3. Create a token with "Read" permission
  4. Add it as HF_TOKEN secret in GitHub / env var locally
"""

import os
import re
import json
import requests

HF_TOKEN = os.environ.get("HF_TOKEN", "")

# Primary model — best free instruct model on HF
HF_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

# Fallback model — smaller, faster, always warm on HF
FALLBACK_MODEL = "HuggingFaceH4/zephyr-7b-beta"
FALLBACK_API_URL = f"https://api-inference.huggingface.co/models/{FALLBACK_MODEL}"


# ------------------------------------------------------------------
# PROMPT TEMPLATE
# ------------------------------------------------------------------

SYSTEM_PROMPT = """You are a sharp tech journalist summarizing AI news for busy engineers.
Your job: read a news title + description, then return ONLY a JSON object with these 3 fields:

{
  "summary": "<one punchy sentence, max 150 chars, written like you're explaining to a friend before an exam — casual, direct, no jargon>",
  "category": "<exactly one of: 🚀 New Launch | 🔬 R&D / Research | ✅ Good News / Wins | ⚠️ Bad News / Risk | 📰 General AI Update>",
  "roles": ["<role1>", "<role2>"]
}

For roles, pick ONLY from this list (can pick multiple, pick none as 🌍 General Awareness if unsure):
- 👨‍💻 Developer
- 🧪 Tester / QA
- 🧠 AI Engineer / ML Engineer
- 🏗️ Architect / Tech Lead
- 📈 Product / Business
- 🌍 General Awareness

Rules:
- summary must sound like a friend texting you, NOT a press release
- Return ONLY valid JSON, no explanation, no markdown fences
"""


def _build_prompt(title: str, description: str) -> str:
    return f"""<s>[INST] {SYSTEM_PROMPT}

Title: {title}
Description: {description[:500]}
[/INST]"""


# ------------------------------------------------------------------
# HF API CALL
# ------------------------------------------------------------------

def _call_hf(prompt: str, api_url: str) -> str | None:
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 200,
            "temperature": 0.4,
            "return_full_text": False,
        },
    }
    try:
        resp = requests.post(api_url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            return data[0].get("generated_text", "")
        return None
    except Exception as e:
        print(f"[hf] {api_url} error: {e}")
        return None


def _parse_response(raw: str) -> dict | None:
    """Extract JSON from model output, handle minor formatting issues."""
    if not raw:
        return None
    # strip any accidental markdown fences
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    # find first { ... } block
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


# ------------------------------------------------------------------
# PUBLIC FUNCTION
# ------------------------------------------------------------------

def ai_enrich(title: str, raw_summary: str) -> dict | None:
    """
    Calls HF Inference API to get:
      - a crisp, friend-tone summary
      - smart category
      - role tags

    Returns a dict with keys: summary, category, roles
    Returns None if HF_TOKEN is not set or the call fails,
    so the caller can fall back to keyword logic.
    """
    if not HF_TOKEN:
        return None  # silently skip — keyword fallback will be used

    prompt = _build_prompt(title, raw_summary)

    # try primary model first, then fallback
    raw_output = _call_hf(prompt, HF_API_URL)
    if not raw_output:
        print("[hf] primary model failed, trying fallback...")
        raw_output = _call_hf(prompt, FALLBACK_API_URL)

    result = _parse_response(raw_output)
    if not result:
        print(f"[hf] could not parse response for: {title[:60]}")
        return None

    # validate / sanitise fields
    summary = result.get("summary", "").strip()[:200]
    category = result.get("category", "📰 General AI Update").strip()
    roles = result.get("roles", ["🌍 General Awareness"])
    if not isinstance(roles, list):
        roles = [str(roles)]

    return {
        "summary": summary or title,
        "category": category,
        "roles": roles,
    }


# ------------------------------------------------------------------
# QUICK TEST
# ------------------------------------------------------------------

if __name__ == "__main__":
    if not HF_TOKEN:
        print("Set HF_TOKEN env var to test.\nexport HF_TOKEN=hf_xxxxxxxxxxxx")
    else:
        test_title = "OpenAI launches GPT-5 with real-time voice and vision"
        test_desc = (
            "OpenAI has released GPT-5, its most powerful model yet, "
            "featuring real-time voice interaction, vision capabilities, "
            "and a new agentic mode that can autonomously browse the web and run code."
        )
        print("Calling HuggingFace API...")
        result = ai_enrich(test_title, test_desc)
        if result:
            print(f"\n✅ Summary : {result['summary']}")
            print(f"   Category: {result['category']}")
            print(f"   Roles   : {', '.join(result['roles'])}")
        else:
            print("❌ AI enrichment failed — check token and model availability")
