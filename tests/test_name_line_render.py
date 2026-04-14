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


def test_multiple_producers_each_become_a_segment():
    blocks = [
        {"type": "ARTIST", "value": "Hurricane Wisdom"},
        {"type": "PRODUCER", "value": "PMHITSS"},
        {"type": "PRODUCER", "value": "REALLYINDIG0"},
        {"type": "TITLE"},
    ]
    result = render_blocks(blocks, global_separator="_", extracted_fields=EXTRACTED)
    assert result == "Hurricane Wisdom_PMHITSS_REALLYINDIG0_Loaded Up"


def test_text_block_replaces_separator_on_both_sides():
    blocks = [
        {"type": "ARTIST", "value": "Hurricane Wisdom"},
        {"type": "TEXT", "value": " @ "},
        {"type": "TITLE"},
    ]
    result = render_blocks(blocks, global_separator="_", extracted_fields=EXTRACTED)
    assert result == "Hurricane Wisdom @ Loaded Up"


def test_empty_value_block_is_skipped_and_separators_collapse():
    blocks = [
        {"type": "ARTIST", "value": "Hurricane Wisdom"},
        {"type": "PRODUCER", "value": ""},
        {"type": "TITLE"},
    ]
    result = render_blocks(blocks, global_separator="_", extracted_fields=EXTRACTED)
    assert result == "Hurricane Wisdom_Loaded Up"


def test_unknown_block_type_ignored():
    blocks = [
        {"type": "TITLE"},
        {"type": "MADE_UP"},
        {"type": "BPM"},
    ]
    result = render_blocks(blocks, global_separator="_", extracted_fields=EXTRACTED)
    assert result == "Loaded Up_140"


def test_empty_blocks_list_renders_empty_string():
    assert render_blocks([], global_separator="_", extracted_fields=EXTRACTED) == ""
