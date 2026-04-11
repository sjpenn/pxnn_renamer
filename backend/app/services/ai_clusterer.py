"""
AI-powered clustering service for UIComment notes.

Supports Anthropic, OpenRouter, and a deterministic Jaccard-similarity fallback.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import List

import httpx

from ..core.config import settings
from ..database.models import UIComment

# ---------------------------------------------------------------------------
# Stopwords — extended list so common filler words don't drive false positives
# ---------------------------------------------------------------------------
_STOPWORDS = {
    # Original required set
    "the", "a", "an", "is", "to", "it", "of", "in", "and", "or", "for",
    "this", "that", "be", "make", "should", "needs", "need", "want",
    "please", "could", "would",
    # Extended filler words
    "completely", "unrelated", "idea", "something", "about", "too",
    "also", "just", "very", "more", "some", "any", "all", "not", "no",
    "with", "was", "are", "has", "had", "have", "been", "when", "where",
    "how", "what", "who", "which", "there", "their", "they", "them",
    "from", "then", "than", "but", "by", "at", "as", "up", "do", "if",
    "so", "we", "you", "me", "my", "our", "your", "its", "use", "get",
    "can", "will", "on", "its", "its", "were", "am", "does", "did",
    "its", "i", "he", "she", "they", "we", "us", "him", "her",
}

# ---------------------------------------------------------------------------
# Jaccard threshold — low enough to catch single-word overlap in short texts
# ---------------------------------------------------------------------------
_JACCARD_THRESHOLD = 0.12

# ---------------------------------------------------------------------------
# Shared AI prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are helping a small SaaS team triage admin UI feedback. "
    "You will be given a JSON list of notes. Each note has an integer id, "
    "a block_key identifying the UI section, and a body describing a requested change. "
    "Group notes that describe the same or highly-related change. "
    "Respond ONLY with minified JSON of the form:\n"
    '{"clusters": [{"title": "...", "summary": "...", "note_ids": [1,2,3]}, ...]}\n'
    "Rules:\n"
    "- Each note_id must appear in at most one cluster. Notes that do not cluster "
    "with anything should be OMITTED entirely (do not create singleton clusters).\n"
    "- Titles should be 3-8 words, crisp, action-oriented "
    '("Enlarge dropzone target", not "Dropzone suggestions").\n'
    "- Summaries should be 1-2 sentences capturing the common intent.\n"
    "- Return ONLY the JSON, no prose, no markdown fences."
)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------
@dataclass
class ClusterResult:
    title: str
    summary: str
    note_ids: List[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> set:
    """Lowercase word set minus stopwords, filtering single-char tokens."""
    words = text.lower().split()
    return {
        w.strip(".,!?;:\"'()[]{}") for w in words
        if len(w.strip(".,!?;:\"'()[]{}")) > 1
        and w.strip(".,!?;:\"'()[]{}") not in _STOPWORDS
    }


def _build_user_prompt(notes: List[UIComment]) -> str:
    return json.dumps([
        {"id": n.id, "block_key": n.block_key, "body": n.body}
        for n in notes
    ])


def _extract_json(text: str) -> dict:
    """Extract JSON from raw text or ```json fenced text."""
    stripped = text.strip()
    if stripped.startswith("```"):
        # Strip fences
        lines = stripped.splitlines()
        # Remove first and last fence lines
        inner_lines = []
        in_fence = False
        for line in lines:
            if line.startswith("```") and not in_fence:
                in_fence = True
                continue
            if line.startswith("```") and in_fence:
                break
            if in_fence:
                inner_lines.append(line)
        stripped = "\n".join(inner_lines).strip()
    try:
        return json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return {"clusters": []}


# ---------------------------------------------------------------------------
# Union-Find for Jaccard clustering
# ---------------------------------------------------------------------------

class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        px, py = self.find(x), self.find(y)
        if px != py:
            self.parent[px] = py


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _cluster_via_fallback(notes: List[UIComment]) -> List[ClusterResult]:
    """Deterministic Jaccard similarity clustering."""
    if not notes:
        return []

    token_sets = [_tokenize(n.body) for n in notes]
    uf = _UnionFind(len(notes))

    for i in range(len(notes)):
        for j in range(i + 1, len(notes)):
            a, b = token_sets[i], token_sets[j]
            if not a or not b:
                continue
            intersection = len(a & b)
            union = len(a | b)
            if union == 0:
                continue
            jaccard = intersection / union
            if jaccard >= _JACCARD_THRESHOLD:
                uf.union(i, j)

    # Build components
    from collections import defaultdict
    components: dict = defaultdict(list)
    for idx in range(len(notes)):
        root = uf.find(idx)
        components[root].append(idx)

    results = []
    for root, indices in components.items():
        if len(indices) < 2:
            continue  # Skip singletons

        group_notes = [notes[i] for i in indices]

        # Title: top 3 most common non-stopword tokens across group
        all_tokens: list = []
        for n in group_notes:
            all_tokens.extend(_tokenize(n.body))
        counter = Counter(all_tokens)
        top_words = [word for word, _ in counter.most_common(3)]
        title = " ".join(top_words).title()

        summary = f"Auto-grouped by keyword overlap — {len(group_notes)} note(s)"
        note_ids = [n.id for n in group_notes]
        results.append(ClusterResult(title=title, summary=summary, note_ids=note_ids))

    return results


def _cluster_via_anthropic(notes: List[UIComment], api_key: str) -> List[ClusterResult]:
    """Call Anthropic Messages API to cluster notes."""
    user_prompt = _build_user_prompt(notes)
    payload = {
        "model": "claude-haiku-4-5",
        "max_tokens": 2048,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    with httpx.Client() as client:
        response = client.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()

    text = response.json()["content"][0]["text"]
    data = _extract_json(text)
    return _parse_cluster_data(data)


def _cluster_via_openrouter(notes: List[UIComment], api_key: str) -> List[ClusterResult]:
    """Call OpenRouter chat completions API to cluster notes."""
    user_prompt = _build_user_prompt(notes)
    payload = {
        "model": "anthropic/claude-haiku-4.5",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 2048,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://pxnn.app",
        "X-Title": "PxNN Admin",
        "content-type": "application/json",
    }
    with httpx.Client() as client:
        response = client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()

    text = response.json()["choices"][0]["message"]["content"]
    data = _extract_json(text)
    return _parse_cluster_data(data)


def _parse_cluster_data(data: dict) -> List[ClusterResult]:
    """Convert raw parsed JSON clusters into ClusterResult objects."""
    results = []
    for c in data.get("clusters", []):
        try:
            results.append(ClusterResult(
                title=c["title"],
                summary=c["summary"],
                note_ids=[int(x) for x in c.get("note_ids", [])],
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def cluster_notes(notes: List[UIComment]) -> List[ClusterResult]:
    """
    Group UIComment notes into clusters using the configured AI provider.

    Returns [] if notes is empty.
    Falls through to deterministic fallback on any HTTP/API failure.
    """
    if not notes:
        return []

    provider = (settings.AI_CLUSTERER_PROVIDER or "auto").lower()
    anthropic_key = settings.ANTHROPIC_API_KEY
    openrouter_key = settings.OPENROUTER_API_KEY

    # Resolve provider
    if provider == "auto":
        if anthropic_key:
            provider = "anthropic"
        elif openrouter_key:
            provider = "openrouter"
        else:
            provider = "fallback"

    if provider == "fallback":
        return _cluster_via_fallback(notes)

    if provider == "anthropic":
        if not anthropic_key:
            print(
                "[ai_clusterer] anthropic forced but ANTHROPIC_API_KEY is not set; "
                "degrading to fallback",
                file=sys.stderr,
            )
            return _cluster_via_fallback(notes)
        try:
            return _cluster_via_anthropic(notes, anthropic_key)
        except Exception as exc:
            print(
                f"[ai_clusterer] anthropic call failed ({exc!r}); degrading to fallback",
                file=sys.stderr,
            )
            return _cluster_via_fallback(notes)

    if provider == "openrouter":
        if not openrouter_key:
            print(
                "[ai_clusterer] openrouter forced but OPENROUTER_API_KEY is not set; "
                "degrading to fallback",
                file=sys.stderr,
            )
            return _cluster_via_fallback(notes)
        try:
            return _cluster_via_openrouter(notes, openrouter_key)
        except Exception as exc:
            print(
                f"[ai_clusterer] openrouter call failed ({exc!r}); degrading to fallback",
                file=sys.stderr,
            )
            return _cluster_via_fallback(notes)

    # Unknown provider — fall back
    print(
        f"[ai_clusterer] unknown provider {provider!r}; degrading to fallback",
        file=sys.stderr,
    )
    return _cluster_via_fallback(notes)
