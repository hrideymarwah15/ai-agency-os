"""Auth flow tests — D-16 cookie flags, uniform login failure, audit write, session guard."""

import conftest
from sqlalchemy import select, text

LOGIN_DATA = {"email": "owner@test.local"}


def _client():
    """TestClient with the app imported AFTER fixtures set the test env."""
    from fastapi.testclient import TestClient

    from backend.main import app

    return TestClient(app, follow_redirects=False)


def _login(client):
    return client.post(
        "/auth/login",
        data={**LOGIN_DATA, "password": conftest.TEST_OWNER_PASSWORD},
    )


def test_login_success_sets_session_cookie(migrated_db):
    with _client() as client:
        response = _login(client)
    assert response.status_code == 302
    assert response.headers["location"] == "/approvals"  # landing page per UI-SPEC (plan 01-03)
    set_cookie = response.headers["set-cookie"].lower()
    assert "session=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "secure" not in set_cookie  # cookie_secure=false in the test env
    assert "max-age=43200" in set_cookie  # session_ttl_seconds


def test_login_cookie_secure_flag_when_enabled(migrated_db):
    import os

    import backend.config as config_module

    os.environ["COOKIE_SECURE"] = "true"
    config_module.get_settings.cache_clear()
    config_module.settings = config_module.get_settings()
    with _client() as client:
        response = _login(client)
    assert "secure" in response.headers["set-cookie"].lower()


def test_login_wrong_password_uniform_flash(migrated_db):
    with _client() as client:
        response = client.post(
            "/auth/login",
            data={**LOGIN_DATA, "password": "wrong-password"},
        )
    assert response.status_code == 200
    assert "Invalid email or password." in response.text


def test_login_wrong_email_uniform_flash(migrated_db):
    with _client() as client:
        response = client.post(
            "/auth/login",
            data={"email": "someone@else.test", "password": conftest.TEST_OWNER_PASSWORD},
        )
    assert response.status_code == 200
    assert "Invalid email or password." in response.text


async def test_login_writes_owner_login_audit_row(migrated_db, test_session):
    from backend.database import AuditLog

    # TRUNCATE, not DELETE: plan 02's append-only trigger rejects DELETEs (T-02-01).
    await test_session.execute(text("TRUNCATE audit_logs"))
    await test_session.commit()

    with _client() as client:
        response = _login(client)
    assert response.status_code == 302

    result = await test_session.execute(select(AuditLog).where(AuditLog.action == "owner_login"))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].actor == "owner"
    assert rows[0].entity_type == "owner"
    assert rows[0].entity_id == "owner@test.local"
    assert rows[0].correlation_id


async def test_audit_page_renders_owner_login(migrated_db, test_session):
    # TRUNCATE, not DELETE: plan 02's append-only trigger rejects DELETEs (T-02-01).
    await test_session.execute(text("TRUNCATE audit_logs"))
    await test_session.commit()

    with _client() as client:
        login = _login(client)
        assert login.status_code == 302
        response = client.get("/audit")
    assert response.status_code == 200
    assert "owner_login" in response.text


def test_audit_without_session_redirects_to_login(migrated_db):
    with _client() as client:
        response = client.get("/audit")
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/login"


def test_tampered_session_cookie_redirects_to_login(migrated_db):
    with _client() as client:
        assert _login(client).status_code == 302
        client.cookies.set("session", "forged-signature")
        response = client.get("/audit")
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/login"


def test_logout_clears_cookie(migrated_db):
    with _client() as client:
        assert _login(client).status_code == 302
        response = client.post("/auth/logout")
        assert response.status_code == 302
        assert response.headers["location"] == "/auth/login"
        after = client.get("/audit")
    assert after.status_code == 302
