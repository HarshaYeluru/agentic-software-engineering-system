from __future__ import annotations

import secrets
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator

from .store import LinkStore

DEFAULT_DATABASE = Path("data") / "url_shortener.sqlite3"
CODE_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
MAX_CODE_GENERATION_ATTEMPTS = 5


class CreateLinkRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2_048)
    expires_at: datetime | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be an absolute http or https URL")
        return value


class CreateLinkResponse(BaseModel):
    code: str
    short_url: str


class AnalyticsResponse(BaseModel):
    code: str
    clicks: int
    period: str = "all_time"


def create_app(database_path: str | Path = DEFAULT_DATABASE) -> FastAPI:
    """Create an app instance; accepting a path keeps tests isolated from local data."""
    store = LinkStore(database_path)
    store.initialize()
    app = FastAPI(
        title="URL Shortener",
        version="0.1.0",
        description="Reference service generated for the agentic engineering assignment.",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/links", response_model=CreateLinkResponse, status_code=status.HTTP_201_CREATED)
    def create_link(payload: CreateLinkRequest, request: Request) -> CreateLinkResponse:
        expires_at = payload.expires_at
        if expires_at is not None:
            if expires_at.tzinfo is None:
                raise HTTPException(status_code=422, detail="expires_at must include a timezone")
            if expires_at <= datetime.now(UTC):
                raise HTTPException(status_code=422, detail="expires_at must be in the future")
        normalized_expiry = expires_at.astimezone(UTC).isoformat() if expires_at else None
        for _ in range(MAX_CODE_GENERATION_ATTEMPTS):
            code = _generate_code()
            if store.create_link(code, payload.url, normalized_expiry):
                base_url = str(request.base_url).rstrip("/")
                return CreateLinkResponse(code=code, short_url=f"{base_url}/{code}")
        raise HTTPException(status_code=503, detail="could not allocate a unique short code; retry request")

    @app.get("/{code}", status_code=status.HTTP_302_FOUND)
    def redirect(code: str) -> RedirectResponse:
        destination = store.find_active_link(code)
        if destination is None:
            raise HTTPException(status_code=404, detail="short link not found or expired")
        store.record_click(code)
        return RedirectResponse(url=destination, status_code=status.HTTP_302_FOUND)

    @app.get("/v1/links/{code}/analytics", response_model=AnalyticsResponse)
    def get_analytics(code: str) -> AnalyticsResponse:
        clicks = store.analytics(code)
        if clicks is None:
            raise HTTPException(status_code=404, detail="short link not found")
        return AnalyticsResponse(code=code, clicks=clicks)

    return app


def _generate_code(length: int = 7) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


app = create_app()
