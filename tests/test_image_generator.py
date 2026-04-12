from unittest.mock import patch, MagicMock

from backend.app.database.models import Campaign, CampaignImage, User
from backend.app.services import image_generator
from backend.app.services.image_generator import ImageResult, generate_images, _via_fallback, _build_prompts
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
        name="Image Test",
        product_description="PxNN filename studio",
        target_audience="Hip hop producers",
        tone="authentic",
        placements="feed,story",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_build_prompts_returns_correct_count(db):
    c = _campaign(db)
    prompts = _build_prompts(c, count=3)
    assert len(prompts) == 3
    for p in prompts:
        assert "prompt" in p
        assert "aspect_ratio" in p


def test_fallback_returns_placehold_url():
    url = _via_fallback("test prompt", "1:1")
    assert "placehold.co" in url
    assert "1024x1024" in url


def test_generate_images_uses_fallback_when_no_token(db, monkeypatch):
    monkeypatch.setattr(settings, "REPLICATE_API_TOKEN", None)
    c = _campaign(db)
    results = generate_images(c, count=3)
    assert len(results) == 3
    for r in results:
        assert "placehold.co" in r.image_url


def test_generate_images_replicate_mocked(db, monkeypatch):
    monkeypatch.setattr(settings, "REPLICATE_API_TOKEN", "test-token")
    c = _campaign(db)

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "status": "succeeded",
        "output": ["https://replicate.delivery/test-image.png"],
    }
    fake_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as client_cls:
        client_instance = MagicMock()
        client_instance.__enter__.return_value = client_instance
        client_instance.post.return_value = fake_response
        client_cls.return_value = client_instance

        results = generate_images(c, count=2)

    assert len(results) == 2
    assert "replicate.delivery" in results[0].image_url


def test_generate_images_replicate_failure_falls_back(db, monkeypatch):
    monkeypatch.setattr(settings, "REPLICATE_API_TOKEN", "broken-token")
    c = _campaign(db)

    with patch("httpx.Client") as client_cls:
        client_instance = MagicMock()
        client_instance.__enter__.return_value = client_instance
        client_instance.post.side_effect = Exception("boom")
        client_cls.return_value = client_instance

        results = generate_images(c, count=2)

    assert len(results) == 2
    for r in results:
        assert "placehold.co" in r.image_url  # fell back


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


def test_generate_images_endpoint(client, db, monkeypatch):
    monkeypatch.setattr(settings, "REPLICATE_API_TOKEN", None)
    admin = _login(client, db, is_admin=True)
    c = _campaign(db, admin_id=admin.id)

    r = client.post(
        f"/admin/campaigns/{c.id}/generate-images",
        follow_redirects=False,
    )
    assert r.status_code == 303

    db.refresh(c)
    assert len(c.images) == 4
    assert c.images[0].image_url is not None


def test_generate_images_endpoint_requires_admin(client, db):
    _login(client, db, is_admin=False)
    r = client.post("/admin/campaigns/1/generate-images")
    assert r.status_code == 403
