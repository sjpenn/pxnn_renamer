from backend.app.core.config import settings
from backend.app.core.rate_limit import reset_rate_limits


def test_login_rate_limit_returns_429(client):
    reset_rate_limits()
    limit = settings.RATE_LIMIT_LOGIN_PER_WINDOW
    last_status = None
    for _ in range(limit + 1):
        response = client.post(
            "/api/auth/login",
            data={"username": "nobody", "password": "wrongwrong"},
        )
        last_status = response.status_code
    assert last_status == 429
    assert "Too many attempts" in response.json()["detail"]


def test_register_rate_limit_returns_429(client):
    reset_rate_limits()
    limit = settings.RATE_LIMIT_REGISTER_PER_WINDOW
    last_status = None
    for i in range(limit + 1):
        response = client.post(
            "/api/auth/register",
            data={"username": f"ratelimituser{i}", "password": "Str0ngPass!23"},
        )
        last_status = response.status_code
    assert last_status == 429


def test_rate_limit_resets_between_tests(client):
    # The autouse fixture cleared the buckets — this login attempt should not be 429.
    response = client.post(
        "/api/auth/login",
        data={"username": "nobody", "password": "wrongwrong"},
    )
    assert response.status_code == 401
