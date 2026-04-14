# Name Line Builder — Design Spec

**Date:** 2026-04-14
**Status:** Approved — ready for implementation planning

## Problem

The current rename flow splits naming config across three places: Step 2's `default_artist` / `default_producers` text fields, a `format_template` textarea, and a separate drag-reorder token-builder row (`app.html` ~line 232). Users who want multiple artists or multiple producers must shove semicolon-separated values into a text field, and the relationship between the template string and the actual values is indirect. This makes a simple task (arrange the pieces of a filename) feel like three tasks.

## Goal

Replace those three UI regions with a single **Name Line**: one horizontal, direct-manipulation component where the blocks the user sees in the line are literally the filename. Each producer and each artist is its own block. Block categories are color-coded for fast scanning. Autocomplete surfaces previously-used names.

## Non-goals

- Reworking the file parser or the rename execution engine beyond the minimal serialization changes described below.
- Changing Step 1 (upload) or Step 3 (review/execute).
- Adding new token types beyond the ones already supported (ARTIST, PRODUCER, TITLE, MIX, VERSION, BPM, KEY, DATE, INDEX).
- Mobile-first optimization — desktop is the primary target; mobile parity is a later pass.

## Design

### Architecture

One component, the **Name Line**, replaces:
- Step 2's `default_artist` input
- Step 2's `default_producers` input
- Step 2's `format_template` textarea
- The current `#token-builder` row

The Name Line is the single source of truth for naming config. What the user sees left-to-right is what the filename becomes.

### Block types

Three block types live in the line:

1. **Token blocks** — `TITLE`, `BPM`, `KEY`, `DATE`, `INDEX`, `MIX`, `VERSION` (singletons: parser-populated, label-only) and `ARTIST` / `PRODUCER` (repeatable, one block per value, inline-edited).
2. **Literal text blocks** (`TEXT`) — freeform user text (e.g. `@`, `feat.`, `+`). Always editable inline. Visually replaces the separator gap at that position.
3. **Separator gaps** — the invisible space between adjacent token/text blocks. Filled globally by a single separator setting (`_`, `-`, ` `, custom). A TEXT block at a position replaces the gap visually and literally.

### Layout

```
┌─ Legend (collapsible): ● Identity  ● Content  ● Metadata  ● Variant ─┐

[Palette: + ARTIST  + PRODUCER  + TITLE  + BPM  + KEY  + DATE  + INDEX  + MIX  + VERSION  + TEXT]

┌─ Name Line ──────────────────────────────────────────────────────────┐
│ [ARTIST: Hurricane Wisdom] [PRODUCER: PMHITSS] [PRODUCER: REALLYINDIG0] [@] [TITLE] [BPM] │
└──────────────────────────────────────────────────────────────────────┘

Separator: [ _ ▾ ]   Reset to default

Preview: Hurricane Wisdom_PMHITSS_REALLYINDIG0@Loaded Up_140.mp3
```

Clicking a palette button appends a new block at the end of the line. Blocks are drag-reorderable anywhere within the line. Each block has a × remove affordance on hover.

### Block visual design

Each block is a pill-shaped chip with:
- A 4px left color swatch indicating category.
- A small category icon (e.g. `person` for ARTIST, `graphic_eq` for PRODUCER, `music_note` for TITLE).
- The token label and, for value-bearing tokens, the value (`ARTIST: Hurricane Wisdom`).
- A × close button visible on hover.
- The whole chip is the drag handle.

Background: ~8% tint of the swatch color, keeping label text readable.

### Color coding (4 families)

Aligned with the warm editorial theme:

| Family | Color | Tokens |
|---|---|---|
| Identity | warm amber/terracotta | ARTIST, PRODUCER |
| Content | ink/neutral | TITLE |
| Metadata | cool sage/teal | BPM, KEY, DATE, INDEX |
| Variant | muted plum/accent | MIX, VERSION |
| Literal | hairline border, no fill | TEXT |

Accessibility: color is never the only signal. Every token type also has a distinct icon and its text label is always shown. The legend below the palette is a persistent key.

### Inline edit behavior

**Singleton tokens** (`TITLE`, `BPM`, `KEY`, `DATE`, `INDEX`, `MIX`, `VERSION`): label only, no inline edit. Value is filled by the parser per file at rename time. Preview uses the first uploaded file's parsed value (or `—` if missing).

**Value-bearing tokens** (`ARTIST`, `PRODUCER`): on add, the chip mounts in edit mode with a text input and an autocomplete dropdown of the user's previously-used values (ranked by recency + frequency). Enter or blur-with-value commits. Click a committed chip to re-edit.

**Literal TEXT blocks**: always editable inline; no autocomplete. Empty TEXT blocks are allowed (user may be mid-edit) but flagged like empty value-bearing tokens if the user tries to submit.

### Autocomplete

New backend endpoints:
- `GET /api/suggestions/producers` — returns distinct PRODUCER values from the current user's prior rename history, ordered by recency then frequency.
- `GET /api/suggestions/artists` — same, for ARTIST.

Response shape: `{ "values": ["PMHITSS", "REALLYINDIG0", ...] }`. Client caches per-session. Failure mode: dropdown silently disabled; free-text entry still works.

### Separator behavior (A3)

- One global separator setting applies to every gap between blocks by default.
- Changing the global separator updates all gap rendering immediately; TEXT blocks are untouched.
- To customize one specific gap, the user drops a TEXT block there. The TEXT block replaces the separator at that position both visually and in the serialized output.

### Data model (client)

```js
{
  blocks: [
    { id: 'b1', type: 'ARTIST',   value: 'Hurricane Wisdom' },
    { id: 'b2', type: 'PRODUCER', value: 'PMHITSS' },
    { id: 'b3', type: 'PRODUCER', value: 'REALLYINDIG0' },
    { id: 'b4', type: 'TEXT',     value: '@' },
    { id: 'b5', type: 'TITLE' },
    { id: 'b6', type: 'BPM' },
  ],
  globalSeparator: '_'
}
```

Persisted to `localStorage` per user. "Reset to default" restores the equivalent of `ARTIST_TITLE_PRODUCERS_MIX_VERSION`.

### Serialization to backend

On every change the client serializes to two fields and POSTs/updates the rename request:

- `format_template` — positional template string. Repeated ARTIST/PRODUCER tokens appear multiple times. TEXT blocks insert their literal content in place of the gap separator. Example for the model above with separator `_`:
  `ARTIST_PRODUCER_PRODUCER@TITLE_BPM`
- `values` — `{ artist: ['Hurricane Wisdom'], producers: ['PMHITSS', 'REALLYINDIG0'] }`.

The backend's format-string expander consumes repeated `ARTIST` / `PRODUCER` tokens positionally from the `values` arrays. The old request shape (`default_artist`, `default_producers`, single `format_template` with singleton `ARTIST`/`PRODUCERS`) continues to work during the transition.

### Live preview

Below the line, the preview filename updates on every change. It uses the first uploaded file's parsed values for singletons (BPM/KEY/etc.) and the explicit values from the line for ARTIST/PRODUCER. If no file is uploaded yet, it uses a generic sample.

### Step 2 after the change

Step 2 collapses to a single purpose: "Build your name." Legend, palette, Name Line, separator dropdown, reset, preview. That's it.

## Error handling & edge cases

- **Empty value-bearing block**: chip shows a red hairline + warning icon; preview shows `⚠ empty producer` (or artist) at that position; rename submit is disabled until the block is filled or removed.
- **No files uploaded yet**: line is still usable; preview shows a generic sample (`Sample Artist_Sample Title_...`).
- **Parser-missing singleton** (e.g. no BPM detectable in file): preview shows `—` at that position; chip gets a "not found in file" tooltip. Submit is not blocked — the rename engine already handles missing singletons.
- **Duplicate producer names**: allowed. A subtle "duplicate" hint appears but doesn't block (some filenames legitimately repeat a name).
- **Global separator change mid-flight**: applies to all gaps; TEXT blocks untouched.
- **Drag onto self / drop outside the line**: no-op, chip snaps back.
- **Autocomplete endpoint failure**: dropdown silently disabled, free-text entry still works.
- **localStorage unavailable**: line falls back to default template in memory; no user-facing warning.

## Testing

**Backend (pytest):**
- `format_template` + `values` round-trip for each block type.
- Repeated `ARTIST` / `PRODUCER` tokens consume values positionally.
- Old request shape (`default_artist` / `default_producers` / singleton template) still produces correct rename output.
- `/api/suggestions/producers` and `/api/suggestions/artists` return distinct, user-scoped values ordered by recency then frequency.
- Unauthenticated requests to suggestion endpoints are rejected.

**Frontend (lightweight JS test harness):**
- Serialization produces expected `format_template` + `values` for each block arrangement.
- Drag-reorder updates preview.
- Empty value-bearing block blocks submit; filling it unblocks.
- Global separator change updates all gap rendering; TEXT-block overrides persist through separator changes.
- Autocomplete endpoint failure leaves free-text entry functional.

## Out of scope (explicit)

- Saving and recalling named "presets" of Name Line configurations.
- Keyboard-driven reordering (arrow-key move). Drag-only for v1.
- Sharing/exporting Name Line configurations between users.
- Mobile-optimized drag interaction.

## Files likely to change

- `frontend/templates/app.html` — replace Step 2 markup (default_artist, default_producers, format_template textarea, current token-builder).
- `frontend/static/js/` — new module for the Name Line component (state, render, drag, serialize, autocomplete, localStorage).
- `frontend/static/css/tailwind-input.css` or `style.css` — color family tokens and chip styles.
- `backend/app/routes/` — new suggestions router; extend rename route to accept the new `values` shape with repeated tokens.
- `backend/app/services/` (wherever format expansion lives) — positional consumption of `values.artist[]` and `values.producers[]`.
- Tests under `tests/` (or equivalent) for the above.
