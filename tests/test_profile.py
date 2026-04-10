import pytest

from backend.app.core.security import hash_password
from backend.app.database.models import User


def _create_user(db, username="profileuser", password="oldpassword123"):
    user = User(
        username=username,
        password_hash=hash_password(password),
        credit_balance=0,
    )
    db.add(user)
    db.commit()
    return user


def _login(client, username, password):
    response = client.post("/api/auth/login", data={"username": username, "password": password})
    assert response.status_code == 200
    return response.cookies


def test_password_update_success(client, db):
    _create_user(db, username="pwuser1", password="oldpassword123")
    _login(client, "pwuser1", "oldpassword123")

    response = client.post("/api/profile/password", data={
        "current_password": "oldpassword123",
        "new_password": "newpassword456",
        "confirm_password": "newpassword456",
    })
    assert response.status_code == 200
    assert response.json() == {"ok": True}

    relogin = client.post("/api/auth/login", data={"username": "pwuser1", "password": "newpassword456"})
    assert relogin.status_code == 200


def test_password_update_wrong_current(client, db):
    _create_user(db, username="pwuser2", password="rightpass123")
    _login(client, "pwuser2", "rightpass123")

    response = client.post("/api/profile/password", data={
        "current_password": "wrongpass",
        "new_password": "newpassword456",
        "confirm_password": "newpassword456",
    })
    assert response.status_code == 401


def test_password_update_mismatched_confirmation(client, db):
    _create_user(db, username="pwuser3", password="rightpass123")
    _login(client, "pwuser3", "rightpass123")

    response = client.post("/api/profile/password", data={
        "current_password": "rightpass123",
        "new_password": "newpassword456",
        "confirm_password": "differentpass",
    })
    assert response.status_code == 400


def test_password_update_weak_password(client, db):
    _create_user(db, username="pwuser4", password="rightpass123")
    _login(client, "pwuser4", "rightpass123")

    response = client.post("/api/profile/password", data={
        "current_password": "rightpass123",
        "new_password": "short",
        "confirm_password": "short",
    })
    assert response.status_code == 400


def test_password_update_google_only_user(client, db):
    user = User(username="googleuser", password_hash=None, google_sub="google_sub_abc", credit_balance=0)
    db.add(user)
    db.commit()

    from backend.app.core.security import create_access_token
    from backend.app.core.config import settings

    token = create_access_token(str(user.id))
    client.cookies.set(settings.COOKIE_NAME, token)

    response = client.post("/api/profile/password", data={
        "current_password": "anything",
        "new_password": "newpassword456",
        "confirm_password": "newpassword456",
    })
    assert response.status_code == 400


def test_delete_account_success(client, db):
    _create_user(db, username="deluser1", password="delpass123")
    _login(client, "deluser1", "delpass123")

    response = client.post("/api/profile/delete", data={"username_confirmation": "deluser1"})
    assert response.status_code == 200

    db.expire_all()
    assert db.query(User).filter(User.username == "deluser1").first() is None


def test_delete_account_wrong_username(client, db):
    _create_user(db, username="deluser2", password="delpass123")
    _login(client, "deluser2", "delpass123")

    response = client.post("/api/profile/delete", data={"username_confirmation": "wrongname"})
    assert response.status_code == 400
