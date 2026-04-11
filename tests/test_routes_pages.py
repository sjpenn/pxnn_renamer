import pytest

from backend.app.core.security import hash_password
from backend.app.database.models import User


def _create_and_login(client, db, username="routesuser", password="testpass123"):
    user = User(
        username=username,
        password_hash=hash_password(password),
        credit_balance=0,
    )
    db.add(user)
    db.commit()
    response = client.post("/api/auth/login", data={"username": username, "password": password})
    assert response.status_code == 200


def test_home_renders_for_anonymous(client, db):
    response = client.get("/")
    assert response.status_code == 200
    assert "PxNN" in response.text
    assert "Get Started" in response.text


def test_home_redirects_authenticated_to_app(client, db):
    _create_and_login(client, db, username="homeauth")
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/app"


def test_app_requires_auth(client, db):
    response = client.get("/app", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_app_renders_for_authenticated(client, db):
    _create_and_login(client, db, username="appuser")
    response = client.get("/app")
    assert response.status_code == 200


def test_login_page_renders_for_anonymous(client, db):
    response = client.get("/login")
    assert response.status_code == 200
    assert "Sign in to PxNN" in response.text


def test_login_page_redirects_authenticated_to_app(client, db):
    _create_and_login(client, db, username="loginauth")
    response = client.get("/login", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/app"


def test_register_page_renders_for_anonymous(client, db):
    response = client.get("/register")
    assert response.status_code == 200
    assert "Create your PxNN account" in response.text


def test_register_page_redirects_authenticated_to_app(client, db):
    _create_and_login(client, db, username="regauth")
    response = client.get("/register", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/app"


def test_register_stores_pending_plan_in_session(client, db):
    response = client.get("/register?plan=pro_monthly")
    assert response.status_code == 200
    assert "Create your PxNN account" in response.text


def test_profile_page_renders_for_authenticated(client, db):
    _create_and_login(client, db, username="profilepage")
    response = client.get("/profile")
    assert response.status_code == 200
    assert "Profile" in response.text
    assert "profilepage" in response.text


def test_profile_page_redirects_anonymous(client, db):
    response = client.get("/profile", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
