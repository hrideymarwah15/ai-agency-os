"""Signed session-cookie helpers and flash-message cookie helpers for the owner UI."""

import json
from typing import Any

from fastapi import Request, Response
from itsdangerous import URLSafeTimedSerializer

from backend import config

# D-16: single owner session, signed with the session secret and a dedicated salt.
serializer = URLSafeTimedSerializer(config.settings.session_secret, salt="owner-session")


def create_session_cookie(response: Response, email: str) -> None:
    """Set the signed owner session cookie with the D-16 flags."""
    response.set_cookie(
        "session",
        serializer.dumps({"email": email}),
        httponly=True,
        secure=config.settings.cookie_secure,
        samesite="lax",
        max_age=config.settings.session_ttl_seconds,
    )


def clear_session_cookie(response: Response) -> None:
    """Delete the owner session cookie."""
    response.delete_cookie("session")


def set_flash(response: Response, message: str, kind: str = "error") -> None:
    """Queue a flash message (rendered on the next server-rendered page)."""
    response.set_cookie(
        "flash",
        json.dumps({"message": message, "kind": kind}),
        httponly=True,
        samesite="lax",
        max_age=60,
        path="/",
    )


def read_flash(request: Request) -> dict[str, Any] | None:
    """Read the queued flash message from the request cookies, if any."""
    raw = request.cookies.get("flash")
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "message" in data:
            return data
    except ValueError:
        pass
    return {"message": raw, "kind": "error"}


def clear_flash(response: Response) -> None:
    """Remove the flash cookie from the outgoing response."""
    response.delete_cookie("flash", path="/")
