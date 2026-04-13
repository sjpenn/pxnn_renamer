# Admin Idea Lab

**Date**: 2026-04-12
**Status**: Approved

## Overview

A general-purpose idea capture and AI analysis system in the admin panel. Admins type raw ideas, then AI expands them into structured analyses with todo items, market research, improvement suggestions, and ballpark cost estimates.

---

## 1. Database: `Idea` Model

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `title` | String, not null | Short idea name |
| `description` | Text, not null | Raw idea as typed by admin |
| `status` | String, default "draft" | draft / analyzed / archived |
| `analysis_json` | Text, nullable | Full AI analysis stored as JSON |
| `created_by_id` | Integer FK -> users.id | |
| `created_at` | DateTime | |
| `updated_at` | DateTime | |

## 2. AI Analysis Service

**File**: `backend/app/services/idea_analyzer.py`

Same Anthropic/OpenRouter/fallback provider pattern as campaign_generator.py and promo_generator.py.

**Input**: idea title + description (strings)

**Output**: Structured JSON with these sections:

```json
{
  "summary": "2-3 sentence refined pitch",
  "viability_score": 7,
  "viability_reasoning": "Why this score",
  "market_analysis": {
    "saturation": "low|medium|high",
    "competitors": ["Competitor A", "Competitor B"],
    "target_audience": "Description of who wants this",
    "market_size": "Estimated TAM"
  },
  "improvements": [
    "Improvement suggestion 1",
    "Improvement suggestion 2"
  ],
  "todo_items": [
    {"task": "Build X", "category": "dev", "effort": "medium"},
    {"task": "Design Y", "category": "design", "effort": "small"}
  ],
  "cost_estimate": {
    "development": {"min": 5000, "max": 15000},
    "marketing": {"min": 2000, "max": 8000},
    "infrastructure": {"min": 500, "max": 2000},
    "legal_ops": {"min": 1000, "max": 3000},
    "total": {"min": 8500, "max": 28000}
  },
  "go_to_market": [
    "Step 1: ...",
    "Step 2: ..."
  ]
}
```

**Fallback**: Template-based analysis with generic structure and placeholder values.

## 3. Admin Routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/admin/ideas` | List page with create form |
| POST | `/admin/ideas` | Create new idea (status=draft) |
| GET | `/admin/ideas/{id}` | Detail page |
| POST | `/admin/ideas/{id}/analyze` | Run AI analysis, store in analysis_json, set status=analyzed |
| POST | `/admin/ideas/{id}/archive` | Toggle status to/from archived |
| POST | `/admin/ideas/{id}/delete` | Delete idea |

## 4. Templates

### List page: `admin/ideas.html`

- Create form: title input + description textarea + submit button
- Table/card list of all ideas sorted by created_at desc
- Each row: title, status badge (draft=amber, analyzed=success, archived=muted), created date, link to detail

### Detail page: `admin/idea_detail.html`

- Raw idea display (title + description) at top
- Action buttons: "Analyze with AI" (if draft), "Re-analyze" (if analyzed), "Archive"/"Unarchive", "Delete"
- If analyzed, render sections from analysis_json:
  - **Summary** — refined pitch text
  - **Viability Score** — number with color-coded badge (1-3 red, 4-6 amber, 7-10 green) + reasoning
  - **Market Analysis** — saturation badge, competitors list, target audience, market size
  - **Areas to Improve** — bulleted list
  - **Todo Items** — list with category badges (dev/design/marketing/ops) and effort indicators
  - **Cost Estimate** — category rows with min-max ranges, total at bottom
  - **Go-to-Market Strategy** — numbered steps

## 5. Admin Nav

Add "Ideas" link to admin base.html nav bar.

## Out of Scope

- Todo item completion tracking (checkboxes that persist) — ideas are for planning, not execution
- Sharing/exporting ideas
- Collaborative editing
- Version history of analyses
