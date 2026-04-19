# Name Line Simplification — Design Spec

**Date:** 2026-04-19
**Status:** Approved — ready for implementation planning
**Supersedes (partial):** [`2026-04-14-name-line-builder-design.md`](2026-04-14-name-line-builder-design.md) — the Name Line component itself stays; this spec replaces its surrounding wizard scaffolding and its drag-and-drop implementation.

## Problem

Two issues compound each other:

1. **Drag-and-drop reorder is broken.** Indicators appear, but on release the reorder doesn't persist and the chip snaps back. The likely root cause is a race between `pointerup` and the browser-fired `click` that follows it: the click triggers `openEditor`, which wipes the reordered chip's DOM, and a 100ms-delayed `blur` commit then overwrites the reordered state with stale data.

2. **Step 2 is cluttered.** The Name Line builder coexists with a duplicate separator dropdown, a casing select, a precision-cleanup toggle, a per-file metadata editor, a "Refresh Preview" button, and "Continue" buttons to/from Step 3. The user sees the Name Line as the real control but is fighting three nearby form fields that do overlapping things.

The result: a tool whose core gesture (drag to reorder) doesn't work, embedded in a wizard that makes a simple task (arrange the pieces of a filename) feel like three unrelated tasks.

## Goal

- **Reliable reorder** via a library-driven drag model with multiple redundant affordances (grip handle, arrow buttons, keyboard shortcuts).
- **Single-page flow** collapsing the 3-step wizard into one scrolling page: upload → Name Line → preview with inline warnings and download.
- **Drop non-essential controls** (casing, cleanup) with sane defaults baked in.

## Non-goals

- Reworking backend rename logic. Existing `format_template` / `values` contract stays; one optional field (`overrides`) is added.
- Changing the Name Line chip data model, token categories, or autocomplete backend.
- Mobile-optimized touch drag (grip handle helps; full polish is future work).
- Preserving the 3-step wizard behind a feature flag. It's removed outright.
- Name Line preset saving/sharing.

## Design

### Architecture

The `[data-step-panel="1"|"2"|"3"]` sections in `frontend/templates/app.html` are removed. The single-page layout has three vertically-stacked zones:

```
┌──────────────────────────────────────────────────────────┐
│  1. UPLOAD              (collapses to slim bar once full)│
│     [ Drop files ]      42 files loaded · + add more    │
├──────────────────────────────────────────────────────────┤
│  2. NAME LINE           (position: sticky; top: 0)       │
│     [Legend]                                             │
│     [Palette: + ARTIST + PRODUCER + TITLE + ...]         │
│     [ ⠿ ARTIST | ⠿ TITLE | ⠿ PRODUCER | ⠿ MIX ]         │
│     Separator: [ _ ▾ ]                                   │
├──────────────────────────────────────────────────────────┤
│  3. PREVIEW & DOWNLOAD  (one row per file)               │
│     ⚠ Hurricane Wisdom_?.mp3   missing producer   ✎     │
│       Hurricane Wisdom_Loaded Up_PMHITSS.mp3      ✎     │
│       … 40 more                                          │
│     [ Download ZIP ]    3 issues blocking → fix to enable│
└──────────────────────────────────────────────────────────┘
```

The Name Line is sticky during scroll so chip edits and reorders stay visible against the preview below.

### Chip design

Each chip has five interactive regions:

```
┌─────────────────────────────────────────┐
│ ⠿ │▌│ 👤 ARTIST: Hurricane Wisdom │◀│▶│× │
└─┬─┴─┴─────────┬──────────────────┴─┴─┴─┘
  │             │                    │ │ └─ remove
  │             │                    │ └─── reorder right (Alt+→)
  │             │                    └───── reorder left  (Alt+←)
  │             └────────── clickable body → edit mode
  └────── drag handle (grip)
```

- **Grip (`⠿`)** is the **only** drag source. Chip body no longer initiates drag.
- **Chip body click** opens inline edit for value-bearing chips (ARTIST, PRODUCER, TEXT).
- **◀ ▶ arrows** are always visible; disabled at first/last position.
- **× remove** is always visible.
- **Keyboard:** `Tab` focuses chip (focus ring), `Alt+←/→` reorders, `Enter` opens edit, `Delete` removes.

### Drag implementation — SortableJS

- Vendor `sortable.min.js` (~13 KB gzipped) at `frontend/static/vendor/sortable.min.js`.
- Load via a `<script>` tag in `base.html` (or inline in `app.html` above `name-line.js`).
- Initialize once per mount:
  ```js
  Sortable.create(lineEl, {
    handle: '.nl-grip',
    animation: 150,
    ghostClass: 'nl-ghost',
    onEnd: (e) => { reorderBlock(e.oldIndex, e.newIndex); }
  });
  ```
- **Remove all existing pointer-drag code** from `frontend/static/js/name-line.js` (lines ~314-412 in the current file): `attachDrag`, `onPointerMove`, `onPointerUp`, `insertionTargetFromPoint`, `clearDropIndicators`, the `drag` mutable state, and the `DRAG_THRESHOLD_PX` constant.

### Diff-rendering (required for SortableJS compatibility)

The current `renderLine()` wipes `lineEl.innerHTML = ""` on every state change. This fights SortableJS, which tracks DOM order as the source of truth during a drag.

Replace with a diff-renderer:

1. Build `existingByid = Map(chipEl.dataset.blockId → chipEl)` from current DOM children.
2. For each `block` in `state.blocks` in order:
   - If `existingByid` has a chip for this id, keep it; update its value/label if changed; append to `lineEl` (moves if needed).
   - If not, create a new chip and append.
3. Remove any chip in `existingByid` whose id is no longer in state.

This preserves Sortable's internal DOM bookkeeping and keyboard focus across re-renders.

### Preview table & inline warnings

Below the sticky Name Line, a single table. One row per uploaded file.

**Row states:**
- **OK row** — plain text, low-contrast `✎` on hover.
- **Warning row (`⚠`)** — 3px left border in `--danger`, warm-red background tint, inline reason text (`missing producer`, `no metadata detected`, etc.), `✎` always visible.
- **Edit-open row** — expands inline to show one input per value-bearing Name Line block; edits apply to that file only, stored in `state.overrides`.

**Warning rule:** a row shows `⚠` when any value-bearing block in the Name Line has no resolved value for that file (no Name Line value, no parsed value from filename, no override). Missing singletons (e.g., BPM not in filename) render as `—` and do **not** trigger a warning — the backend already tolerates them.

**Download gating:**
- Any warning row → Download button disabled with label "Fix N issues to download".
- Existing credit/auth gate at [app.html:279-293](frontend/templates/app.html:279) moves unchanged beneath Download as a second gating layer.
- Clicking `✎` on a warning row auto-focuses the first empty field for that row.

**Live recomputation:** every Name Line change recomputes preview rows only (not the Name Line itself). Debounce 80 ms so drag-in-progress doesn't thrash the table.

### Data model (client)

```js
{
  blocks: [
    { id: 'b1', type: 'ARTIST',   value: 'Hurricane Wisdom' },
    { id: 'b2', type: 'TITLE' },
    { id: 'b3', type: 'PRODUCER', value: 'PMHITSS' },
  ],
  globalSeparator: '_',
  overrides: {
    'file_af12': { PRODUCER: 'REALLYINDIG0' },
    'file_b0e9': { TITLE: 'Overtime', PRODUCER: 'PMHITSS' }
  }
}
```

Persisted to `localStorage` under key `pxnn.nameLine.v2` (bumped from `.v1`). Migration on load: v1 state gets `overrides: {}` appended; no data loss.

### Backend contract

**Unchanged** for existing fields. One optional field added to the rename request:

```json
{
  "format_template": "ARTIST_TITLE_PRODUCER",
  "values": { "artist": ["Hurricane Wisdom"], "producers": ["PMHITSS"] },
  "overrides": {
    "file_af12": { "PRODUCER": "REALLYINDIG0" }
  }
}
```

Resolution order per token per file:
1. `overrides[file_id][TOKEN]` if present
2. Value parsed from the original filename
3. Value from the Name Line block (for value-bearing tokens: ARTIST, PRODUCER, TEXT)
4. Missing → `—` for singletons (no error), `⚠` for value-bearing (blocks download)

### Defaults (dropped from UI)

| Setting | New default | Rationale |
|---|---|---|
| Casing | `keep` | 99%+ of users wanted this; advanced control moves to user profile later if needed. |
| Safe cleanup | `true` | Always-on archive safety is the right default for the target audience. |
| Separator | `_` | Visible as the one remaining form control beneath the Name Line. |

Backend `casing` and `safe_cleanup` logic is untouched; the request sends them as constants.

### Removed from UI

- `<form id="rename-form">` block at [app.html:196-231](frontend/templates/app.html:196) (Separator Logic, Casing Style, Precision Cleanup).
- "Per-file cleanup" panel at [app.html:233-251](frontend/templates/app.html:233) including `#metadata-editor-list` and `#refresh-preview`.
- `#go-review` and "Continue" buttons.
- Step 3's "Active Rule Summary" `<dl>` card.
- `[data-step-panel]` wrapper sections.

## Error handling & edge cases

| Case | Behavior |
|---|---|
| Drag dropped outside line | SortableJS native behavior — chip snaps back; no state change. |
| Drag source chip vanishes mid-drag (e.g., rapid edit from another user action) | `onEnd` sees invalid index; no-op; single console warning. |
| Empty value-bearing chip | Chip gets red hairline; every file row shows `⚠`; Download disabled. |
| `localStorage` unavailable | Fall back to in-memory state; silent (same as today). |
| Suggestions endpoint 4xx/5xx | Dropdown hidden; free-text entry still works (same as today). |
| User removes chip mid-edit | Edit commit aborted; block removed; preview recomputes. |
| Name Line has zero blocks | Preview shows "Add at least one block to start" placeholder; Download disabled. |
| Duplicate chip ids (shouldn't happen) | Diff-renderer keeps first; logs. Defensive. |
| SortableJS fails to load (CDN/vendor broken) | Arrow buttons + keyboard still reorder; drag silently unavailable. |

## Testing

### Backend (pytest)

Extend `tests/test_name_line_render.py`:

- `overrides` map replaces parsed value for the named file+token; falls back correctly when the key is absent.
- Request without `overrides` field produces identical output to pre-change behavior (backward compat).
- Repeated ARTIST / PRODUCER tokens continue to consume `values` arrays positionally (existing behavior, regression guard).
- `overrides` with a file_id not in the upload set is ignored silently (no 500).

### Frontend (new test harness)

Add `tests/frontend/name-line.test.js` (Node + jsdom, or a minimal `<script type="module">` runner served at `/test`):

- **Diff-render correctness:** state `[A,B,C]` → DOM `[A,B,C]`; reorder state to `[B,A,C]` → DOM nodes moved, not replaced (identity preserved via reference equality).
- **SortableJS integration:** `onEnd({oldIndex: 0, newIndex: 2})` on state `[A,B,C]` produces `[B,C,A]`.
- **Drag source isolation:** clicking `.nl-grip` does **not** open editor; clicking chip body does.
- **Arrow buttons:** `◀` disabled at index 0; `▶` disabled at last index; click moves chip one position.
- **Keyboard:** focused chip + `Alt+ArrowRight` moves one right; `Alt+ArrowLeft` moves one left; `Enter` opens editor; `Delete` removes.
- **Warning rule:** file with no parseable ARTIST + ARTIST chip empty → row flagged; setting chip value clears the flag.
- **Override:** `overrides.file_af12.PRODUCER = 'X'` updates only that row's preview; other rows unchanged.
- **Download gate:** button disabled while any row has a warning; enables when all cleared.
- **localStorage migration:** v1 state (no `overrides`) loads with `overrides: {}`; subsequent save is v2.

### Manual smoke (documented in spec)

- Drag-by-grip in Chrome, Safari, Firefox → chip lands at drop location; state matches visual order.
- Keyboard-only session: Tab to chip, Alt+→ reorders, preview updates live.
- Per-file edit: open override on one row, type a value, blur → preview reflects override; other rows unchanged; backend receives `overrides` map.

## Files changed

| File | Change |
|---|---|
| `frontend/templates/app.html` | Remove wizard scaffolding, Step 2/3 forms, per-file panel, continue buttons; new single-page layout with sticky Name Line and preview table. |
| `frontend/static/js/name-line.js` | Remove pointer-drag (~80 lines); add diff-renderer; SortableJS integration; grip + arrow + keyboard handlers; overrides state. |
| `frontend/static/js/preview.js` | **New.** Renders file table, warnings, overrides, download gate. |
| `frontend/static/css/name-line.css` | Grip, arrow button, ghost class, focus-visible styles, preview row styles, warning row, sticky positioning. |
| `frontend/static/vendor/sortable.min.js` | **New.** Vendored library. |
| `backend/app/services/name_line.py` | Accept + apply `overrides` map in resolution order. |
| `backend/app/routes/` (rename route) | Accept optional `overrides` field on request payload. |
| `tests/test_name_line_render.py` | Override tests + backward-compat guard. |
| `tests/frontend/name-line.test.js` | **New.** Frontend test harness. |

## Out of scope (explicit)

- Saving / recalling named Name Line presets.
- Mobile-optimized touch drag (grip helps; full polish is a later pass).
- Sharing Name Line configs between users.
- Restoring casing or cleanup as visible UI (power-user setting in user profile is future work).
- Rebuilding `name-line.js` into separate modules (`state.js`, `chip.js`, etc.) — considered and rejected as scope creep for this change.
