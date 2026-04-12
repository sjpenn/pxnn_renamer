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
