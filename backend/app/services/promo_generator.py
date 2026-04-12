"""Promotional headline generation for admin promotions.

Uses the same provider-selection pattern as campaign_generator.py:
Anthropic direct → OpenRouter → deterministic fallback.
"""
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

from ..core.config import settings


@dataclass
class PromoSuggestion:
    headline: str
    description: str
    duration_days: int


SYSTEM_PROMPT = """You are an expert marketing copywriter for PxNN, a music production SaaS that helps hip hop and soul beatmakers batch-rename their audio files with precision metadata.

Given a promotional offer (plan name, base credits, bonus credits), generate a catchy promotional headline and description that drives urgency and conversions.

Output as JSON:
{"headline": "...", "description": "...", "duration_days": N}

Rules:
- headline: Under 60 characters. Punchy, exciting, clear value proposition. Use the actual numbers.
- description: 1-2 sentences. Create urgency, highlight the value. Authentic to studio/producer culture.
- duration_days: Recommend an optimal promotion duration (7-30 days) based on the offer size.
- Never use generic corporate language. Sound like a producer talking to producers.
- Return ONLY valid JSON, no markdown fences, no prose."""


def _build_prompt(plan_label: str, plan_credits: int, bonus_credits: int) -> str:
    return (
        f"Create a promotional offer for our '{plan_label}' plan.\n"
        f"Base credits: {plan_credits}\n"
        f"Bonus credits being offered: {bonus_credits}\n"
        f"Total credits customer gets: {plan_credits + bonus_credits}"
    )


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}


def _parse_suggestion(data: dict) -> PromoSuggestion:
    return PromoSuggestion(
        headline=data.get("headline", ""),
        description=data.get("description", ""),
        duration_days=int(data.get("duration_days", 14)),
    )


def _via_anthropic(plan_label: str, plan_credits: int, bonus_credits: int, api_key: str) -> PromoSuggestion:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 512,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": _build_prompt(plan_label, plan_credits, bonus_credits)}],
            },
        )
        response.raise_for_status()
        text = response.json()["content"][0]["text"]
        return _parse_suggestion(_extract_json(text))


def _via_openrouter(plan_label: str, plan_credits: int, bonus_credits: int, api_key: str) -> PromoSuggestion:
    with httpx.Client(timeout=30.0) as client:
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
                "max_tokens": 512,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _build_prompt(plan_label, plan_credits, bonus_credits)},
                ],
            },
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        return _parse_suggestion(_extract_json(text))


def _via_fallback(plan_label: str, plan_credits: int, bonus_credits: int) -> PromoSuggestion:
    return PromoSuggestion(
        headline=f"Buy {plan_credits} credits, get {bonus_credits} FREE!",
        description=f"Grab the {plan_label} now and unlock {bonus_credits} bonus credits — upgrade your workflow today.",
        duration_days=14,
    )


def generate_promo(plan_label: str, plan_credits: int, bonus_credits: int) -> PromoSuggestion:
    """Generate a promotional headline and description."""
    provider = (settings.AI_CLUSTERER_PROVIDER or "auto").lower().strip()

    if provider == "fallback":
        return _via_fallback(plan_label, plan_credits, bonus_credits)

    if provider in ("anthropic", "auto") and settings.ANTHROPIC_API_KEY:
        try:
            return _via_anthropic(plan_label, plan_credits, bonus_credits, settings.ANTHROPIC_API_KEY)
        except Exception as e:
            print(f"[promo_generator] Anthropic failed: {e}", file=sys.stderr)
            if provider == "anthropic":
                return _via_fallback(plan_label, plan_credits, bonus_credits)

    if provider in ("openrouter", "auto") and settings.OPENROUTER_API_KEY:
        try:
            return _via_openrouter(plan_label, plan_credits, bonus_credits, settings.OPENROUTER_API_KEY)
        except Exception as e:
            print(f"[promo_generator] OpenRouter failed: {e}", file=sys.stderr)

    return _via_fallback(plan_label, plan_credits, bonus_credits)
