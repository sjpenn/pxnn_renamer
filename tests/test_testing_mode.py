from backend.app.core.security import has_unlimited_access, serialize_user
from backend.app.database.models import User


def test_has_unlimited_access_true_for_testing_user():
    u = User(username="t", email="t@x.com", password_hash="x", is_testing=True, credit_balance=0)
    assert has_unlimited_access(u) is True


def test_has_unlimited_access_false_for_normal_user():
    u = User(username="n", email="n@x.com", password_hash="x", is_testing=False, credit_balance=0)
    assert has_unlimited_access(u) is False


def test_has_unlimited_access_false_for_none():
    assert has_unlimited_access(None) is False


def test_serialize_user_includes_is_testing():
    u = User(
        id=1,
        username="s",
        email="s@x.com",
        password_hash="x",
        is_testing=True,
        credit_balance=5,
        active_plan="free",
        plan_status="inactive",
    )
    data = serialize_user(u)
    assert data["is_testing"] is True
