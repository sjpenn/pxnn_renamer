const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { JSDOM } = require("jsdom");

const JS_PATH = path.join(__dirname, "..", "..", "frontend", "static", "js", "name-line.js");
const SOURCE = fs.readFileSync(JS_PATH, "utf8");

function loadNameLine() {
  const dom = new JSDOM("<!doctype html><html><body></body></html>", { runScripts: "outside-only", url: "http://localhost" });
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

// Report.
for (const r of results) {
  console.log(`${r.ok ? "PASS" : "FAIL"}  ${r.name}`);
  if (!r.ok) console.error(r.err);
}
const failed = results.filter((r) => !r.ok).length;
process.exit(failed ? 1 : 0);
