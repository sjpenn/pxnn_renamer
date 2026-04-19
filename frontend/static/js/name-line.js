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
    chip.dataset.blockId = block.id;
    chip.dataset.blockType = block.type;
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

    const grip = document.createElement("span");
    grip.className = "material-symbols-outlined nl-grip";
    grip.textContent = "drag_indicator";
    grip.setAttribute("aria-label", "Drag to reorder");
    grip.addEventListener("click", (e) => e.stopPropagation());
    chip.appendChild(grip);

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
        const t = event.target;
        if (t.closest(".nl-chip-remove")) return;
        if (t.closest(".nl-grip")) return;
        if (t.closest(".nl-chip-arrow")) return;
        handlers.onEdit(block.id, chip);
      });
    } else {
      const label = document.createElement("span");
      label.textContent = meta.label;
      chip.appendChild(label);
    }

    const arrowLeft = document.createElement("button");
    arrowLeft.type = "button";
    arrowLeft.className = "nl-chip-arrow nl-chip-arrow-left";
    arrowLeft.textContent = "◀";
    arrowLeft.setAttribute("aria-label", "Move left");
    arrowLeft.setAttribute("tabindex", "-1");
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
    arrowRight.setAttribute("tabindex", "-1");
    arrowRight.addEventListener("click", (event) => {
      event.stopPropagation();
      if (typeof handlers.onMoveRight === "function") handlers.onMoveRight(block.id);
    });
    chip.appendChild(arrowRight);

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "nl-chip-remove";
    removeBtn.textContent = "×";
    removeBtn.setAttribute("tabindex", "-1");
    removeBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      handlers.onRemove(block.id);
    });
    chip.appendChild(removeBtn);

    return chip;
  }

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
    diffRenderLine,
    mount,
  };
})();
