"""AI-powered idea analysis for the admin idea lab.

Uses the same provider-selection pattern as campaign_generator.py:
Anthropic direct → OpenRouter → deterministic fallback.
"""
import json
import sys

import httpx

from ..core.config import settings


SYSTEM_PROMPT = """You are a senior business strategist and product consultant. Given a business or product idea, provide a comprehensive analysis.

Output as JSON with this exact structure:
{
  "summary": "2-3 sentence refined pitch of the idea",
  "viability_score": 7,
  "viability_reasoning": "Why you gave this score — be specific about strengths and risks",
  "market_analysis": {
    "saturation": "low|medium|high",
    "competitors": ["Competitor 1", "Competitor 2", "Competitor 3"],
    "target_audience": "Who would pay for this and why",
    "market_size": "Estimated total addressable market"
  },
  "improvements": [
    "Specific way to strengthen the idea",
    "Another improvement suggestion"
  ],
  "todo_items": [
    {"task": "Actionable task description", "category": "dev|design|marketing|ops", "effort": "small|medium|large"},
    {"task": "Another task", "category": "dev", "effort": "medium"}
  ],
  "cost_estimate": {
    "development": {"min": 5000, "max": 15000},
    "marketing": {"min": 2000, "max": 8000},
    "infrastructure": {"min": 500, "max": 2000},
    "legal_ops": {"min": 1000, "max": 3000},
    "total": {"min": 8500, "max": 28000}
  },
  "go_to_market": [
    "Step 1: Validate with target audience",
    "Step 2: Build MVP",
    "Step 3: Launch strategy"
  ]
}

Rules:
- viability_score: 1-10 integer. Be honest — most ideas are 4-7.
- competitors: List real companies/products if they exist. Say "No direct competitors found" if truly novel.
- todo_items: 8-15 actionable items ordered by priority. Categories: dev, design, marketing, ops.
- cost_estimate: USD amounts. Be realistic for a small team / indie project. Total should equal sum of categories.
- go_to_market: 5-8 concrete steps.
- improvements: 3-5 specific, actionable suggestions.
- Return ONLY valid JSON, no markdown fences, no prose."""


def _build_prompt(title: str, description: str) -> str:
    return f"Idea: {title}\n\nDescription: {description}"


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}


def _via_anthropic(title: str, description: str, api_key: str) -> dict:
    with httpx.Client(timeout=90.0) as client:
        response = client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 4096,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": _build_prompt(title, description)}],
            },
        )
        response.raise_for_status()
        text = response.json()["content"][0]["text"]
        return _extract_json(text)


def _via_openrouter(title: str, description: str, api_key: str) -> dict:
    with httpx.Client(timeout=90.0) as client:
        response = client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://pxnn.app",
                "X-Title": "PxNN Admin",
                "content-type": "application/json",
            },
            json={
                "model": "anthropic/claude-haiku-4.5",
                "max_tokens": 4096,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _build_prompt(title, description)},
                ],
            },
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        return _extract_json(text)


def _via_fallback(title: str, description: str) -> dict:
    return {
        "summary": f"{title} — {description[:200]}",
        "viability_score": 5,
        "viability_reasoning": "Unable to perform AI analysis. Configure ANTHROPIC_API_KEY or OPENROUTER_API_KEY for full analysis.",
        "market_analysis": {
            "saturation": "unknown",
            "competitors": ["Analysis requires AI — configure API keys"],
            "target_audience": "To be determined with market research",
            "market_size": "Requires further analysis",
        },
        "improvements": [
            "Validate the idea with potential customers",
            "Research existing competitors in the space",
            "Define a clear unique value proposition",
            "Identify the minimum viable feature set",
        ],
        "todo_items": [
            {"task": "Define target customer persona", "category": "marketing", "effort": "small"},
            {"task": "Competitive landscape research", "category": "marketing", "effort": "medium"},
            {"task": "Design MVP wireframes", "category": "design", "effort": "medium"},
            {"task": "Build core MVP functionality", "category": "dev", "effort": "large"},
            {"task": "Set up infrastructure and hosting", "category": "dev", "effort": "small"},
            {"task": "Create landing page", "category": "marketing", "effort": "small"},
            {"task": "Beta test with early adopters", "category": "ops", "effort": "medium"},
            {"task": "Iterate based on feedback", "category": "dev", "effort": "medium"},
        ],
        "cost_estimate": {
            "development": {"min": 5000, "max": 20000},
            "marketing": {"min": 2000, "max": 10000},
            "infrastructure": {"min": 500, "max": 3000},
            "legal_ops": {"min": 1000, "max": 5000},
            "total": {"min": 8500, "max": 38000},
        },
        "go_to_market": [
            "Validate idea with 10-20 potential customers",
            "Build MVP with core feature set",
            "Launch beta to early adopters",
            "Collect feedback and iterate",
            "Public launch with marketing push",
            "Monitor metrics and optimize",
        ],
    }


def analyze_idea(title: str, description: str) -> dict:
    """Analyze a business idea and return structured analysis."""
    provider = (settings.AI_CLUSTERER_PROVIDER or "auto").lower().strip()

    if provider == "fallback":
        return _via_fallback(title, description)

    if provider in ("anthropic", "auto") and settings.ANTHROPIC_API_KEY:
        try:
            result = _via_anthropic(title, description, settings.ANTHROPIC_API_KEY)
            if result:
                return result
        except Exception as e:
            print(f"[idea_analyzer] Anthropic failed: {e}", file=sys.stderr)
            if provider == "anthropic":
                return _via_fallback(title, description)

    if provider in ("openrouter", "auto") and settings.OPENROUTER_API_KEY:
        try:
            result = _via_openrouter(title, description, settings.OPENROUTER_API_KEY)
            if result:
                return result
        except Exception as e:
            print(f"[idea_analyzer] OpenRouter failed: {e}", file=sys.stderr)

    return _via_fallback(title, description)
