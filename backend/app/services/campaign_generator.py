"""Ad copy generation for campaigns.

Uses the same provider-selection pattern as ai_clusterer.py:
Anthropic direct → OpenRouter → deterministic fallback.
"""
import json
import sys
from dataclasses import dataclass
from typing import List

import httpx

from ..core.config import settings
from ..database.models import Campaign


@dataclass
class CopyVariant:
    headline: str
    primary_text: str
    description: str
    cta: str


SYSTEM_PROMPT = """You are an expert Meta ads copywriter for a music production SaaS targeting hip hop and soul beatmakers.
Generate ad copy variants that feel authentic to studio culture — never corporate, never generic.

Given a campaign brief, output exactly 8 distinct ad copy variants as JSON:
{"variants": [{"headline": "...", "primary_text": "...", "description": "...", "cta": "..."}, ...]}

Rules:
- headline: 5-10 words, punchy, scroll-stopping. No clickbait.
- primary_text: 2-4 sentences. Lead with a pain point or aspiration. Include the offer if provided.
- description: 1 sentence, supporting detail or social proof angle.
- cta: One of: "Learn More", "Sign Up", "Get Started", "Try Free", "Shop Now", "Download". Pick the best fit.
- Vary angle across variants: some pain-point-driven, some aspiration-driven, some offer-driven, some social-proof-driven.
- Match the requested tone (authentic, hype, chill, professional).
- Return ONLY valid JSON, no markdown fences, no prose."""


def _build_brief_prompt(campaign: Campaign) -> str:
    brief = {
        "product": campaign.product_description,
        "audience": campaign.target_audience,
        "tone": campaign.tone,
        "placements": campaign.placements,
    }
    if campaign.offer:
        brief["offer"] = campaign.offer
    return f"Campaign brief:\n{json.dumps(brief, indent=2)}"


def _extract_json(text: str) -> dict:
    """Parse JSON from text, handling optional markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last lines (fences)
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"variants": []}


def _parse_variants(data: dict) -> List[CopyVariant]:
    result = []
    for v in data.get("variants", []):
        if not v.get("headline") or not v.get("primary_text"):
            continue
        result.append(CopyVariant(
            headline=v["headline"],
            primary_text=v["primary_text"],
            description=v.get("description", ""),
            cta=v.get("cta", "Learn More"),
        ))
    return result


def _via_anthropic(campaign: Campaign, api_key: str) -> List[CopyVariant]:
    with httpx.Client(timeout=60.0) as client:
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
                "messages": [{"role": "user", "content": _build_brief_prompt(campaign)}],
            },
        )
        response.raise_for_status()
        text = response.json()["content"][0]["text"]
        return _parse_variants(_extract_json(text))


def _via_openrouter(campaign: Campaign, api_key: str) -> List[CopyVariant]:
    with httpx.Client(timeout=60.0) as client:
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
                    {"role": "user", "content": _build_brief_prompt(campaign)},
                ],
            },
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        return _parse_variants(_extract_json(text))


def _via_fallback(campaign: Campaign) -> List[CopyVariant]:
    """Deterministic fallback — generates 4 template-based variants."""
    name = campaign.name or "our product"
    audience = campaign.target_audience or "beatmakers"
    offer_line = f" {campaign.offer}." if campaign.offer else ""

    templates = [
        CopyVariant(
            headline=f"Your beats deserve better filenames",
            primary_text=f"Stop spending hours renaming tracks manually. {name} uses precision metadata to organize your entire catalog in seconds.{offer_line}",
            description="Built by producers, for producers.",
            cta="Get Started",
        ),
        CopyVariant(
            headline=f"Clean files. Clean workflow. Clean sound.",
            primary_text=f"Every {audience.split(',')[0].strip().lower()} knows the struggle — hundreds of unnamed bounces cluttering your drive. {name} fixes that.{offer_line}",
            description="Batch rename with metadata intelligence.",
            cta="Try Free",
        ),
        CopyVariant(
            headline=f"From chaos to catalog in 60 seconds",
            primary_text=f"Upload your tracks, set your naming convention once, and let {name} handle the rest. Your future self will thank you.{offer_line}",
            description="Works with WAV, MP3, AIFF, and FLAC.",
            cta="Learn More",
        ),
        CopyVariant(
            headline=f"The filename studio {audience.split(',')[0].strip().lower()} actually need",
            primary_text=f"BPM, key, artist, version — automatically extracted and formatted your way. No more 'final_final_v3_REAL.wav'.{offer_line}",
            description="Precision metadata for serious producers.",
            cta="Sign Up",
        ),
    ]
    return templates


def generate_copy(campaign: Campaign) -> List[CopyVariant]:
    """Generate ad copy variants for a campaign. Follows the same
    provider-selection pattern as ai_clusterer.cluster_notes()."""
    provider = (settings.AI_CLUSTERER_PROVIDER or "auto").lower().strip()

    if provider == "fallback":
        return _via_fallback(campaign)

    if provider in ("anthropic", "auto") and settings.ANTHROPIC_API_KEY:
        try:
            return _via_anthropic(campaign, settings.ANTHROPIC_API_KEY)
        except Exception as e:
            print(f"[campaign_generator] Anthropic failed: {e}", file=sys.stderr)
            if provider == "anthropic":
                return _via_fallback(campaign)

    if provider in ("openrouter", "auto") and settings.OPENROUTER_API_KEY:
        try:
            return _via_openrouter(campaign, settings.OPENROUTER_API_KEY)
        except Exception as e:
            print(f"[campaign_generator] OpenRouter failed: {e}", file=sys.stderr)

    return _via_fallback(campaign)
