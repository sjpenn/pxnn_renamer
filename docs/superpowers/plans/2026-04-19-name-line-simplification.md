# Name Line Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken pointer-drag in the Name Line with SortableJS (grip-handled) + arrow buttons + keyboard reorder, collapse the 3-step wizard into one scrolling page with inline warnings on a preview table, and drop the casing/cleanup UI in favor of baked-in defaults.

**Architecture:** The backend already accepts per-file overrides (`file_overrides_json` form field on `/api/wizard/preview`) — no backend changes are needed for overrides resolution. This plan is almost entirely frontend: vendored SortableJS, a diff-renderer that preserves DOM identity (so Sortable and re-render don't fight), grip-only drag source (removes the click/drag race that breaks the current reorder), and a new preview module that replaces the per-file metadata editor list. The 3-step wizard becomes a single scrolling layout with a sticky Name Line above a preview table of all files.

**Tech Stack:** FastAPI backend (Python 3.14), HTMX + Jinja2 templates, vanilla JS IIFE modules, Tailwind CSS, SortableJS (new vendored dep, ~13 KB gzipped). Testing: pytest backend, Node+jsdom for pure-function frontend tests, manual smoke for UI.

**Spec:** [`docs/superpowers/specs/2026-04-19-name-line-simplification-design.md`](../specs/2026-04-19-name-line-simplification-design.md)

---

## Prerequisites

- Working tree clean; branch off `main`.
- `docker-compose up --build` starts the app at `http://localhost:8000/app`.
- `pytest` runs from repo root.
- Node 18+ installed for the frontend test harness (Task 3 creates it).

---

## Task 1: Vendor SortableJS

**Files:**
- Create: `frontend/static/vendor/sortable.min.js`
- Create: `frontend/static/vendor/README.md`
- Modify: `frontend/templates/app.html:9` (add `<script>` tag above name-line.js load)

- [ ] **Step 1: Download SortableJS into the repo**

Run:
```bash
mkdir -p frontend/static/vendor
curl -fsSL https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js \
  -o frontend/static/vendor/sortable.min.js
```

Expected: a ~45 KB file (unminified source is larger; this is the min build). Verify with `wc -c frontend/static/vendor/sortable.min.js` (≈ 45000 bytes).

- [ ] **Step 2: Record the source in a tiny README**

Create `frontend/static/vendor/README.md`:

```markdown
# Vendored Frontend Libraries

- **sortable.min.js** — SortableJS v1.15.2
  Source: https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js
  License: MIT (https://github.com/SortableJS/Sortable/blob/master/LICENSE)
  Used by: `frontend/static/js/name-line.js` for drag-reorder of chips.
```

- [ ] **Step 3: Load the script in app.html above name-line.js**

Current [app.html:8-9](frontend/templates/app.html:8):

```html
<link rel="stylesheet" href="{{ url_for('static', path='/css/name-line.css') }}?v=name-line-4">
<script src="{{ url_for('static', path='/js/name-line.js') }}?v=name-line-4"></script>
```

Change to:

```html
<link rel="stylesheet" href="{{ url_for('static', path='/css/name-line.css') }}?v=name-line-5">
<script src="{{ url_for('static', path='/vendor/sortable.min.js') }}"></script>
<script src="{{ url_for('static', path='/js/name-line.js') }}?v=name-line-5"></script>
```

Note: cache-buster bumped to `name-line-5` everywhere in this plan.

- [ ] **Step 4: Verify Sortable loads**

Start the app (`docker-compose up`), open `http://localhost:8000/app`, open DevTools console, run:

```js
typeof Sortable
```

Expected: `"function"`.

- [ ] **Step 5: Commit**

```bash
git add frontend/static/vendor/ frontend/templates/app.html
git commit -m "feat(name-line): vendor SortableJS 1.15.2"
```

---

## Task 2: Set up Node + jsdom test harness for frontend pure-function tests

**Files:**
- Create: `tests/frontend/package.json`
- Create: `tests/frontend/name-line.test.js`
- Create: `tests/frontend/run-frontend-tests.sh`

The existing `frontend/static/js/name-line.js` is an IIFE that attaches to `window.NameLine`. We'll load it into a jsdom VM context to unit-test pure functions (state, serialize, normalize) and DOM-touching helpers (diff-renderer, chip render) without a real browser.

- [ ] **Step 1: Create the harness manifest**

Create `tests/frontend/package.json`:

```json
{
  "name": "name-line-frontend-tests",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "test": "node name-line.test.js"
  },
  "dependencies": {
    "jsdom": "^24.0.0"
  }
}
```

- [ ] **Step 2: Create the test file with one seed test**

Create `tests/frontend/name-line.test.js`:

```js
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { JSDOM } = require("jsdom");

const JS_PATH = path.join(__dirname, "..", "..", "frontend", "static", "js", "name-line.js");
const SOURCE = fs.readFileSync(JS_PATH, "utf8");

function loadNameLine() {
  const dom = new JSDOM("<!doctype html><html><body></body></html>", { runScripts: "outside-only" });
  const context = dom.getInternalVMContext();
  vm.runInContext(SOURCE, context);
  return { dom, NameLine: dom.window.NameLine };
}

const results = [];
function test(name, fn) {
  try {
    fn();
    results.push({ name, ok: true });
  } catch (err) {
    results.push({ name, ok: false, err });
  }
}

function assertEqual(actual, expected, msg) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a !== e) throw new Error(`${msg || "not equal"}: expected ${e} got ${a}`);
}

// Seed test — proves harness works.
test("NameLine module loads and exposes createState", () => {
  const { NameLine } = loadNameLine();
  if (typeof NameLine.createState !== "function") {
    throw new Error("createState missing");
  }
});

// Report.
for (const r of results) {
  console.log(`${r.ok ? "PASS" : "FAIL"}  ${r.name}`);
  if (!r.ok) console.error(r.err);
}
const failed = results.filter((r) => !r.ok).length;
process.exit(failed ? 1 : 0);
```

- [ ] **Step 3: Create a convenience runner**

Create `tests/frontend/run-frontend-tests.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d node_modules ]; then
  npm install --silent
fi
npm test
```

Make it executable:

```bash
chmod +x tests/frontend/run-frontend-tests.sh
```

- [ ] **Step 4: Run the harness to verify it works**

```bash
./tests/frontend/run-frontend-tests.sh
```

Expected output:
```
PASS  NameLine module loads and exposes createState
```

Exit code 0.

- [ ] **Step 5: Commit**

```bash
git add tests/frontend/
git commit -m "test(name-line): add node+jsdom frontend test harness"
```

---

## Task 3: Add diff-renderer (test-first)

**Files:**
- Modify: `frontend/static/js/name-line.js:292-312` (replace `renderLine()`)
- Modify: `tests/frontend/name-line.test.js` (add diff-render tests)

The current `renderLine()` does `lineEl.innerHTML = ""` then re-creates every chip. This destroys SortableJS's DOM bookkeeping during a drag and wipes keyboard focus on every state change. Replace with a diff-render that preserves chip DOM nodes by `data-block-id`.

- [ ] **Step 1: Write failing tests for diff-render identity preservation**

Append to `tests/frontend/name-line.test.js` (before the report block):

```js
test("diff-render keeps existing chip nodes when state order stays the same", () => {
  const { dom, NameLine } = loadNameLine();
  const line = dom.window.document.createElement("div");
  const blocks = [
    { id: "b1", type: "ARTIST", value: "A" },
    { id: "b2", type: "TITLE" },
    { id: "b3", type: "PRODUCER", value: "P" },
  ];
  NameLine.diffRenderLine(line, blocks, { onRemove() {}, onEdit() {} });
  const firstChips = Array.from(line.children);
  NameLine.diffRenderLine(line, blocks, { onRemove() {}, onEdit() {} });
  const secondChips = Array.from(line.children);
  for (let i = 0; i < firstChips.length; i++) {
    if (firstChips[i] !== secondChips[i]) {
      throw new Error(`chip at index ${i} was replaced, should be preserved`);
    }
  }
});

test("diff-render reorders existing chip nodes when state order changes", () => {
  const { dom, NameLine } = loadNameLine();
  const line = dom.window.document.createElement("div");
  const blocks = [
    { id: "b1", type: "ARTIST", value: "A" },
    { id: "b2", type: "TITLE" },
    { id: "b3", type: "PRODUCER", value: "P" },
  ];
  NameLine.diffRenderLine(line, blocks, { onRemove() {}, onEdit() {} });
  const originalB1 = line.querySelector('[data-block-id="b1"]');
  const originalB3 = line.querySelector('[data-block-id="b3"]');
  const reordered = [blocks[2], blocks[0], blocks[1]];
  NameLine.diffRenderLine(line, reordered, { onRemove() {}, onEdit() {} });
  const afterB3 = line.querySelector('[data-block-id="b3"]');
  const afterB1 = line.querySelector('[data-block-id="b1"]');
  if (afterB3 !== originalB3) throw new Error("b3 node was replaced");
  if (afterB1 !== originalB1) throw new Error("b1 node was replaced");
  if (line.children[0] !== originalB3) throw new Error("b3 not in position 0");
  if (line.children[1] !== originalB1) throw new Error("b1 not in position 1");
});

test("diff-render adds new chips and removes missing ones", () => {
  const { dom, NameLine } = loadNameLine();
  const line = dom.window.document.createElement("div");
  NameLine.diffRenderLine(line, [{ id: "b1", type: "TITLE" }], { onRemove() {}, onEdit() {} });
  if (line.children.length !== 1) throw new Error("initial render wrong");
  NameLine.diffRenderLine(
    line,
    [{ id: "b1", type: "TITLE" }, { id: "b2", type: "BPM" }],
    { onRemove() {}, onEdit() {} }
  );
  if (line.children.length !== 2) throw new Error("add failed");
  NameLine.diffRenderLine(line, [{ id: "b2", type: "BPM" }], { onRemove() {}, onEdit() {} });
  if (line.children.length !== 1) throw new Error("remove failed");
  if (line.children[0].dataset.blockId !== "b2") throw new Error("wrong chip left");
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
./tests/frontend/run-frontend-tests.sh
```

Expected: 3 new FAIL lines with `diffRenderLine is not a function`.

- [ ] **Step 3: Implement `diffRenderLine` inside the IIFE**

In `frontend/static/js/name-line.js`, locate the existing `renderChip` function (line ~84) and add this new function directly after it:

```js
function diffRenderLine(lineEl, blocks, handlers) {
  const existingById = new Map();
  Array.from(lineEl.children).forEach((child) => {
    const id = child.dataset.blockId;
    if (id) existingById.set(id, child);
  });

  const desiredIds = new Set(blocks.map((b) => b.id));
  existingById.forEach((chip, id) => {
    if (!desiredIds.has(id)) chip.remove();
  });

  blocks.forEach((block, index) => {
    let chip = existingById.get(block.id);
    if (chip) {
      const meta = TOKEN_CATEGORIES[block.type];
      if (meta && meta.hasValue) {
        const valueNode = chip.querySelector(".nl-chip-value");
        if (valueNode) {
          const newText = block.value || (meta.literal ? "…" : "empty");
          if (valueNode.textContent !== newText) valueNode.textContent = newText;
        }
        if (!block.value) chip.dataset.empty = "true";
        else delete chip.dataset.empty;
      }
    } else {
      chip = renderChip(block, handlers);
    }
    const currentAtIndex = lineEl.children[index];
    if (currentAtIndex !== chip) lineEl.insertBefore(chip, currentAtIndex || null);
  });
}
```

- [ ] **Step 4: Expose `diffRenderLine` on `window.NameLine`**

Find the `window.NameLine = { ... }` export at the bottom of the file (line ~457) and add `diffRenderLine`:

```js
window.NameLine = {
  TOKEN_CATEGORIES,
  DEFAULT_BLOCKS,
  createState,
  serialize,
  loadPersisted,
  persist,
  newId,
  normalizeBlock,
  renderChip,
  renderPalette,
  renderLegend,
  openEditor,
  fetchSuggestions,
  diffRenderLine,
  mount,
};
```

- [ ] **Step 5: Replace the existing `renderLine` body to delegate to diff-render**

Locate `renderLine()` at [name-line.js:292-312](frontend/static/js/name-line.js:292). Replace the entire function with:

```js
function renderLine() {
  diffRenderLine(lineEl, state.blocks, {
    onRemove(id) {
      state.blocks = state.blocks.filter((b) => b.id !== id);
      rerender();
    },
    onEdit(id, chipEl) {
      const target = state.blocks.find((b) => b.id === id);
      if (!target) return;
      openEditor(chipEl, target, (newValue) => {
        target.value = newValue;
        rerender();
      });
    },
  });
}
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
./tests/frontend/run-frontend-tests.sh
```

Expected: all 4 tests PASS (seed + 3 new).

- [ ] **Step 7: Commit**

```bash
git add frontend/static/js/name-line.js tests/frontend/name-line.test.js
git commit -m "feat(name-line): diff-render preserves chip DOM identity"
```

---

## Task 4: Remove pointer-based drag code

**Files:**
- Modify: `frontend/static/js/name-line.js` (remove lines ~314-412)

The existing pointer-drag is broken (click-after-pointerup races openEditor). We remove it entirely before wiring SortableJS.

- [ ] **Step 1: Delete the pointer-drag block**

In `frontend/static/js/name-line.js`, remove the entire section from the comment `// Pointer-based drag-and-drop` through the end of `attachDrag`. Specifically, delete:

- `const DRAG_THRESHOLD_PX = 4;` and `let drag = null;`
- function `clearDropIndicators`
- function `insertionTargetFromPoint`
- function `onPointerMove`
- function `onPointerUp`
- function `attachDrag`

These live roughly at [name-line.js:314-412](frontend/static/js/name-line.js:314). After deletion, the function directly above `renderLine` should be `openEditor`, and the function directly below the new `renderLine` (from Task 3) should be the `mount()` function.

- [ ] **Step 2: Remove the now-dead `attachDrag(chip)` call**

The previous `renderLine()` had `attachDrag(chip); lineEl.appendChild(chip);` — Task 3 already replaced that body. Double-check no other callers of `attachDrag` remain:

```bash
grep -n "attachDrag\|onPointerMove\|onPointerUp\|insertionTargetFromPoint\|clearDropIndicators\|DRAG_THRESHOLD_PX" frontend/static/js/name-line.js
```

Expected: zero results.

- [ ] **Step 3: Remove `.nl-dragging`, `.nl-drop-before`, `.nl-drop-after` from name-line.css**

In `frontend/static/css/name-line.css`, delete lines 37 (`.nl-chip.nl-dragging { ... }`), 70, and 71:

```css
.nl-chip.nl-dragging { cursor: grabbing; }
...
.nl-drop-before { box-shadow: -2px 0 0 0 #cc7044; }
.nl-drop-after  { box-shadow:  2px 0 0 0 #cc7044; }
```

(We'll add Sortable's replacement classes in Task 5.)

- [ ] **Step 4: Verify the app still loads (drag will be broken, expected)**

Reload `http://localhost:8000/app`. Open Step 2. The Name Line should render; chips should be editable and removable; drag does nothing. No console errors.

- [ ] **Step 5: Run frontend tests to confirm nothing regressed**

```bash
./tests/frontend/run-frontend-tests.sh
```

Expected: all 4 tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/static/js/name-line.js frontend/static/css/name-line.css
git commit -m "refactor(name-line): remove broken pointer-drag implementation"
```

---

## Task 5: Wire SortableJS with grip handle

**Files:**
- Modify: `frontend/static/js/name-line.js` (add grip to renderChip; init Sortable in mount)
- Modify: `frontend/static/css/name-line.css` (grip + ghost styles)
- Modify: `tests/frontend/name-line.test.js` (grip presence + click-edit isolation)

- [ ] **Step 1: Write failing test — grip exists and has expected class**

Append to `tests/frontend/name-line.test.js`:

```js
test("renderChip produces a .nl-grip handle at the front of the chip", () => {
  const { dom, NameLine } = loadNameLine();
  const block = { id: "b1", type: "ARTIST", value: "A" };
  const chip = NameLine.renderChip(block, { onRemove() {}, onEdit() {} });
  const grip = chip.querySelector(".nl-grip");
  if (!grip) throw new Error("grip missing");
  if (chip.firstElementChild !== grip) throw new Error("grip is not first child");
});

test("clicking the grip does not trigger onEdit", () => {
  const { dom, NameLine } = loadNameLine();
  let edited = false;
  const block = { id: "b1", type: "ARTIST", value: "A" };
  const chip = NameLine.renderChip(block, { onRemove() {}, onEdit() { edited = true; } });
  dom.window.document.body.appendChild(chip);
  const grip = chip.querySelector(".nl-grip");
  grip.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  if (edited) throw new Error("onEdit fired when grip was clicked");
});

test("clicking the chip body (not grip, not remove) triggers onEdit", () => {
  const { dom, NameLine } = loadNameLine();
  let edited = false;
  const block = { id: "b1", type: "ARTIST", value: "A" };
  const chip = NameLine.renderChip(block, { onRemove() {}, onEdit() { edited = true; } });
  const valueNode = chip.querySelector(".nl-chip-value");
  valueNode.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  if (!edited) throw new Error("onEdit should fire on chip body click");
});
```

- [ ] **Step 2: Run tests to verify failures**

```bash
./tests/frontend/run-frontend-tests.sh
```

Expected: 3 new FAILs (`grip missing`, `onEdit fired when grip was clicked` or similar).

- [ ] **Step 3: Add grip to renderChip**

In `frontend/static/js/name-line.js`, find `renderChip` (around line 84). Locate the first block where `chip` is configured — after `chip.dataset.blockType = block.type;`. Insert the grip as the **first child** before the swatch:

```js
const grip = document.createElement("span");
grip.className = "material-symbols-outlined nl-grip";
grip.textContent = "drag_indicator";
grip.setAttribute("aria-label", "Drag to reorder");
grip.addEventListener("click", (e) => e.stopPropagation());
chip.appendChild(grip);
```

Move this `chip.appendChild(grip)` to execute **before** the existing `chip.appendChild(swatch)` line. The resulting order: grip → swatch → icon → label/value → remove button.

- [ ] **Step 4: Update the click handler on chip to ignore grip clicks**

Find the existing click listener on `chip` inside `renderChip`:

```js
chip.addEventListener("click", (event) => {
  if (event.target.classList.contains("nl-chip-remove")) return;
  handlers.onEdit(block.id, chip);
});
```

Replace with:

```js
chip.addEventListener("click", (event) => {
  const t = event.target;
  if (t.closest(".nl-chip-remove")) return;
  if (t.closest(".nl-grip")) return;
  if (t.closest(".nl-chip-arrow")) return;
  handlers.onEdit(block.id, chip);
});
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
./tests/frontend/run-frontend-tests.sh
```

Expected: all 7 tests PASS.

- [ ] **Step 6: Add grip + ghost styles to CSS**

Add to `frontend/static/css/name-line.css`:

```css
.nl-chip .nl-grip {
  font-size: 14px;
  cursor: grab;
  opacity: 0.45;
  margin-right: 2px;
  user-select: none;
  touch-action: none;
}
.nl-chip .nl-grip:hover { opacity: 0.85; }
.nl-chip.nl-ghost {
  opacity: 0.35;
  border: 1px dashed #cc7044;
}
.sortable-chosen { cursor: grabbing; }
```

- [ ] **Step 7: Initialize Sortable in `mount()`**

In `frontend/static/js/name-line.js`, locate `mount()` (around line 271). After the `state` is created and before `rerender()`, add:

```js
const sortable = (typeof Sortable !== "undefined" && Sortable.create)
  ? Sortable.create(lineEl, {
      handle: ".nl-grip",
      animation: 150,
      ghostClass: "nl-ghost",
      onEnd(evt) {
        if (evt.oldIndex === evt.newIndex) return;
        const [moved] = state.blocks.splice(evt.oldIndex, 1);
        state.blocks.splice(evt.newIndex, 0, moved);
        rerender();
      },
    })
  : null;
```

Place this right before the final `rerender();` call at the end of `mount()`.

- [ ] **Step 8: Manual smoke — drag by grip**

Reload `http://localhost:8000/app`, open Step 2. Hover a chip — grip appears slightly dimmed. Drag the grip of the first chip to the right past the second chip. Release. The chips should swap. The preview (wherever it's shown) should reflect the new order. Repeat for each chip type.

**Known remaining regressions:** arrow buttons and keyboard reorder not yet added (Tasks 6, 7). That's fine for now.

- [ ] **Step 9: Commit**

```bash
git add frontend/static/js/name-line.js frontend/static/css/name-line.css tests/frontend/name-line.test.js
git commit -m "feat(name-line): grip-handled SortableJS drag replaces pointer-drag"
```

---

## Task 6: Arrow buttons for reorder

**Files:**
- Modify: `frontend/static/js/name-line.js` (renderChip: add ◀ ▶ buttons; wire handlers)
- Modify: `frontend/static/css/name-line.css` (arrow styles)
- Modify: `tests/frontend/name-line.test.js` (arrow behavior tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/frontend/name-line.test.js`:

```js
test("renderChip renders left/right arrow buttons", () => {
  const { NameLine } = loadNameLine();
  const chip = NameLine.renderChip(
    { id: "b1", type: "TITLE" },
    { onRemove() {}, onEdit() {}, onMoveLeft() {}, onMoveRight() {} }
  );
  if (!chip.querySelector(".nl-chip-arrow-left")) throw new Error("left arrow missing");
  if (!chip.querySelector(".nl-chip-arrow-right")) throw new Error("right arrow missing");
});

test("clicking left arrow calls onMoveLeft with block id", () => {
  const { dom, NameLine } = loadNameLine();
  let movedId = null;
  const chip = NameLine.renderChip(
    { id: "b1", type: "TITLE" },
    { onRemove() {}, onEdit() {}, onMoveLeft(id) { movedId = id; }, onMoveRight() {} }
  );
  chip.querySelector(".nl-chip-arrow-left").dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  if (movedId !== "b1") throw new Error("onMoveLeft not fired with id");
});

test("clicking right arrow calls onMoveRight with block id", () => {
  const { dom, NameLine } = loadNameLine();
  let movedId = null;
  const chip = NameLine.renderChip(
    { id: "b1", type: "TITLE" },
    { onRemove() {}, onEdit() {}, onMoveLeft() {}, onMoveRight(id) { movedId = id; } }
  );
  chip.querySelector(".nl-chip-arrow-right").dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  if (movedId !== "b1") throw new Error("onMoveRight not fired with id");
});

test("click on arrow does not bubble to chip (no edit)", () => {
  const { dom, NameLine } = loadNameLine();
  let edited = false;
  const chip = NameLine.renderChip(
    { id: "b1", type: "TITLE" },
    { onRemove() {}, onEdit() { edited = true; }, onMoveLeft() {}, onMoveRight() {} }
  );
  chip.querySelector(".nl-chip-arrow-right").dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  if (edited) throw new Error("edit fired on arrow click");
});
```

- [ ] **Step 2: Run tests to verify failures**

```bash
./tests/frontend/run-frontend-tests.sh
```

Expected: 4 new FAILs.

- [ ] **Step 3: Add arrow buttons to renderChip**

In `renderChip`, after the remove button (`removeBtn`) is appended, insert the arrows before `removeBtn`:

Locate this block in `renderChip`:

```js
const removeBtn = document.createElement("button");
removeBtn.type = "button";
removeBtn.className = "nl-chip-remove";
removeBtn.textContent = "×";
removeBtn.addEventListener("click", (event) => {
  event.stopPropagation();
  handlers.onRemove(block.id);
});
chip.appendChild(removeBtn);
```

**Before** that block, add:

```js
const arrowLeft = document.createElement("button");
arrowLeft.type = "button";
arrowLeft.className = "nl-chip-arrow nl-chip-arrow-left";
arrowLeft.textContent = "◀";
arrowLeft.setAttribute("aria-label", "Move left");
arrowLeft.addEventListener("click", (event) => {
  event.stopPropagation();
  if (typeof handlers.onMoveLeft === "function") handlers.onMoveLeft(block.id);
});
chip.appendChild(arrowLeft);

const arrowRight = document.createElement("button");
arrowRight.type = "button";
arrowRight.className = "nl-chip-arrow nl-chip-arrow-right";
arrowRight.textContent = "▶";
arrowRight.setAttribute("aria-label", "Move right");
arrowRight.addEventListener("click", (event) => {
  event.stopPropagation();
  if (typeof handlers.onMoveRight === "function") handlers.onMoveRight(block.id);
});
chip.appendChild(arrowRight);
```

- [ ] **Step 4: Wire onMoveLeft / onMoveRight handlers in the IIFE's renderLine**

Update `renderLine()` (created in Task 3) to pass the new handlers:

```js
function renderLine() {
  diffRenderLine(lineEl, state.blocks, {
    onRemove(id) {
      state.blocks = state.blocks.filter((b) => b.id !== id);
      rerender();
    },
    onEdit(id, chipEl) {
      const target = state.blocks.find((b) => b.id === id);
      if (!target) return;
      openEditor(chipEl, target, (newValue) => {
        target.value = newValue;
        rerender();
      });
    },
    onMoveLeft(id) { moveBlock(id, -1); },
    onMoveRight(id) { moveBlock(id, 1); },
  });
  updateArrowDisabled();
}

function moveBlock(id, delta) {
  const idx = state.blocks.findIndex((b) => b.id === id);
  if (idx < 0) return;
  const target = idx + delta;
  if (target < 0 || target >= state.blocks.length) return;
  const [moved] = state.blocks.splice(idx, 1);
  state.blocks.splice(target, 0, moved);
  rerender();
}

function updateArrowDisabled() {
  const chips = Array.from(lineEl.children);
  chips.forEach((chip, index) => {
    const left = chip.querySelector(".nl-chip-arrow-left");
    const right = chip.querySelector(".nl-chip-arrow-right");
    if (left) left.toggleAttribute("disabled", index === 0);
    if (right) right.toggleAttribute("disabled", index === chips.length - 1);
  });
}
```

Place `moveBlock` and `updateArrowDisabled` inside `mount()`, directly after `renderLine`.

- [ ] **Step 5: Add arrow CSS**

Append to `frontend/static/css/name-line.css`:

```css
.nl-chip .nl-chip-arrow {
  border: none;
  background: transparent;
  font-size: 10px;
  padding: 0 3px;
  cursor: pointer;
  opacity: 0.55;
  color: inherit;
  line-height: 1;
}
.nl-chip .nl-chip-arrow:hover { opacity: 1; }
.nl-chip .nl-chip-arrow[disabled] {
  opacity: 0.15;
  cursor: not-allowed;
}
```

- [ ] **Step 6: Run tests to verify**

```bash
./tests/frontend/run-frontend-tests.sh
```

Expected: 11 tests PASS.

- [ ] **Step 7: Manual smoke**

Reload app. Each chip shows ◀ ▶ buttons between the label and ×. Click ◀ on second chip → swaps with first. Click ▶ on last chip — disabled (no effect). First chip's ◀ is disabled.

- [ ] **Step 8: Commit**

```bash
git add frontend/static/js/name-line.js frontend/static/css/name-line.css tests/frontend/name-line.test.js
git commit -m "feat(name-line): arrow reorder buttons on every chip"
```

---

## Task 7: Keyboard reorder (Alt+←/→, Enter, Delete)

**Files:**
- Modify: `frontend/static/js/name-line.js` (renderChip: tabindex + keydown; focus-visible styles)
- Modify: `frontend/static/css/name-line.css` (focus-ring)
- Modify: `tests/frontend/name-line.test.js` (keydown tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/frontend/name-line.test.js`:

```js
test("renderChip is focusable via tabindex=0", () => {
  const { NameLine } = loadNameLine();
  const chip = NameLine.renderChip({ id: "b1", type: "TITLE" }, { onRemove() {}, onEdit() {} });
  if (chip.getAttribute("tabindex") !== "0") throw new Error("tabindex=0 missing");
});

test("Alt+ArrowRight on focused chip calls onMoveRight", () => {
  const { dom, NameLine } = loadNameLine();
  let movedId = null;
  const chip = NameLine.renderChip(
    { id: "b1", type: "TITLE" },
    { onRemove() {}, onEdit() {}, onMoveLeft() {}, onMoveRight(id) { movedId = id; } }
  );
  dom.window.document.body.appendChild(chip);
  const evt = new dom.window.KeyboardEvent("keydown", { key: "ArrowRight", altKey: true, bubbles: true });
  chip.dispatchEvent(evt);
  if (movedId !== "b1") throw new Error("onMoveRight not fired");
});

test("Alt+ArrowLeft on focused chip calls onMoveLeft", () => {
  const { dom, NameLine } = loadNameLine();
  let movedId = null;
  const chip = NameLine.renderChip(
    { id: "b1", type: "TITLE" },
    { onRemove() {}, onEdit() {}, onMoveLeft(id) { movedId = id; }, onMoveRight() {} }
  );
  dom.window.document.body.appendChild(chip);
  const evt = new dom.window.KeyboardEvent("keydown", { key: "ArrowLeft", altKey: true, bubbles: true });
  chip.dispatchEvent(evt);
  if (movedId !== "b1") throw new Error("onMoveLeft not fired");
});

test("Delete on focused chip calls onRemove", () => {
  const { dom, NameLine } = loadNameLine();
  let removedId = null;
  const chip = NameLine.renderChip(
    { id: "b1", type: "TITLE" },
    { onRemove(id) { removedId = id; }, onEdit() {} }
  );
  dom.window.document.body.appendChild(chip);
  chip.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "Delete", bubbles: true }));
  if (removedId !== "b1") throw new Error("onRemove not fired");
});

test("ArrowRight without Alt on focused chip does NOT call onMoveRight", () => {
  const { dom, NameLine } = loadNameLine();
  let moved = false;
  const chip = NameLine.renderChip(
    { id: "b1", type: "TITLE" },
    { onRemove() {}, onEdit() {}, onMoveLeft() {}, onMoveRight() { moved = true; } }
  );
  dom.window.document.body.appendChild(chip);
  chip.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
  if (moved) throw new Error("onMoveRight fired without Alt");
});
```

- [ ] **Step 2: Run tests to verify failures**

```bash
./tests/frontend/run-frontend-tests.sh
```

Expected: 5 new FAILs.

- [ ] **Step 3: Make chip focusable + add keydown handler**

In `renderChip`, after `chip.dataset.blockType = block.type;`, add:

```js
chip.setAttribute("tabindex", "0");
chip.addEventListener("keydown", (event) => {
  if (event.target !== chip) return; // ignore keys from inner input
  if (event.key === "ArrowLeft" && event.altKey) {
    event.preventDefault();
    if (typeof handlers.onMoveLeft === "function") handlers.onMoveLeft(block.id);
  } else if (event.key === "ArrowRight" && event.altKey) {
    event.preventDefault();
    if (typeof handlers.onMoveRight === "function") handlers.onMoveRight(block.id);
  } else if (event.key === "Delete" || event.key === "Backspace") {
    event.preventDefault();
    handlers.onRemove(block.id);
  } else if (event.key === "Enter") {
    event.preventDefault();
    const meta = TOKEN_CATEGORIES[block.type];
    if (meta && meta.hasValue) handlers.onEdit(block.id, chip);
  }
});
```

- [ ] **Step 4: Add focus-visible style**

Append to `frontend/static/css/name-line.css`:

```css
.nl-chip:focus-visible {
  outline: 2px solid var(--cyan, #0bb7c4);
  outline-offset: 2px;
}
```

- [ ] **Step 5: Run tests to verify**

```bash
./tests/frontend/run-frontend-tests.sh
```

Expected: all 16 tests PASS.

- [ ] **Step 6: Manual smoke**

Reload app. Tab until a chip is focused (cyan outline). Alt+Right → moves right one. Alt+Left → moves back. Delete → chip removed. Enter on an ARTIST chip → edit mode.

- [ ] **Step 7: Commit**

```bash
git add frontend/static/js/name-line.js frontend/static/css/name-line.css tests/frontend/name-line.test.js
git commit -m "feat(name-line): keyboard reorder (Alt+←/→), Enter edit, Delete remove"
```

---

## Task 8: localStorage v1 → v2 migration (add overrides to state)

**Files:**
- Modify: `frontend/static/js/name-line.js` (STORAGE_KEY, createState, persist, loadPersisted)
- Modify: `tests/frontend/name-line.test.js` (migration + persist tests)

This adds `overrides` to the Name Line state. Existing sites running v1 continue to work. Per-file edits are intentionally kept in a separate place later (Task 10) — this task only prepares state shape.

- [ ] **Step 1: Write failing tests**

Append to `tests/frontend/name-line.test.js`:

```js
test("createState defaults overrides to empty object", () => {
  const { NameLine } = loadNameLine();
  const s = NameLine.createState();
  assertEqual(s.overrides, {}, "overrides default");
});

test("createState preserves overrides when passed", () => {
  const { NameLine } = loadNameLine();
  const s = NameLine.createState({ blocks: [], globalSeparator: "_", overrides: { f1: { artist: "x" } } });
  assertEqual(s.overrides, { f1: { artist: "x" } }, "overrides preserved");
});

test("loadPersisted migrates v1 shape (no overrides key) by attaching empty overrides via createState", () => {
  const { dom, NameLine } = loadNameLine();
  dom.window.localStorage.setItem(
    "pxnn.nameLine.v1",
    JSON.stringify({ blocks: [{ type: "TITLE" }], globalSeparator: "_" })
  );
  const migrated = NameLine.loadPersisted();
  if (!migrated) throw new Error("no migration result");
  assertEqual(migrated.overrides, {}, "migrated overrides");
  assertEqual(migrated.blocks[0].type, "TITLE", "blocks carried over");
});
```

- [ ] **Step 2: Run tests to verify failures**

```bash
./tests/frontend/run-frontend-tests.sh
```

Expected: 3 new FAILs.

- [ ] **Step 3: Update `createState` to accept overrides**

In `frontend/static/js/name-line.js`, replace `createState`:

```js
function createState(initial) {
  const rawBlocks = Array.isArray(initial && initial.blocks) ? initial.blocks : DEFAULT_BLOCKS;
  const blocks = rawBlocks.map(normalizeBlock).filter(Boolean);
  const globalSeparator = (initial && initial.globalSeparator) || "_";
  const overrides = (initial && initial.overrides && typeof initial.overrides === "object") ? initial.overrides : {};
  return { blocks, globalSeparator, overrides };
}
```

- [ ] **Step 4: Update `serialize` to include overrides**

Replace `serialize`:

```js
function serialize(state) {
  return {
    blocks: state.blocks.map((block) => {
      const meta = TOKEN_CATEGORIES[block.type];
      return meta && meta.hasValue
        ? { type: block.type, value: block.value || "" }
        : { type: block.type };
    }),
    global_separator: state.globalSeparator,
    overrides: state.overrides || {},
  };
}
```

- [ ] **Step 5: Update `loadPersisted` to read from v2 but migrate v1**

Replace the existing `STORAGE_KEY` line and `loadPersisted` / `persist`:

```js
const STORAGE_KEY = "pxnn.nameLine.v2";
const LEGACY_STORAGE_KEYS = ["pxnn.nameLine.v1"];

function loadPersisted() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
    for (const legacy of LEGACY_STORAGE_KEYS) {
      const legacyRaw = window.localStorage.getItem(legacy);
      if (legacyRaw) {
        const parsed = JSON.parse(legacyRaw);
        const migrated = {
          blocks: Array.isArray(parsed && parsed.blocks) ? parsed.blocks : DEFAULT_BLOCKS,
          globalSeparator: (parsed && parsed.globalSeparator) || "_",
          overrides: {},
        };
        try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(migrated)); } catch (_) {}
        return migrated;
      }
    }
    return null;
  } catch (_err) {
    return null;
  }
}
```

- [ ] **Step 6: Run tests**

```bash
./tests/frontend/run-frontend-tests.sh
```

Expected: all 19 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/static/js/name-line.js tests/frontend/name-line.test.js
git commit -m "feat(name-line): add overrides to state; migrate v1 localStorage to v2"
```

---

## Task 9: Preview module — file table with warnings

**Files:**
- Create: `frontend/static/js/preview.js`
- Create: `frontend/static/css/preview.css` (or append to `name-line.css`)
- Modify: `frontend/templates/app.html` (include `preview.js`)

The preview module is a separate IIFE that owns the file table beneath the Name Line. It exposes `window.Preview.mount(root, opts)`. It's self-contained: takes the current Name Line state + file list, renders one row per file, flags warnings, gates the download button.

For this task we build the module with warnings + download gate but without per-file override edit (Task 10 adds that).

- [ ] **Step 1: Create `frontend/static/js/preview.js`**

```js
(function () {
  "use strict";

  // Maps Name Line block types → backend field names (lowercase).
  const VALUE_TYPE_FIELD = { ARTIST: "artist", PRODUCER: "producers" };
  const SINGLETON_FIELDS = {
    TITLE: "title", MIX: "mix", VERSION: "version", BPM: "bpm",
    DATE: "date", KEY: "key", INDEX: "index",
  };

  function resolveForFile(block, file, overrides) {
    const perFile = overrides && overrides[file.id] ? overrides[file.id] : {};
    const blockType = String(block.type || "").toUpperCase();
    if (VALUE_TYPE_FIELD[blockType]) {
      const field = VALUE_TYPE_FIELD[blockType];
      return (perFile[field] || block.value || (file.fields && file.fields[field]) || "").trim();
    }
    if (SINGLETON_FIELDS[blockType]) {
      const field = SINGLETON_FIELDS[blockType];
      return (perFile[field] || (file.fields && file.fields[field]) || "").trim();
    }
    if (blockType === "TEXT") return String(block.value || "");
    return "";
  }

  function warningsForFile(nameLineState, file) {
    const warnings = [];
    (nameLineState.blocks || []).forEach((block) => {
      const t = String(block.type || "").toUpperCase();
      if (!VALUE_TYPE_FIELD[t] && t !== "TEXT") return;
      if (t === "TEXT") {
        if (!String(block.value || "").trim()) warnings.push("empty text block");
        return;
      }
      const val = resolveForFile(block, file, nameLineState.overrides || {});
      if (!val) warnings.push(`missing ${t.toLowerCase()}`);
    });
    return warnings;
  }

  function computeRenderedName(nameLineState, file) {
    const sep = nameLineState.globalSeparator || "_";
    const parts = [];
    let prevWasToken = false;
    (nameLineState.blocks || []).forEach((block) => {
      const t = String(block.type || "").toUpperCase();
      if (t === "TEXT") {
        const text = String(block.value || "");
        if (text) { parts.push(text); prevWasToken = false; }
        return;
      }
      const val = resolveForFile(block, file, nameLineState.overrides || {});
      if (!val) return;
      if (prevWasToken) parts.push(sep);
      parts.push(val);
      prevWasToken = true;
    });
    const stem = parts.join("");
    const ext = (file.fields && file.fields.ext) ? "." + String(file.fields.ext).toLowerCase() : "";
    return stem + ext;
  }

  function renderRow(file, nameLineState) {
    const warnings = warningsForFile(nameLineState, file);
    const row = document.createElement("div");
    row.className = "pv-row" + (warnings.length ? " pv-row-warn" : "");
    row.dataset.fileId = file.id;

    const nameEl = document.createElement("div");
    nameEl.className = "pv-name";
    nameEl.textContent = computeRenderedName(nameLineState, file) || "(empty)";
    row.appendChild(nameEl);

    if (warnings.length) {
      const warnEl = document.createElement("div");
      warnEl.className = "pv-warn";
      warnEl.textContent = "⚠ " + warnings.join(", ");
      row.appendChild(warnEl);
    }
    return row;
  }

  function mount(root, opts) {
    opts = opts || {};
    root.innerHTML = "";
    root.classList.add("pv-root");

    const header = document.createElement("div");
    header.className = "pv-header";
    const counter = document.createElement("div");
    counter.className = "pv-counter";
    const downloadBtn = document.createElement("button");
    downloadBtn.type = "button";
    downloadBtn.className = "pv-download";
    downloadBtn.textContent = "Download ZIP";
    downloadBtn.addEventListener("click", () => {
      if (typeof opts.onDownload === "function") opts.onDownload();
    });
    header.appendChild(counter);
    header.appendChild(downloadBtn);
    root.appendChild(header);

    const body = document.createElement("div");
    body.className = "pv-body";
    root.appendChild(body);

    let currentFiles = [];
    let currentState = { blocks: [], globalSeparator: "_", overrides: {} };

    function render() {
      body.innerHTML = "";
      let warnCount = 0;
      currentFiles.forEach((file) => {
        const row = renderRow(file, currentState);
        if (row.classList.contains("pv-row-warn")) warnCount++;
        body.appendChild(row);
      });
      const total = currentFiles.length;
      if (total === 0) {
        counter.textContent = "No files uploaded yet";
      } else if (warnCount === 0) {
        counter.textContent = `${total} files ready`;
      } else {
        counter.textContent = `${total} files · ${warnCount} need attention`;
      }
      const blocked = warnCount > 0 || total === 0;
      downloadBtn.toggleAttribute("disabled", blocked);
      downloadBtn.textContent = blocked
        ? (total === 0 ? "Upload files to download" : `Fix ${warnCount} issue${warnCount === 1 ? "" : "s"} to download`)
        : "Download ZIP";
    }

    let debounceTimer = null;
    function scheduleRender() {
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(render, 80);
    }

    return {
      setFiles(files) { currentFiles = Array.isArray(files) ? files : []; scheduleRender(); },
      setNameLineState(state) { currentState = state || currentState; scheduleRender(); },
      getDownloadButton() { return downloadBtn; },
      _renderNow: render, // exposed for tests
    };
  }

  window.Preview = {
    mount,
    resolveForFile,
    warningsForFile,
    computeRenderedName,
    renderRow,
  };
})();
```

- [ ] **Step 2: Add preview CSS (append to `frontend/static/css/name-line.css`)**

```css
.pv-root { margin-top: 18px; }
.pv-header { display: flex; align-items: center; justify-content: space-between; padding: 6px 0; font-size: 12px; color: var(--ink-dim, #6b6257); }
.pv-counter { font-weight: 600; }
.pv-download {
  padding: 8px 16px; border-radius: 10px; font-size: 12px; font-weight: 700;
  background: #cc7044; color: #fff; border: none; cursor: pointer;
}
.pv-download[disabled] { opacity: 0.5; cursor: not-allowed; }
.pv-body { max-height: 420px; overflow-y: auto; border: 1px solid var(--hairline, #dcd4c8); border-radius: 10px; background: #fff; }
.pv-row { display: flex; justify-content: space-between; gap: 12px; padding: 6px 10px; font-size: 12px; border-bottom: 1px solid #f3eee6; }
.pv-row:last-child { border-bottom: none; }
.pv-row-warn { border-left: 3px solid #cc4a3d; background: #fff4f2; }
.pv-name { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.pv-warn { color: #cc4a3d; font-weight: 600; }
```

- [ ] **Step 3: Add preview.js test — warning rule**

Append to `tests/frontend/name-line.test.js`:

```js
function loadPreview(dom) {
  const p = path.join(__dirname, "..", "..", "frontend", "static", "js", "preview.js");
  const src = fs.readFileSync(p, "utf8");
  vm.runInContext(src, dom.getInternalVMContext());
  return dom.window.Preview;
}

test("Preview: warning when ARTIST chip empty and file has no parsed artist", () => {
  const { dom } = loadNameLine();
  const Preview = loadPreview(dom);
  const state = {
    blocks: [{ id: "b1", type: "ARTIST", value: "" }],
    globalSeparator: "_",
    overrides: {},
  };
  const file = { id: "f1", fields: { artist: "", title: "t", ext: "MP3" } };
  const warnings = Preview.warningsForFile(state, file);
  if (!warnings.some((w) => w.includes("artist"))) throw new Error("expected artist warning");
});

test("Preview: no warning when ARTIST chip filled even if file has nothing", () => {
  const { dom } = loadNameLine();
  const Preview = loadPreview(dom);
  const state = {
    blocks: [{ id: "b1", type: "ARTIST", value: "Hurricane" }],
    globalSeparator: "_",
    overrides: {},
  };
  const file = { id: "f1", fields: { artist: "", ext: "MP3" } };
  const warnings = Preview.warningsForFile(state, file);
  if (warnings.length) throw new Error("should be clean");
});

test("Preview: override replaces chip value for a specific file", () => {
  const { dom } = loadNameLine();
  const Preview = loadPreview(dom);
  const state = {
    blocks: [{ id: "b1", type: "ARTIST", value: "Default" }],
    globalSeparator: "_",
    overrides: { f1: { artist: "OverrideName" } },
  };
  const file = { id: "f1", fields: { artist: "", ext: "MP3" } };
  const name = Preview.computeRenderedName(state, file);
  if (!name.startsWith("OverrideName")) throw new Error("override not applied: " + name);
});

test("Preview: singleton TITLE missing from file does NOT produce a warning", () => {
  const { dom } = loadNameLine();
  const Preview = loadPreview(dom);
  const state = {
    blocks: [{ id: "b1", type: "ARTIST", value: "A" }, { id: "b2", type: "TITLE" }],
    globalSeparator: "_",
    overrides: {},
  };
  const file = { id: "f1", fields: { title: "", ext: "MP3" } };
  const warnings = Preview.warningsForFile(state, file);
  if (warnings.length) throw new Error("singleton missing should not warn");
});
```

- [ ] **Step 4: Include preview.js in app.html**

In `frontend/templates/app.html:8-10`, after the `name-line.js` script tag, add:

```html
<script src="{{ url_for('static', path='/js/preview.js') }}?v=name-line-5"></script>
```

- [ ] **Step 5: Run tests**

```bash
./tests/frontend/run-frontend-tests.sh
```

Expected: all 23 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/static/js/preview.js frontend/static/css/name-line.css frontend/templates/app.html tests/frontend/name-line.test.js
git commit -m "feat(preview): file table module with warning rows and download gate"
```

---

## Task 10: Inline per-file override edit in preview rows

**Files:**
- Modify: `frontend/static/js/preview.js` (add ✎ edit control per row; update overrides on commit)
- Modify: `frontend/static/css/name-line.css` (edit form styles)
- Modify: `tests/frontend/name-line.test.js` (edit-commit updates overrides)

- [ ] **Step 1: Write failing tests**

Append to `tests/frontend/name-line.test.js`:

```js
test("Preview: clicking ✎ on a warning row opens an edit form with one input per value-bearing block", () => {
  const { dom } = loadNameLine();
  const Preview = loadPreview(dom);
  const root = dom.window.document.createElement("div");
  const ctrl = Preview.mount(root, { onOverrideChange() {} });
  ctrl.setFiles([{ id: "f1", fields: { artist: "", ext: "MP3" } }]);
  ctrl.setNameLineState({
    blocks: [{ id: "b1", type: "ARTIST", value: "" }, { id: "b2", type: "TITLE" }],
    globalSeparator: "_",
    overrides: {},
  });
  ctrl._renderNow();
  const editBtn = root.querySelector('.pv-row[data-file-id="f1"] .pv-edit');
  if (!editBtn) throw new Error("edit button missing on warning row");
  editBtn.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  const input = root.querySelector('.pv-row[data-file-id="f1"] input[data-field="artist"]');
  if (!input) throw new Error("artist input not rendered after edit click");
});

test("Preview: committing an edit calls onOverrideChange with file_id + field + value", () => {
  const { dom } = loadNameLine();
  const Preview = loadPreview(dom);
  const root = dom.window.document.createElement("div");
  let received = null;
  const ctrl = Preview.mount(root, {
    onOverrideChange(fileId, field, value) { received = { fileId, field, value }; },
  });
  ctrl.setFiles([{ id: "f1", fields: { artist: "", ext: "MP3" } }]);
  ctrl.setNameLineState({
    blocks: [{ id: "b1", type: "ARTIST", value: "" }],
    globalSeparator: "_",
    overrides: {},
  });
  ctrl._renderNow();
  root.querySelector('.pv-row[data-file-id="f1"] .pv-edit').dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  const input = root.querySelector('.pv-row[data-file-id="f1"] input[data-field="artist"]');
  input.value = "Hurricane Wisdom";
  input.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
  if (!received) throw new Error("onOverrideChange not called");
  assertEqual(received, { fileId: "f1", field: "artist", value: "Hurricane Wisdom" }, "override payload");
});
```

- [ ] **Step 2: Run tests to verify failures**

```bash
./tests/frontend/run-frontend-tests.sh
```

Expected: 2 new FAILs.

- [ ] **Step 3: Extend `renderRow` to add ✎ and wire an inline edit form**

Replace the existing `renderRow` function inside `preview.js` with:

```js
function renderRow(file, nameLineState, handlers) {
  handlers = handlers || {};
  const warnings = warningsForFile(nameLineState, file);
  const row = document.createElement("div");
  row.className = "pv-row" + (warnings.length ? " pv-row-warn" : "");
  row.dataset.fileId = file.id;

  const main = document.createElement("div");
  main.className = "pv-row-main";

  const nameEl = document.createElement("div");
  nameEl.className = "pv-name";
  nameEl.textContent = computeRenderedName(nameLineState, file) || "(empty)";
  main.appendChild(nameEl);

  if (warnings.length) {
    const warnEl = document.createElement("div");
    warnEl.className = "pv-warn";
    warnEl.textContent = "⚠ " + warnings.join(", ");
    main.appendChild(warnEl);
  }

  const editBtn = document.createElement("button");
  editBtn.type = "button";
  editBtn.className = "pv-edit";
  editBtn.textContent = "✎";
  editBtn.setAttribute("aria-label", "Edit this file's metadata");
  editBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const existing = row.querySelector(".pv-edit-form");
    if (existing) { existing.remove(); return; }
    row.appendChild(buildEditForm(file, nameLineState, handlers));
  });
  main.appendChild(editBtn);

  row.appendChild(main);
  return row;
}

function buildEditForm(file, nameLineState, handlers) {
  const form = document.createElement("div");
  form.className = "pv-edit-form";
  const fields = new Set();
  (nameLineState.blocks || []).forEach((block) => {
    const t = String(block.type || "").toUpperCase();
    if (VALUE_TYPE_FIELD[t]) fields.add(VALUE_TYPE_FIELD[t]);
    if (SINGLETON_FIELDS[t]) fields.add(SINGLETON_FIELDS[t]);
  });
  const overrides = (nameLineState.overrides && nameLineState.overrides[file.id]) || {};
  fields.forEach((field) => {
    const label = document.createElement("label");
    label.className = "pv-edit-label";
    label.textContent = field;
    const input = document.createElement("input");
    input.type = "text";
    input.className = "pv-edit-input";
    input.dataset.field = field;
    input.value = overrides[field] || (file.fields && file.fields[field]) || "";
    input.placeholder = field;
    input.addEventListener("change", () => {
      if (typeof handlers.onOverrideChange === "function") {
        handlers.onOverrideChange(file.id, field, input.value);
      }
    });
    label.appendChild(input);
    form.appendChild(label);
  });
  return form;
}
```

- [ ] **Step 4: Thread `handlers` through `render()` in `mount()`**

Inside `mount()`, update the `render()` closure to pass handlers to `renderRow`:

```js
function render() {
  body.innerHTML = "";
  let warnCount = 0;
  currentFiles.forEach((file) => {
    const row = renderRow(file, currentState, {
      onOverrideChange(fileId, field, value) {
        if (typeof opts.onOverrideChange === "function") {
          opts.onOverrideChange(fileId, field, value);
        }
      },
    });
    if (row.classList.contains("pv-row-warn")) warnCount++;
    body.appendChild(row);
  });
  // ... (keep existing counter + downloadBtn logic)
  const total = currentFiles.length;
  if (total === 0) {
    counter.textContent = "No files uploaded yet";
  } else if (warnCount === 0) {
    counter.textContent = `${total} files ready`;
  } else {
    counter.textContent = `${total} files · ${warnCount} need attention`;
  }
  const blocked = warnCount > 0 || total === 0;
  downloadBtn.toggleAttribute("disabled", blocked);
  downloadBtn.textContent = blocked
    ? (total === 0 ? "Upload files to download" : `Fix ${warnCount} issue${warnCount === 1 ? "" : "s"} to download`)
    : "Download ZIP";
}
```

- [ ] **Step 5: Add edit-form CSS**

Append to `frontend/static/css/name-line.css`:

```css
.pv-row-main { display: flex; align-items: center; gap: 10px; }
.pv-row-main .pv-name { flex: 1; }
.pv-edit { border: none; background: transparent; cursor: pointer; font-size: 14px; opacity: 0.55; }
.pv-edit:hover { opacity: 1; }
.pv-edit-form { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 8px; padding: 8px; background: #faf6ef; border-radius: 8px; }
.pv-edit-label { display: flex; flex-direction: column; font-size: 10px; text-transform: uppercase; color: #6b6257; font-weight: 600; }
.pv-edit-input { padding: 4px 6px; border: 1px solid #dcd4c8; border-radius: 4px; font-size: 12px; background: #fff; min-width: 140px; }
```

- [ ] **Step 6: Run tests**

```bash
./tests/frontend/run-frontend-tests.sh
```

Expected: all 25 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/static/js/preview.js frontend/static/css/name-line.css tests/frontend/name-line.test.js
git commit -m "feat(preview): inline per-file override editor on preview rows"
```

---

## Task 11: Collapse wizard to single page — strip Step 2/3 forms and wire preview

**Files:**
- Modify: `frontend/templates/app.html` (remove form controls, metadata editor list, continue buttons, step-switching; add preview container)
- Modify: `frontend/templates/app.html` (the inline `<script>` that manages state — wire Preview.mount, remove step switching)

This is the biggest single file change, but it's mostly deletions. Follow the checklist carefully.

- [ ] **Step 1: Remove the `<form id="rename-form">` block**

Delete [app.html:196-231](frontend/templates/app.html:196) entirely — the block starting with `<form id="rename-form" class="space-y-6">` through its closing `</form>`. This contained the duplicate Separator Logic dropdown, Casing Style select, and Precision Cleanup toggle.

- [ ] **Step 2: Remove the "Per-file cleanup" panel**

Delete [app.html:233-251](frontend/templates/app.html:233) — the block starting with `<div class="space-y-4 pt-4 border-t border-hairline">` containing `#metadata-editor-list`, `#refresh-preview`, and `#go-review`. Stop at its closing `</div>` just before the `</section>` that ends Step 2.

- [ ] **Step 3: Add preview container below Name Line**

In the Step 2 `<section>`, after the closing `</div>` of `#name-line-root` (which ends around the old line 194), add:

```html
<div id="preview-root" class="mt-6"></div>
```

So the end of the (to-be-removed) `<section data-step-panel="2">` should look like:

```html
<div id="name-line-root" data-nl-root ...>
  ...
</div>
<div id="preview-root" class="mt-6"></div>
```

- [ ] **Step 4: Remove the wizard panel wrappers**

Delete these three `<section class="wizard-panel ..." data-step-panel="1|2|3">` opening tags **and** their matching closing `</section>` tags around [app.html:131, 167, 255](frontend/templates/app.html:131). Keep their inner content.

Also delete Step 3's entire body at [app.html:255-322](frontend/templates/app.html:255) — from the `<section class="wizard-panel hidden space-y-8 relative" data-step-panel="3">` opening through its closing `</section>`. Step 3 is gone.

After this change, the markup sequence should be:

```html
<!-- (was Step 1) upload dropzone content -->
...

<!-- (was Step 2) name-line + preview -->
<div class="space-y-2">...Step headings...</div>
<div id="name-line-root" ...></div>
<div id="preview-root" class="mt-6"></div>

<!-- (was Step 3) — DELETED -->
```

- [ ] **Step 5: Remove the step-switching JS**

In the inline `<script>` inside app.html, remove all uses of `setStep(n)` and the definition of `setStep`. Specifically:

- Delete the function definition at [app.html:778](frontend/templates/app.html:778) (`function setStep(step) { ... }`).
- Delete the variable at [app.html:535](frontend/templates/app.html:535) (`const stepPanels = Array.from(...)`).
- Replace `setStep(1)` at [app.html:689](frontend/templates/app.html:689) with nothing (delete the line).
- Replace `setStep(2)` at [app.html:1360](frontend/templates/app.html:1360) and `setStep(3)` at [app.html:1534](frontend/templates/app.html:1534) with nothing.
- Delete the `setStep(Number(button.dataset.stepTarget))` line at [app.html:1444](frontend/templates/app.html:1444).

Verify:

```bash
grep -n "setStep\|stepPanels\|wizard-panel" frontend/templates/app.html
```

Expected: zero results.

- [ ] **Step 6: Remove the per-file metadata editor rendering**

Delete the function `renderMetadataEditor` (at [app.html:818](frontend/templates/app.html:818) through its closing `}` — it's the function that renders the per-file edit cards). Also delete the two calls to `renderMetadataEditor()` at [app.html:685](frontend/templates/app.html:685) and [app.html:1306](frontend/templates/app.html:1306) and [app.html:1542](frontend/templates/app.html:1542).

Verify:

```bash
grep -n "renderMetadataEditor\|metadata-editor-list\|refresh-preview\|go-review" frontend/templates/app.html
```

Expected: zero results.

- [ ] **Step 7: Remove references to dropped DOM ids**

`summaryFormat`, `summaryArtist`, `summaryProducers`, `summaryDelimiter`, `summaryCase`, `summaryCleanup`, `statFiles`, `statSize`, `statReady`, `downloadFileCount` — all of these live in Step 3 which is gone. Delete their `document.getElementById(...)` lookups and the `updateSummary()` function at [app.html:1092](frontend/templates/app.html:1092).

Replace calls to `updateSummary()` with nothing (just delete the line) everywhere.

Verify:

```bash
grep -n "updateSummary\|summaryFormat\|downloadFileCount\|statFiles\|statReady" frontend/templates/app.html
```

Expected: zero results.

- [ ] **Step 8: Drop casing/cleanup form field reads; pass constants to the backend**

The submit path at [app.html:1326-1328](frontend/templates/app.html:1326) posts `blocks_json` and `file_overrides_json`. It likely also posts `case_style`, `safe_cleanup`, and `delimiter` from the removed form elements. Find the `FormData` construction (the `formData.append(...)` calls in the submit handler) and replace any reads of `document.getElementById("case_style").value`, `document.getElementById("safe_cleanup").checked`, `document.getElementById("delimiter").value` with literal constants:

```js
formData.append("case_style", "keep");
formData.append("safe_cleanup", "true");
formData.append("delimiter", "underscore");
```

The separator logic is carried by `blocks_json.global_separator`, not by the `delimiter` form field, but the backend still expects `delimiter` present — hence the literal.

Verify no remaining reads of those removed elements:

```bash
grep -n 'getElementById("case_style")\|getElementById("safe_cleanup")\|getElementById("delimiter")' frontend/templates/app.html
```

Expected: zero results.

- [ ] **Step 9: Wire `Preview.mount` and connect it to Name Line state**

Locate the inline `<script>` at the bottom of app.html where `NameLine.mount(root, {...})` is called (around [app.html:1606](frontend/templates/app.html:1606)).

**Before** the `NameLine.mount` call, declare a closure variable to hold the latest Name Line state:

```js
let currentNameLineState = { blocks: [], globalSeparator: "_" };
```

**After** the `NameLine.mount` call, add the Preview wiring:

```js
const previewRoot = document.getElementById("preview-root");
const previewCtrl = window.Preview.mount(previewRoot, {
  onOverrideChange(fileId, field, value) {
    state.fileEdits[fileId] = { ...(state.fileEdits[fileId] || {}), [field]: value };
    const trimmed = value == null ? "" : String(value).trim();
    if (!trimmed) delete state.fileEdits[fileId][field];
    if (state.fileEdits[fileId] && Object.keys(state.fileEdits[fileId]).length === 0) {
      delete state.fileEdits[fileId];
    }
    previewCtrl.setNameLineState({ ...currentNameLineState, overrides: state.fileEdits });
  },
  onDownload() {
    if (typeof window.triggerDownload === "function") window.triggerDownload();
    else document.getElementById("download-link")?.click();
  },
});

function refreshPreview() {
  previewCtrl.setNameLineState({ ...currentNameLineState, overrides: state.fileEdits });
  previewCtrl.setFiles((state.uploadedFiles || []).map((f) => ({
    id: f.id,
    fields: f.fields || {},
  })));
}
```

Also hook `refreshPreview()` into these existing state changes:
- After `state.uploadedFiles = payload.files` is assigned (around [app.html:1302](frontend/templates/app.html:1302)), add `refreshPreview();`.
- Update the existing `NameLine.mount(root, { onChange(nlState) { ... } })` callback: assign `currentNameLineState = { blocks: nlState.blocks, globalSeparator: nlState.global_separator || nlState.globalSeparator || "_" };` at the top of the callback (normalizing both snake_case from `serialize()` output and camelCase from raw state), then add `refreshPreview();` at the end.

- [ ] **Step 10: Manual smoke — full flow**

1. `docker-compose up --build`.
2. Open `http://localhost:8000/app`. Sign in.
3. Upload a folder of music files. Observe: no Step 1/2/3 wizard panels — everything is one scrolling page.
4. Name Line appears beneath upload. Drag by grip → reorders. ◀ ▶ → reorder. Alt+←/→ → reorder.
5. Preview list appears beneath Name Line, one row per file.
6. Clear the ARTIST chip's value → every row shows `⚠ missing artist`; Download shows "Fix N issues to download" and is disabled.
7. Click ✎ on a warning row. Fill in `artist` for just that file. That row clears its warning; download button updates count. Others still warned.
8. Fill the ARTIST chip value → all rows clear; Download enables.
9. Click Download → ZIP downloads.

- [ ] **Step 11: Commit**

```bash
git add frontend/templates/app.html
git commit -m "feat(app): single-page flow — name-line + preview table, drop wizard"
```

---

## Task 12: Sticky Name Line + collapsed upload bar

**Files:**
- Modify: `frontend/static/css/name-line.css` (sticky positioning)
- Modify: `frontend/templates/app.html` (add `.nl-sticky` wrapper + upload-bar collapse class logic)

- [ ] **Step 1: Add sticky class to CSS**

Append to `frontend/static/css/name-line.css`:

```css
.nl-sticky {
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--stage, #faf6ef);
  padding-top: 8px;
  margin-top: -8px;
}

.upload-collapsed .dropzone-full { display: none; }
.upload-collapsed .dropzone-bar  { display: flex; }
.dropzone-bar { display: none; align-items: center; justify-content: space-between; padding: 8px 14px; border: 1px solid var(--hairline, #dcd4c8); border-radius: 10px; font-size: 12px; }
```

- [ ] **Step 2: Wrap Name Line in sticky container**

In `frontend/templates/app.html`, wrap the `<div id="name-line-root">` with `<div class="nl-sticky">` and close with `</div>`. Preview stays outside sticky.

```html
<div class="nl-sticky">
  <div id="name-line-root" data-nl-root class="rounded-xl border border-hairline bg-stage-raised p-4 space-y-3">
    ...
  </div>
</div>
<div id="preview-root" class="mt-6"></div>
```

- [ ] **Step 3: Add a collapsed upload bar + toggle logic**

Find the upload dropzone markup (whichever block currently shows "Drop files" / drag-over in Step 1). Wrap the full dropzone in a `<div class="dropzone-full">`, and add a compact bar **sibling** (not child) of it:

```html
<div id="upload-zone">
  <div class="dropzone-full">
    <!-- existing full drop target markup -->
  </div>
  <div class="dropzone-bar">
    <span><b id="upload-count">0</b> files loaded</span>
    <button type="button" id="upload-add-more" class="underline">+ add more</button>
  </div>
</div>
```

In the inline JS, when files are uploaded successfully (the handler that currently calls `setStep(2)` at [app.html:1360](frontend/templates/app.html:1360) — already removed in Task 11), instead do:

```js
document.getElementById("upload-zone").classList.add("upload-collapsed");
const countEl = document.getElementById("upload-count");
if (countEl) countEl.textContent = String(state.uploadedFiles.length);
```

Hook `#upload-add-more` to re-expand:

```js
document.getElementById("upload-add-more")?.addEventListener("click", () => {
  document.getElementById("upload-zone").classList.remove("upload-collapsed");
});
```

- [ ] **Step 4: Manual smoke**

Reload app. Drop files → full dropzone collapses to a thin bar showing `42 files loaded · + add more`. Click `+ add more` → full dropzone returns. Scroll down past the Name Line: it stays pinned to top of viewport while preview scrolls beneath it.

- [ ] **Step 5: Commit**

```bash
git add frontend/static/css/name-line.css frontend/templates/app.html
git commit -m "feat(app): sticky Name Line + collapsed upload bar after files loaded"
```

---

## Task 13: Backend regression test — overrides still resolve correctly

**Files:**
- Modify: `tests/test_name_line_render.py`

The backend is unchanged in this plan, but the frontend is now the sole producer of `blocks_json` + `file_overrides_json`. Add guard tests so anyone later changing the backend knows the existing contract the new frontend depends on.

- [ ] **Step 1: Append new tests to `tests/test_name_line_render.py`**

```python
def test_value_type_empty_causes_skip_but_fills_with_override_equivalent_upstream():
    """Simulates the resolution chain: backend render_blocks only sees resolved values.
    This test just asserts the service drops empty value-bearing blocks so the
    filename doesn't have a dangling separator — the frontend's warning rule is
    the one that catches this case for the user."""
    blocks = [
        {"type": "ARTIST", "value": ""},
        {"type": "TITLE"},
        {"type": "PRODUCER", "value": ""},
    ]
    result = render_blocks(blocks, global_separator="_", extracted_fields=EXTRACTED)
    assert result == "Loaded Up"


def test_text_block_value_preserved_verbatim_even_around_empty_values():
    blocks = [
        {"type": "ARTIST", "value": ""},
        {"type": "TEXT", "value": "@"},
        {"type": "TITLE"},
    ]
    result = render_blocks(blocks, global_separator="_", extracted_fields=EXTRACTED)
    assert result == "@Loaded Up"


def test_no_duplicate_separator_when_singleton_missing_between_tokens():
    blocks = [
        {"type": "ARTIST", "value": "Hurricane Wisdom"},
        {"type": "BPM"},
        {"type": "TITLE"},
    ]
    extracted = {**EXTRACTED, "bpm": ""}
    result = render_blocks(blocks, global_separator="_", extracted_fields=extracted)
    assert result == "Hurricane Wisdom_Loaded Up"
```

- [ ] **Step 2: Run the backend test suite**

```bash
docker-compose exec backend pytest tests/test_name_line_render.py -v
```

(Or run locally: `pytest tests/test_name_line_render.py -v` if the Python env has the `backend` package on path.)

Expected: all tests PASS including the three new ones.

- [ ] **Step 3: Commit**

```bash
git add tests/test_name_line_render.py
git commit -m "test(name-line): regression guards for empty/text block resolution"
```

---

## Task 14: Final manual smoke + cache-buster verification

- [ ] **Step 1: Rebuild Docker**

```bash
docker-compose up --build
```

- [ ] **Step 2: Run every frontend + backend test**

```bash
./tests/frontend/run-frontend-tests.sh
docker-compose exec backend pytest
```

Expected: all green.

- [ ] **Step 3: End-to-end manual smoke (checklist)**

Work through this in one uninterrupted session. Each line should pass.

- [ ] Open `http://localhost:8000/app` in Chrome. Sign in.
- [ ] Upload a folder of 5+ music files. No wizard panel. Upload collapses to thin bar.
- [ ] Name Line shows default chips (ARTIST, TITLE, PRODUCER, MIX, VERSION).
- [ ] Drag ARTIST chip's grip past TITLE. Chip order updates. Preview names update.
- [ ] Click TITLE chip body — nothing happens (singleton, no edit).
- [ ] Click ARTIST chip body → edit input opens; type a value; blur → chip shows value.
- [ ] Click ◀ on TITLE → moves left. ▶ on last → disabled.
- [ ] Tab to PRODUCER chip (cyan focus ring). Alt+→ → moves right. Alt+← → moves left. Enter → edit mode. Delete → removed.
- [ ] Clear all ARTIST value → every preview row shows ⚠ missing artist. Download disabled with "Fix N issues".
- [ ] Click ✎ on one row. Fill artist for just that file. That row un-warns. Download count decreases.
- [ ] Refill chip value → all rows clear. Download enables.
- [ ] Click Download → ZIP downloads.
- [ ] Scroll down past the Name Line → it stays pinned to top.
- [ ] Refresh the page → state persisted (chips, separator, per-file edits).
- [ ] Clear localStorage in DevTools, re-set old v1 key:
  ```js
  localStorage.setItem("pxnn.nameLine.v1", JSON.stringify({blocks:[{type:"TITLE"}],globalSeparator:"-"}));
  location.reload();
  ```
  Confirm: chips = [TITLE], separator = `-`. `localStorage.getItem("pxnn.nameLine.v2")` is populated. v1 key still exists (that's fine; we only migrate *once on read*).
- [ ] Test in Firefox + Safari: drag by grip works in all three.

- [ ] **Step 4: Tag the release-candidate commit**

```bash
git log --oneline | head -15
git tag name-line-v2-rc1
```

- [ ] **Step 5: Commit any final cleanup** (empty commit if nothing to add — documents the milestone)

```bash
git commit --allow-empty -m "chore(name-line): v2 simplification complete — all tasks green"
```

---

## Appendix: Files changed summary

- **Created:** `frontend/static/vendor/sortable.min.js`, `frontend/static/vendor/README.md`, `frontend/static/js/preview.js`, `tests/frontend/package.json`, `tests/frontend/name-line.test.js`, `tests/frontend/run-frontend-tests.sh`
- **Modified:** `frontend/static/js/name-line.js`, `frontend/static/css/name-line.css`, `frontend/templates/app.html`, `tests/test_name_line_render.py`
- **Backend:** unchanged (overrides already supported via `file_overrides_json`).

## Appendix: Cache-buster notes

The `?v=name-line-5` query string in `<script>` and `<link>` tags in `app.html` is the cache-buster. Bumping it forces browsers to re-download after deploy. If later tasks modify `name-line.js` / `name-line.css` / `preview.js`, bump to `name-line-6`, etc.
