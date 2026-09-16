import secrets

from fastapi import Header, HTTPException, status

from secure.config import get_settings


def require_api_key(authorization: str | None = Header(default=None)) -> None:
    expected = f"Bearer {get_settings().admin_api_key}"
    if authorization is None or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
