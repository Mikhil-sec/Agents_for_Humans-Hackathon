"""Error handling.

Every non-2xx body is a contract `ApiError`. The `error` field is a stable
machine-readable code — the web app switches on it, so **never change a code
without changing the web app in the same PR.**
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from quiet_hours_contracts import ApiError

# The full set of codes the web app knows about. Keep this list in sync with
# `web/lib/errors.ts`.
DECISION_NOT_FOUND = "decision_not_found"
DECISION_NOT_PENDING = "decision_not_pending"
RUN_NOT_FOUND = "run_not_found"
POLICY_NOT_FOUND = "policy_not_found"
BRIEF_NOT_FOUND = "brief_not_found"
FIXTURES_MISSING = "fixtures_missing"
INVALID_REQUEST = "invalid_request"
INVALID_CHOICE = "invalid_choice"
AGENT_UNAVAILABLE = "agent_unavailable"
BACKEND_ERROR = "backend_error"


class ApiProblem(Exception):
    """Raised anywhere in the API; rendered as a contract `ApiError`.

    We do not use `HTTPException` because its body is `{"detail": ...}`, which is
    not the shape the contract promises.
    """

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _body(code: str, message: str) -> dict[str, str]:
    return ApiError(error=code, message=message).model_dump(mode="json")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiProblem)
    async def _problem(_: Request, exc: ApiProblem) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
        detail = first.get("msg", "request did not match the contract")
        return JSONResponse(
            status_code=422,
            content=_body(INVALID_REQUEST, f"{where}: {detail}" if where else detail),
        )

    @app.exception_handler(FileNotFoundError)
    async def _missing_fixture(_: Request, exc: FileNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=503, content=_body(FIXTURES_MISSING, str(exc)))
