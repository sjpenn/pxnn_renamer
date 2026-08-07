(function () {
  "use strict";

  const VALUE_TYPE_FIELD = { ARTIST: "artist", PRODUCER: "producers" };
  const SINGLETON_FIELDS = {
    TITLE: "title", MIX: "mix", VERSION: "version", BPM: "bpm",
    DATE: "date", KEY: "key", INDEX: "index",
  };

  function resolveForFile(block, file, overrides, accountDefaults) {
    const perFile = overrides && overrides[file.id] ? overrides[file.id] : {};
    const defaults = accountDefaults || {};
    const blockType = String(block.type || "").toUpperCase();
    if (VALUE_TYPE_FIELD[blockType]) {
      const field = VALUE_TYPE_FIELD[blockType];
      return (perFile[field] || block.value || (file.fields && file.fields[field]) || defaults[field] || "").trim();
    }
    if (SINGLETON_FIELDS[blockType]) {
      const field = SINGLETON_FIELDS[blockType];
      return (perFile[field] || (file.fields && file.fields[field]) || defaults[field] || "").trim();
    }
    if (blockType === "TEXT") return String(block.value || "");
    return "";
  }

  function warningsForFile(nameLineState, file, accountDefaults) {
    const warnings = [];
    (nameLineState.blocks || []).forEach((block) => {
      const t = String(block.type || "").toUpperCase();
      if (!VALUE_TYPE_FIELD[t] && t !== "TEXT") return;
      if (t === "TEXT") {
        if (!String(block.value || "").trim()) warnings.push("empty text block");
        return;
      }
      const val = resolveForFile(block, file, nameLineState.overrides || {}, accountDefaults);
      if (!val) warnings.push(`missing ${t.toLowerCase()}`);
    });
    return warnings;
  }

  function computeRenderedName(nameLineState, file, accountDefaults) {
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
      const val = resolveForFile(block, file, nameLineState.overrides || {}, accountDefaults);
      if (!val) return;
      if (prevWasToken) parts.push(sep);
      parts.push(val);
      prevWasToken = true;
    });
    const stem = parts.join("");
    const ext = (file.fields && file.fields.ext) ? "." + String(file.fields.ext).toLowerCase() : "";
    return stem + ext;
  }

  function renderRow(file, nameLineState, handlers, accountDefaults) {
    handlers = handlers || {};
    const warnings = warningsForFile(nameLineState, file, accountDefaults);
    const row = document.createElement("div");
    row.className = "pv-row" + (warnings.length ? " pv-row-warn" : "");
    row.dataset.fileId = file.id;

    const main = document.createElement("div");
    main.className = "pv-row-main";

    const nameEl = document.createElement("div");
    nameEl.className = "pv-name";
    nameEl.textContent = computeRenderedName(nameLineState, file, accountDefaults) || "(empty)";
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

    function buildSampleFile() {
      const getFields = typeof opts.getSampleFields === "function" ? opts.getSampleFields : () => ({});
      return { id: "__sample__", fields: Object.assign({ ext: "wav" }, getFields() || {}) };
    }

    function currentAccountDefaults() {
      const fn = typeof opts.getAccountDefaults === "function" ? opts.getAccountDefaults : null;
      return fn ? (fn() || {}) : {};
    }

    function renderSampleRow() {
      const file = buildSampleFile();
      const row = document.createElement("div");
      row.className = "pv-row";
      row.dataset.sample = "true";
      const main = document.createElement("div");
      main.className = "pv-row-main";
      const hint = document.createElement("span");
      hint.className = "pv-warn";
      hint.style.color = "var(--color-ink-mute, #868584)";
      hint.style.fontWeight = "600";
      hint.textContent = "PREVIEW";
      main.appendChild(hint);
      const nameEl = document.createElement("div");
      nameEl.className = "pv-name";
      nameEl.textContent = computeRenderedName(currentState, file, currentAccountDefaults()) || "(build your name line above)";
      main.appendChild(nameEl);
      row.appendChild(main);
      return row;
    }

    function render() {
      body.innerHTML = "";
      let warnCount = 0;
      const total = currentFiles.length;
      const accountDefaults = currentAccountDefaults();
      if (total === 0) {
        body.appendChild(renderSampleRow());
      } else {
        currentFiles.forEach((file) => {
          const row = renderRow(file, currentState, {
            onOverrideChange(fileId, field, value) {
              if (typeof opts.onOverrideChange === "function") {
                opts.onOverrideChange(fileId, field, value);
              }
            },
          }, accountDefaults);
          if (row.classList.contains("pv-row-warn")) warnCount++;
          body.appendChild(row);
        });
      }
      if (total === 0) {
        counter.textContent = "Sample preview — upload files to rename";
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
      _renderNow: render,
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
