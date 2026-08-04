"""Owner-guard FastAPI dependency — requires a valid signed session cookie (D-16)."""

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired

from backend import config
from backend.auth.session import serializer


def get_current_owner(request: Request) -> str:
    """Return the authenticated owner email or raise 401 (handled → /auth/login)."""
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = serializer.loads(token, max_age=config.settings.session_ttl_seconds)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return str(payload["email"])
