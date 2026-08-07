from unittest.mock import patch

from backend.app.core.config import settings
from backend.app.core.security import (
    create_password_reset_token,
    hash_password,
    verify_password,
    verify_password_reset_token,
)
from backend.app.database.models import User


def _make_user(db, username="resetme", email="resetme@example.com"):
    user = User(
        username=username,
        email=email,
        password_hash=hash_password("OldPass!234"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_register_accepts_optional_email(client, db):
    response = client.post(
        "/api/auth/register",
        data={"username": "withemail", "password": "Str0ngPass!23", "email": "me@example.com"},
    )
    assert response.status_code == 200, response.text
    user = db.query(User).filter(User.username == "withemail").first()
    assert user.email == "me@example.com"


def test_register_rejects_bad_email(client, db):
    response = client.post(
        "/api/auth/register",
        data={"username": "bademail", "password": "Str0ngPass!23", "email": "not-an-email"},
    )
    assert response.status_code == 400


def test_forgot_always_returns_ok_and_sends_when_email_exists(client, db):
    user = _make_user(db)
    with patch("backend.app.routes.auth.send_password_reset", return_value=True) as mock_send:
        response = client.post("/api/auth/forgot", data={"identifier": user.username})
    assert response.status_code == 200
    assert response.json()["ok"] is True
    mock_send.assert_called_once()
    reset_url = mock_send.call_args[0][1]
    assert "/reset?token=" in reset_url


def test_forgot_unknown_account_still_returns_ok(client, db):
    with patch("backend.app.routes.auth.send_password_reset") as mock_send:
        response = client.post("/api/auth/forgot", data={"identifier": "ghost"})
    assert response.status_code == 200
    mock_send.assert_not_called()


def test_reset_with_valid_token_changes_password(client, db):
    user = _make_user(db, username="resetter", email="resetter@example.com")
    token = create_password_reset_token(user.id)

    response = client.post(
        "/api/auth/reset",
        data={
            "token": token,
            "new_password": "BrandNew!234",
            "confirm_password": "BrandNew!234",
        },
    )
    assert response.status_code == 200, response.text
    db.refresh(user)
    assert verify_password("BrandNew!234", user.password_hash)

    login = client.post(
        "/api/auth/login",
        data={"username": "resetter", "password": "BrandNew!234"},
    )
    assert login.status_code == 200


def test_reset_with_invalid_token_fails(client, db):
    response = client.post(
        "/api/auth/reset",
        data={
            "token": "garbage.token.value",
            "new_password": "BrandNew!234",
            "confirm_password": "BrandNew!234",
        },
    )
    assert response.status_code == 400


def test_reset_token_rejects_access_tokens(db):
    # A normal session token must never work as a reset token.
    from backend.app.core.security import create_access_token

    token = create_access_token("1")
    assert verify_password_reset_token(token) is None


def test_reset_mismatched_passwords_fail(client, db):
    user = _make_user(db, username="mismatch", email="mismatch@example.com")
    token = create_password_reset_token(user.id)
    response = client.post(
        "/api/auth/reset",
        data={
            "token": token,
            "new_password": "BrandNew!234",
            "confirm_password": "Different!234",
        },
    )
    assert response.status_code == 400


def test_forgot_and_reset_pages_render(client):
    assert client.get("/forgot").status_code == 200
    assert client.get("/reset?token=abc").status_code == 200
