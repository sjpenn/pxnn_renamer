from backend.app.services.name_line import render_blocks

EXTRACTED = {
    "artist": "Hurricane Wisdom",
    "title": "Loaded Up",
    "producers": "PMHITSS; REALLYINDIG0",
    "mix": "MAIN",
    "version": "V2",
    "bpm": "140",
    "date": "2025",
    "key": "Amin",
    "index": "01",
}


def test_renders_singletons_joined_by_separator():
    blocks = [
        {"type": "TITLE"},
        {"type": "BPM"},
        {"type": "KEY"},
    ]
    result = render_blocks(blocks, global_separator="_", extracted_fields=EXTRACTED)
    assert result == "Loaded Up_140_Amin"


def test_missing_singleton_skipped_without_double_separator():
    blocks = [
        {"type": "TITLE"},
        {"type": "BPM"},
        {"type": "KEY"},
    ]
    extracted = {**EXTRACTED, "bpm": ""}
    result = render_blocks(blocks, global_separator="_", extracted_fields=extracted)
    assert result == "Loaded Up_Amin"


def test_unknown_separator_falls_back_to_underscore():
    blocks = [{"type": "TITLE"}, {"type": "BPM"}]
    result = render_blocks(blocks, global_separator="&&", extracted_fields=EXTRACTED)
    assert result == "Loaded Up_140"
