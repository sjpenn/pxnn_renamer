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
