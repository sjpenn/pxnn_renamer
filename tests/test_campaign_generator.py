from unittest.mock import patch, MagicMock

from backend.app.database.models import Campaign, CampaignVariant, User
from backend.app.services import campaign_generator
from backend.app.services.campaign_generator import CopyVariant, _via_fallback, generate_copy
from backend.app.core.security import create_access_token
from backend.app.core.config import settings


def _campaign(db, admin_id=None):
    if admin_id is None:
        u = User(username="a", email="a@x.com", password_hash="x", is_admin=True)
        db.add(u)
        db.commit()
        db.refresh(u)
        admin_id = u.id
    c = Campaign(
        admin_id=admin_id,
        name="Test Campaign",
        product_description="PxNN filename studio for beatmakers",
        target_audience="Hip hop producers, soul beatmakers",
        offer="10 free credits",
        tone="authentic",
        placements="feed,story",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_fallback_returns_4_variants(db):
    c = _campaign(db)
    result = _via_fallback(c)
    assert len(result) == 4
    for v in result:
        assert v.headline
        assert v.primary_text
        assert v.cta


def test_generate_copy_uses_fallback_when_no_keys(db, monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", None)
    monkeypatch.setattr(settings, "AI_CLUSTERER_PROVIDER", "auto")

    c = _campaign(db)
    result = generate_copy(c)
    assert len(result) == 4


def test_generate_copy_anthropic_mocked(db, monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", None)
    monkeypatch.setattr(settings, "AI_CLUSTERER_PROVIDER", "anthropic")

    c = _campaign(db)

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "content": [{"type": "text", "text": '{"variants":[{"headline":"Test Head","primary_text":"Test body","description":"desc","cta":"Learn More"}]}'}]
    }
    fake_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as client_cls:
        client_instance = MagicMock()
        client_instance.__enter__.return_value = client_instance
        client_instance.post.return_value = fake_response
        client_cls.return_value = client_instance

        result = generate_copy(c)

    assert len(result) == 1
    assert result[0].headline == "Test Head"


def test_generate_copy_openrouter_mocked(db, monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setattr(settings, "AI_CLUSTERER_PROVIDER", "openrouter")

    c = _campaign(db)

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "choices": [{"message": {"content": '{"variants":[{"headline":"OR Head","primary_text":"OR body","description":"d","cta":"Sign Up"}]}'}}]
    }
    fake_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as client_cls:
        client_instance = MagicMock()
        client_instance.__enter__.return_value = client_instance
        client_instance.post.return_value = fake_response
        client_cls.return_value = client_instance

        result = generate_copy(c)

    assert len(result) == 1
    assert result[0].headline == "OR Head"


def test_generate_copy_http_failure_falls_back(db, monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-broken")
    monkeypatch.setattr(settings, "AI_CLUSTERER_PROVIDER", "anthropic")

    c = _campaign(db)

    with patch("httpx.Client") as client_cls:
        client_instance = MagicMock()
        client_instance.__enter__.return_value = client_instance
        client_instance.post.side_effect = Exception("boom")
        client_cls.return_value = client_instance

        result = generate_copy(c)

    assert len(result) == 4  # fallback


def _login(client, db, *, is_admin: bool):
    u = User(
        username=("admin" if is_admin else "normie"),
        email=("sjpenn@gmail.com" if is_admin else "n@x.com"),
        password_hash="x",
        is_admin=is_admin,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    client.cookies.set(settings.COOKIE_NAME, create_access_token(str(u.id)))
    return u


def test_generate_copy_endpoint_creates_variants(client, db, monkeypatch):
    monkeypatch.setattr(settings, "AI_CLUSTERER_PROVIDER", "fallback")
    admin = _login(client, db, is_admin=True)
    c = _campaign(db, admin_id=admin.id)

    r = client.post(
        f"/admin/campaigns/{c.id}/generate-copy",
        follow_redirects=False,
    )
    assert r.status_code == 303

    db.refresh(c)
    assert c.status == "ready"
    assert len(c.variants) == 4


def test_generate_copy_endpoint_requires_admin(client, db):
    _login(client, db, is_admin=False)
    r = client.post("/admin/campaigns/1/generate-copy")
    assert r.status_code == 403
