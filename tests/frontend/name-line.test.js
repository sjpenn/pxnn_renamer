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

// Report.
for (const r of results) {
  console.log(`${r.ok ? "PASS" : "FAIL"}  ${r.name}`);
  if (!r.ok) console.error(r.err);
}
const failed = results.filter((r) => !r.ok).length;
process.exit(failed ? 1 : 0);
