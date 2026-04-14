(function () {
  "use strict";

  const TOKEN_CATEGORIES = {
    ARTIST: { family: "identity", icon: "person", label: "ARTIST", hasValue: true, repeatable: true },
    PRODUCER: { family: "identity", icon: "graphic_eq", label: "PRODUCER", hasValue: true, repeatable: true },
    TITLE: { family: "content", icon: "music_note", label: "TITLE", hasValue: false, repeatable: false },
    BPM: { family: "metadata", icon: "speed", label: "BPM", hasValue: false, repeatable: false },
    KEY: { family: "metadata", icon: "piano", label: "KEY", hasValue: false, repeatable: false },
    DATE: { family: "metadata", icon: "calendar_today", label: "DATE", hasValue: false, repeatable: false },
    INDEX: { family: "metadata", icon: "tag", label: "INDEX", hasValue: false, repeatable: false },
    MIX: { family: "variant", icon: "tune", label: "MIX", hasValue: false, repeatable: false },
    VERSION: { family: "variant", icon: "layers", label: "VERSION", hasValue: false, repeatable: false },
    TEXT: { family: "literal", icon: "text_fields", label: "TEXT", hasValue: true, repeatable: true, literal: true },
  };

  const DEFAULT_BLOCKS = [
    { type: "ARTIST", value: "" },
    { type: "TITLE" },
    { type: "PRODUCER", value: "" },
    { type: "MIX" },
    { type: "VERSION" },
  ];

  const STORAGE_KEY = "pxnn.nameLine.v1";

  function newId() {
    return "b_" + Math.random().toString(36).slice(2, 9);
  }

  function normalizeBlock(block) {
    const type = String(block.type || "").toUpperCase();
    const meta = TOKEN_CATEGORIES[type];
    if (!meta) return null;
    const out = { id: block.id || newId(), type };
    if (meta.hasValue) out.value = String(block.value || "");
    return out;
  }

  function createState(initial) {
    const rawBlocks = Array.isArray(initial && initial.blocks) ? initial.blocks : DEFAULT_BLOCKS;
    const blocks = rawBlocks.map(normalizeBlock).filter(Boolean);
    const globalSeparator = (initial && initial.globalSeparator) || "_";
    return { blocks, globalSeparator };
  }

  function serialize(state) {
    return {
      blocks: state.blocks.map((block) => {
        const meta = TOKEN_CATEGORIES[block.type];
        return meta && meta.hasValue
          ? { type: block.type, value: block.value || "" }
          : { type: block.type };
      }),
      global_separator: state.globalSeparator,
    };
  }

  function loadPersisted() {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (_err) {
      return null;
    }
  }

  function persist(state) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (_err) {
      // ignore
    }
  }

  // --- Rendering ---

  function familyFor(type) {
    const meta = TOKEN_CATEGORIES[type];
    return meta ? meta.family : "literal";
  }

  function renderChip(block, handlers) {
    const meta = TOKEN_CATEGORIES[block.type] || { family: "literal", label: block.type, icon: "help" };
    const chip = document.createElement("span");
    chip.className = "nl-chip nl-family-" + meta.family;
    chip.setAttribute("draggable", "true");
    chip.dataset.blockId = block.id;
    chip.dataset.blockType = block.type;

    const swatch = document.createElement("span");
    swatch.className = "nl-chip-swatch";
    chip.appendChild(swatch);

    const icon = document.createElement("span");
    icon.className = "material-symbols-outlined nl-chip-icon";
    icon.textContent = meta.icon;
    chip.appendChild(icon);

    if (meta.hasValue) {
      const valueText = block.value || "";
      if (!valueText) chip.dataset.empty = "true";

      if (!meta.literal) {
        const label = document.createElement("span");
        label.textContent = meta.label + ": ";
        chip.appendChild(label);
      }

      const valueNode = document.createElement("span");
      valueNode.className = "nl-chip-value";
      valueNode.textContent = valueText || (meta.literal ? "…" : "empty");
      chip.appendChild(valueNode);

      chip.addEventListener("click", (event) => {
        if (event.target.classList.contains("nl-chip-remove")) return;
        handlers.onEdit(block.id, chip);
      });
    } else {
      const label = document.createElement("span");
      label.textContent = meta.label;
      chip.appendChild(label);
    }

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "nl-chip-remove";
    removeBtn.textContent = "×";
    removeBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      handlers.onRemove(block.id);
    });
    chip.appendChild(removeBtn);

    return chip;
  }

  function renderPalette(container, handlers) {
    container.innerHTML = "";
    Object.keys(TOKEN_CATEGORIES).forEach((type) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "+ " + TOKEN_CATEGORIES[type].label;
      btn.addEventListener("click", () => handlers.onAdd(type));
      container.appendChild(btn);
    });
  }

  function renderLegend(container) {
    container.innerHTML = "";
    const families = [
      ["identity", "Identity"],
      ["content", "Content"],
      ["metadata", "Metadata"],
      ["variant", "Variant"],
      ["literal", "Literal"],
    ];
    families.forEach(([family, label]) => {
      const item = document.createElement("span");
      item.className = "nl-legend-item";
      const swatch = document.createElement("span");
      swatch.className = "nl-swatch nl-family-" + family;
      item.appendChild(swatch);
      item.appendChild(document.createTextNode(label));
      container.appendChild(item);
    });
  }

  // --- Autocomplete ---

  const suggestionsCache = { ARTIST: null, PRODUCER: null };

  async function fetchSuggestions(blockType) {
    if (suggestionsCache[blockType] !== null && suggestionsCache[blockType] !== undefined) {
      return suggestionsCache[blockType];
    }
    const endpoint = blockType === "ARTIST" ? "/api/suggestions/artists" : "/api/suggestions/producers";
    try {
      const response = await fetch(endpoint, { credentials: "same-origin" });
      if (!response.ok) {
        suggestionsCache[blockType] = [];
        return [];
      }
      const body = await response.json();
      const values = Array.isArray(body.values) ? body.values : [];
      suggestionsCache[blockType] = values;
      return values;
    } catch (_err) {
      suggestionsCache[blockType] = [];
      return [];
    }
  }

  function openEditor(chipEl, block, onCommit) {
    chipEl.innerHTML = "";
    const input = document.createElement("input");
    input.type = "text";
    input.className = "nl-chip-input";
    input.value = block.value || "";
    input.placeholder = (TOKEN_CATEGORIES[block.type] && TOKEN_CATEGORIES[block.type].label) || "";
    chipEl.appendChild(input);

    let dropdown = null;
    let activeIndex = -1;
    let options = [];
    let committed = false;

    function closeDropdown() {
      if (dropdown) dropdown.remove();
      dropdown = null;
      activeIndex = -1;
      options = [];
    }

    function commit() {
      if (committed) return;
      committed = true;
      closeDropdown();
      onCommit(input.value.trim());
    }

    function renderDropdown(values) {
      closeDropdown();
      const query = input.value.toLowerCase();
      const filtered = values.filter((v) => v.toLowerCase().includes(query)).slice(0, 8);
      if (!filtered.length) return;
      dropdown = document.createElement("div");
      dropdown.className = "nl-autocomplete";
      filtered.forEach((value) => {
        const item = document.createElement("div");
        item.className = "nl-autocomplete-item";
        item.textContent = value;
        item.addEventListener("mousedown", (event) => {
          event.preventDefault();
          input.value = value;
          commit();
        });
        dropdown.appendChild(item);
      });
      chipEl.appendChild(dropdown);
      options = filtered;
    }

    function highlightActive() {
      if (!dropdown) return;
      Array.from(dropdown.children).forEach((child, index) => {
        child.classList.toggle("is-active", index === activeIndex);
      });
    }

    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") { event.preventDefault(); commit(); }
      else if (event.key === "Escape") { closeDropdown(); committed = true; onCommit(block.value || ""); }
      else if (event.key === "ArrowDown" && dropdown) { activeIndex = Math.min(activeIndex + 1, options.length - 1); highlightActive(); }
      else if (event.key === "ArrowUp" && dropdown)   { activeIndex = Math.max(activeIndex - 1, 0); highlightActive(); }
    });
    input.addEventListener("blur", () => { setTimeout(commit, 100); });

    const meta = TOKEN_CATEGORIES[block.type];
    if (meta && !meta.literal && (block.type === "ARTIST" || block.type === "PRODUCER")) {
      fetchSuggestions(block.type).then((values) => {
        renderDropdown(values);
        input.addEventListener("input", () => renderDropdown(values));
      });
    }

    input.focus();
    input.select();
  }

  function mount(root, options) {
    options = options || {};
    const legendEl   = root.querySelector("[data-nl-legend]");
    const paletteEl  = root.querySelector("[data-nl-palette]");
    const lineEl     = root.querySelector("[data-nl-line]");
    const separatorSelect = root.querySelector("[data-nl-separator]");
    const resetBtn   = root.querySelector("[data-nl-reset]");

    const state = createState(loadPersisted() || undefined);
    if (separatorSelect) separatorSelect.value = state.globalSeparator;

    function notifyChange() {
      persist(state);
      if (typeof options.onChange === "function") options.onChange(serialize(state));
    }

    function rerender() {
      renderLine();
      notifyChange();
    }

    function renderLine() {
      lineEl.innerHTML = "";
      state.blocks.forEach((block) => {
        const chip = renderChip(block, {
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
        attachDrag(chip);
        lineEl.appendChild(chip);
      });
    }

    function attachDrag(chipEl) {
      chipEl.addEventListener("dragstart", (event) => {
        event.dataTransfer.setData("text/plain", chipEl.dataset.blockId);
        event.dataTransfer.effectAllowed = "move";
        chipEl.style.opacity = "0.4";
      });
      chipEl.addEventListener("dragend", () => {
        chipEl.style.opacity = "";
        lineEl.querySelectorAll(".nl-chip").forEach((c) => {
          c.classList.remove("nl-drop-before", "nl-drop-after");
        });
      });
      chipEl.addEventListener("dragover", (event) => {
        event.preventDefault();
        const rect = chipEl.getBoundingClientRect();
        const after = event.clientX - rect.left > rect.width / 2;
        chipEl.classList.toggle("nl-drop-after", after);
        chipEl.classList.toggle("nl-drop-before", !after);
      });
      chipEl.addEventListener("dragleave", () => {
        chipEl.classList.remove("nl-drop-before", "nl-drop-after");
      });
      chipEl.addEventListener("drop", (event) => {
        event.preventDefault();
        const sourceId = event.dataTransfer.getData("text/plain");
        if (!sourceId || sourceId === chipEl.dataset.blockId) return;
        const rect = chipEl.getBoundingClientRect();
        const after = event.clientX - rect.left > rect.width / 2;
        const targetId = chipEl.dataset.blockId;
        const sourceIndex = state.blocks.findIndex((b) => b.id === sourceId);
        if (sourceIndex < 0) return;
        const [moved] = state.blocks.splice(sourceIndex, 1);
        const targetIndex = state.blocks.findIndex((b) => b.id === targetId);
        state.blocks.splice(after ? targetIndex + 1 : targetIndex, 0, moved);
        rerender();
      });
    }

    if (legendEl) renderLegend(legendEl);
    if (paletteEl) {
      renderPalette(paletteEl, {
        onAdd(type) {
          const block = normalizeBlock({ type });
          if (!block) return;
          state.blocks.push(block);
          rerender();
          const meta = TOKEN_CATEGORIES[type];
          if (meta && meta.hasValue) {
            const chip = lineEl.querySelector('[data-block-id="' + block.id + '"]');
            if (chip) openEditor(chip, block, (newValue) => {
              block.value = newValue;
              rerender();
            });
          }
        },
      });
    }
    if (separatorSelect) {
      separatorSelect.addEventListener("change", () => {
        state.globalSeparator = separatorSelect.value || "_";
        rerender();
      });
    }
    if (resetBtn) {
      resetBtn.addEventListener("click", () => {
        const fresh = createState();
        state.blocks = fresh.blocks;
        state.globalSeparator = fresh.globalSeparator;
        if (separatorSelect) separatorSelect.value = state.globalSeparator;
        rerender();
      });
    }

    rerender();

    return {
      getState: () => state,
      getSerialized: () => serialize(state),
    };
  }

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
    mount,
  };
})();
