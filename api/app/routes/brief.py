"""`/api/brief/latest` — the daily brief, and a preview of the email it becomes.

`GET /api/brief/latest` is the frozen route and returns the contract `DailyBrief`.
`GET /api/brief/latest/preview` renders the same brief as the digest email, so the
template can be looked at without sending anything. Rendering is pure; nothing on
this router can send mail.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse

from ..backends import get_backend
from ..digest import render_html, render_text, subject_for
from ..errors import BRIEF_NOT_FOUND, ApiProblem

router = APIRouter(prefix="/api/brief", tags=["brief"])

APP_URL = os.environ.get("QH_APP_URL", "http://localhost:3000")


def _latest():
    brief = get_backend().latest_brief()
    if brief is None:
        raise ApiProblem(BRIEF_NOT_FOUND, "the agent has not produced a brief yet", 404)
    return brief


@router.get("/latest")
def latest_brief() -> dict[str, Any]:
    return _latest().model_dump(mode="json")


@router.get("/latest/preview", response_class=HTMLResponse)
def preview_digest() -> HTMLResponse:
    """The digest email as it will arrive. Handy for a screenshot, and the only
    way to review the template without an SES identity."""
    return HTMLResponse(render_html(_latest(), get_backend().household(), app_url=APP_URL))


@router.get("/latest/preview.txt", response_class=PlainTextResponse)
def preview_digest_text() -> PlainTextResponse:
    """The plain-text alternative, with the subject line on top."""
    brief = _latest()
    body = render_text(brief, get_backend().household(), app_url=APP_URL)
    return PlainTextResponse(f"Subject: {subject_for(brief)}\n\n{body}")
