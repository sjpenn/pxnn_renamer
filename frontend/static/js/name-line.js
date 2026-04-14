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

  window.NameLine = {
    TOKEN_CATEGORIES,
    DEFAULT_BLOCKS,
    createState,
    serialize,
    loadPersisted,
    persist,
    newId,
    normalizeBlock,
  };
})();
