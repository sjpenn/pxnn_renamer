from backend.app.core.security import create_access_token
from backend.app.core.config import settings
from backend.app.database.models import Campaign, CampaignVariant, CampaignImage, User


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


def test_campaigns_list_requires_admin(client, db):
    _login(client, db, is_admin=False)
    r = client.get("/admin/campaigns")
    assert r.status_code == 403


def test_campaigns_list_empty(client, db):
    _login(client, db, is_admin=True)
    r = client.get("/admin/campaigns")
    assert r.status_code == 200
    assert "No campaigns yet" in r.text


def test_campaign_create(client, db):
    admin = _login(client, db, is_admin=True)
    r = client.post(
        "/admin/campaigns",
        data={
            "name": "Summer Beat Sale",
            "product_description": "PxNN filename studio",
            "target_audience": "Hip hop producers",
            "offer": "10 free credits",
            "tone": "hype",
            "placements": "feed,story",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "/admin/campaigns/" in r.headers["location"]

    campaign = db.query(Campaign).first()
    assert campaign is not None
    assert campaign.name == "Summer Beat Sale"
    assert campaign.admin_id == admin.id
    assert campaign.status == "draft"


def test_campaign_detail(client, db):
    admin = _login(client, db, is_admin=True)
    c = Campaign(
        admin_id=admin.id,
        name="Test Campaign",
        product_description="desc",
        target_audience="audience",
        tone="authentic",
        placements="feed",
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    r = client.get(f"/admin/campaigns/{c.id}")
    assert r.status_code == 200
    assert "Test Campaign" in r.text


def test_campaign_detail_404(client, db):
    _login(client, db, is_admin=True)
    r = client.get("/admin/campaigns/999")
    assert r.status_code == 404


def test_campaign_delete(client, db):
    admin = _login(client, db, is_admin=True)
    c = Campaign(
        admin_id=admin.id,
        name="Delete Me",
        product_description="d",
        target_audience="a",
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    r = client.post(f"/admin/campaigns/{c.id}/delete", follow_redirects=False)
    assert r.status_code == 303
    assert db.query(Campaign).count() == 0


def test_new_campaign_form(client, db):
    _login(client, db, is_admin=True)
    r = client.get("/admin/campaigns/new")
    assert r.status_code == 200
    assert "New Campaign" in r.text


def test_toggle_variant_favorite(client, db):
    admin = _login(client, db, is_admin=True)
    c = Campaign(
        admin_id=admin.id,
        name="Fav Test",
        product_description="d",
        target_audience="a",
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    v = CampaignVariant(
        campaign_id=c.id,
        headline="Test",
        primary_text="Body",
        cta="Learn More",
    )
    db.add(v)
    db.commit()
    db.refresh(v)

    assert v.is_favorite is False

    r = client.post(
        f"/admin/campaigns/{c.id}/variants/{v.id}/favorite",
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.refresh(v)
    assert v.is_favorite is True

    # Toggle off
    r = client.post(
        f"/admin/campaigns/{c.id}/variants/{v.id}/favorite",
        follow_redirects=False,
    )
    db.refresh(v)
    assert v.is_favorite is False


def test_toggle_image_favorite(client, db):
    admin = _login(client, db, is_admin=True)
    c = Campaign(
        admin_id=admin.id,
        name="Img Fav",
        product_description="d",
        target_audience="a",
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    img = CampaignImage(
        campaign_id=c.id,
        prompt="test",
        image_url="https://example.com/img.png",
        aspect_ratio="1:1",
    )
    db.add(img)
    db.commit()
    db.refresh(img)

    r = client.post(
        f"/admin/campaigns/{c.id}/images/{img.id}/favorite",
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.refresh(img)
    assert img.is_favorite is True


def test_export_csv(client, db):
    admin = _login(client, db, is_admin=True)
    c = Campaign(
        admin_id=admin.id,
        name="Export Test",
        product_description="d",
        target_audience="a",
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    db.add(CampaignVariant(
        campaign_id=c.id,
        headline="Head",
        primary_text="Body",
        cta="Learn More",
        is_favorite=True,
    ))
    db.add(CampaignImage(
        campaign_id=c.id,
        prompt="test",
        image_url="https://example.com/img.png",
        aspect_ratio="1:1",
        is_favorite=True,
    ))
    db.commit()

    r = client.get(f"/admin/campaigns/{c.id}/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "Head" in r.text
    assert "https://example.com/img.png" in r.text

    db.refresh(c)
    assert c.status == "exported"


def test_export_requires_admin(client, db):
    _login(client, db, is_admin=False)
    r = client.get("/admin/campaigns/1/export")
    assert r.status_code == 403


def test_detail_shows_meta_mockup_when_both_exist(client, db):
    admin = _login(client, db, is_admin=True)
    c = Campaign(
        admin_id=admin.id,
        name="Mockup Test",
        product_description="d",
        target_audience="a",
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    db.add(CampaignVariant(
        campaign_id=c.id,
        headline="Great Ad",
        primary_text="Buy now",
        cta="Shop Now",
    ))
    db.add(CampaignImage(
        campaign_id=c.id,
        prompt="photo",
        image_url="https://example.com/img.png",
        aspect_ratio="1:1",
    ))
    db.commit()

    r = client.get(f"/admin/campaigns/{c.id}")
    assert r.status_code == 200
    assert "Great Ad" in r.text
    assert "Sponsored" in r.text
    assert "Meta Feed" in r.text
