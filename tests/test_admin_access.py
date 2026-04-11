import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.security import require_admin, create_access_token, set_auth_cookie
from backend.app.core.config import settings
from backend.app.database.models import User
from backend.app.database.session import get_db
from tests.conftest import TestingSessionLocal, override_get_db


def _make_user(db: Session, *, username: str, email: str, is_admin: bool = False) -> User:
    user = User(
        username=username,
        email=email,
        password_hash="x",
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_require_admin_rejects_non_admin(db):
    user = _make_user(db, username="normie", email="normie@example.com", is_admin=False)
    with pytest.raises(HTTPException) as exc:
        require_admin(current_user=user)
    assert exc.value.status_code == 403


def test_require_admin_allows_admin(db):
    admin = _make_user(db, username="boss", email="sjpenn@gmail.com", is_admin=True)
    result = require_admin(current_user=admin)
    assert result.id == admin.id
