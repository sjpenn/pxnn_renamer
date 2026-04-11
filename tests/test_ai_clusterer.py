from unittest.mock import patch, MagicMock

import pytest

from backend.app.services import ai_clusterer
from backend.app.services.ai_clusterer import ClusterResult, _cluster_via_fallback
from backend.app.database.models import UIComment, User


def _make_notes(db, bodies):
    admin = User(username="a", email="a@x.com", password_hash="x", is_admin=True)
    db.add(admin)
    db.commit()
    db.refresh(admin)
    notes = []
    for i, body in enumerate(bodies):
        n = UIComment(
            author_id=admin.id,
            block_key=f"block-{i}",
            page_path="/app",
            body=body,
        )
        db.add(n)
    db.commit()
    return db.query(UIComment).all()


def test_fallback_returns_empty_for_no_notes(db):
    assert _cluster_via_fallback([]) == []


def test_fallback_clusters_similar_notes(db):
    notes = _make_notes(db, [
        "Make the dropzone bigger and easier to click",
        "The dropzone target is too small",
        "Something completely unrelated about billing",
    ])
    result = _cluster_via_fallback(notes)
    # The two dropzone notes should cluster
    assert len(result) >= 1
    cluster_ids = {tuple(sorted(c.note_ids)) for c in result}
    paired = any(len(ids) >= 2 for ids in cluster_ids)
    assert paired


def test_fallback_does_not_create_singleton_clusters(db):
    notes = _make_notes(db, [
        "Change the color of the button",
        "Completely unrelated idea about invoicing",
    ])
    result = _cluster_via_fallback(notes)
    # Nothing matches → no clusters (all singletons are omitted)
    assert result == []


def test_cluster_notes_empty_input(db):
    assert ai_clusterer.cluster_notes([]) == []


def test_cluster_notes_uses_fallback_when_no_keys(db, monkeypatch):
    from backend.app.core.config import settings
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", None)
    monkeypatch.setattr(settings, "AI_CLUSTERER_PROVIDER", "auto")

    notes = _make_notes(db, [
        "Make dropzone bigger please",
        "Dropzone is too small please enlarge it",
    ])
    result = ai_clusterer.cluster_notes(notes)
    assert len(result) >= 1


def test_cluster_notes_forced_fallback(db, monkeypatch):
    from backend.app.core.config import settings
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-dummy")
    monkeypatch.setattr(settings, "AI_CLUSTERER_PROVIDER", "fallback")

    notes = _make_notes(db, [
        "Completely unrelated idea A",
        "Completely unrelated idea B",
    ])
    # Forced fallback returns [] for no similar groups
    result = ai_clusterer.cluster_notes(notes)
    assert result == []


def test_cluster_notes_anthropic_http_mocked(db, monkeypatch):
    from backend.app.core.config import settings
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-test-key")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", None)
    monkeypatch.setattr(settings, "AI_CLUSTERER_PROVIDER", "anthropic")

    notes = _make_notes(db, [
        "Make dropzone bigger",
        "Increase dropzone target area",
    ])
    ids = [n.id for n in notes]

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "content": [
            {
                "type": "text",
                "text": '{"clusters":[{"title":"Enlarge dropzone","summary":"Users want a larger drop target","note_ids":' + str(ids) + "}]}",
            }
        ]
    }
    fake_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as client_cls:
        client_instance = MagicMock()
        client_instance.__enter__.return_value = client_instance
        client_instance.post.return_value = fake_response
        client_cls.return_value = client_instance

        result = ai_clusterer.cluster_notes(notes)

    assert len(result) == 1
    assert result[0].title == "Enlarge dropzone"
    assert sorted(result[0].note_ids) == sorted(ids)


def test_cluster_notes_openrouter_http_mocked(db, monkeypatch):
    from backend.app.core.config import settings
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setattr(settings, "AI_CLUSTERER_PROVIDER", "openrouter")

    notes = _make_notes(db, [
        "Fix invoicing emails",
        "Invoicing email typo",
    ])
    ids = [n.id for n in notes]

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"clusters":[{"title":"Fix invoicing emails","summary":"Admin cleanup","note_ids":' + str(ids) + "}]}",
                }
            }
        ]
    }
    fake_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as client_cls:
        client_instance = MagicMock()
        client_instance.__enter__.return_value = client_instance
        client_instance.post.return_value = fake_response
        client_cls.return_value = client_instance

        result = ai_clusterer.cluster_notes(notes)

    assert len(result) == 1
    assert "invoicing" in result[0].title.lower()


def test_cluster_notes_http_failure_falls_back(db, monkeypatch):
    from backend.app.core.config import settings
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-broken")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", None)
    monkeypatch.setattr(settings, "AI_CLUSTERER_PROVIDER", "anthropic")

    notes = _make_notes(db, [
        "Dropzone should be larger",
        "Make dropzone target bigger",
    ])

    with patch("httpx.Client") as client_cls:
        client_instance = MagicMock()
        client_instance.__enter__.return_value = client_instance
        client_instance.post.side_effect = Exception("boom")
        client_cls.return_value = client_instance

        # Should not raise — degrades to fallback
        result = ai_clusterer.cluster_notes(notes)

    # Fallback should still cluster the 2 similar notes
    assert len(result) >= 1
