from backend.app.core.security import authenticate_user, serialize_user
from backend.app.database.models import User


def _make_user(**kwargs):
    defaults = {
        "id": 1,
        "username": "testuser",
        "password_hash": None,
        "email": "test@example.com",
        "credit_balance": 5,
        "active_plan": "pro_monthly",
        "plan_status": "active",
        "subscription_status": "active",
        "subscription_plan": "pro_monthly",
        "created_at": None,
    }
    defaults.update(kwargs)
    u = User.__new__(User)
    for k, v in defaults.items():
        setattr(u, k, v)
    return u


def test_serialize_user_includes_email():
    user = _make_user(email="artist@example.com")
    result = serialize_user(user)
    assert result["email"] == "artist@example.com"


def test_serialize_user_includes_subscription_status():
    user = _make_user(subscription_status="active", subscription_plan="pro_monthly")
    result = serialize_user(user)
    assert result["subscription_status"] == "active"
    assert result["subscription_plan"] == "pro_monthly"


def test_serialize_user_none_returns_none():
    assert serialize_user(None) is None


def test_authenticate_user_google_only_returns_none(db):
    from backend.app.core.security import hash_password
    user = User(username="googleuser", password_hash=None, email="g@example.com", google_sub="sub123")
    db.add(user)
    db.commit()
    result = authenticate_user(db, "googleuser", "any_password")
    assert result is None
