(function () {
  "use strict";

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
