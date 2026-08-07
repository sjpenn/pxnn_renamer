from backend.app.routes.wizard import _extract_fields


def test_prod_dot_credit_becomes_producer():
    fields = _extract_fields("drake_gods plan_prod. metro boomin_140bpm_dirty", ".mp3", 1)
    assert fields["artist"] == "drake"
    assert "metro boomin" in fields["producers"].lower()
    assert "prod" not in fields["title"].lower()
    assert fields["bpm"] == "140BPM"
    assert fields["mix"] == "DIRTY"


def test_produced_by_credit_becomes_producer():
    fields = _extract_fields("Artist_Song Title_produced by Zaytoven", ".wav", 1)
    assert "zaytoven" in fields["producers"].lower()
    assert "produced" not in fields["title"].lower()


def test_dash_separated_artist_is_extracted():
    fields = _extract_fields("SZA - Kill Bill", ".wav", 1)
    assert fields["artist"] == "SZA"
    assert fields["title"] == "Kill Bill"


def test_parenthetical_mix_note_is_kept():
    fields = _extract_fields("SZA - Kill Bill (Clean Mix)", ".wav", 1)
    assert fields["artist"] == "SZA"
    assert fields["mix"] == "CLEAN"
    assert "clean" not in fields["title"].lower()


def test_parenthetical_prod_credit_is_kept():
    fields = _extract_fields("Hurricane Wisdom - Loaded Up (prod. PMHITSS)", ".mp3", 1)
    assert "pmhitss" in fields["producers"].lower()
    assert fields["artist"] == "Hurricane Wisdom"


def test_underscore_files_still_parse_as_before():
    fields = _extract_fields("drake_gods plan_dirty", ".mp3", 2)
    assert fields["artist"] == "drake"
    assert fields["title"] == "gods plan"
    assert fields["mix"] == "DIRTY"
    assert fields["index"] == "02"
