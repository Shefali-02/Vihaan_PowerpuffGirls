"""Domain errors and the problem+json handler. `code` values are a stable contract."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("munshi.errors")

# Stable error code list (documented in README).
ERROR_CODES: dict[str, str] = {
    "VALIDATION_ERROR": "Request body or parameters are invalid",
    "UNAUTHENTICATED": "Missing or invalid bearer token",
    "FORBIDDEN": "Authenticated but not allowed",
    "ROLE_NOT_PERMITTED": "Your role cannot perform this action",
    "SELF_APPROVAL_FORBIDDEN": "Preparer cannot approve their own object",
    "NOT_FOUND": "Resource not found in this workspace",
    "CONFLICT": "State conflict",
    "INVALID_STATE_TRANSITION": "Workflow transition not allowed from current state",
    "VERSION_HASH_MISMATCH": "Object changed since approval was requested",
    "PERIOD_NOT_FOUND": "No accounting period covers this date",
    "PERIOD_LOCKED": "Period is locked; post a reversal in an open period",
    "PERIOD_CLOSE_NOT_APPROVED": "Period close must be approved before publishing",
    "UNBALANCED_JOURNAL": "Debits do not equal credits",
    "DRAFT_MISMATCH": "Draft no longer matches what the rules engine produces",
    "RULE_REJECTED": "Rules engine rejected the input",
    "IMMUTABLE_RECORD": "Posted journals and audit events cannot be changed",
    "DUPLICATE_DOCUMENT": "Document already ingested",
    "UNSUPPORTED_DOCUMENT": "File type not supported",
    "MANUAL_ENTRY_REQUIRED": "AI extraction unavailable; enter the journal manually",
    "NOT_ENABLED": "Live integration not enabled in this MVP",
    "ANCHOR_FAILED": "Could not anchor the Merkle root",
    "IDEMPOTENCY_KEY_REUSED": "Idempotency-Key reused for a different request",
    "INTERNAL": "Unexpected server error",
}


class DomainError(Exception):
    status = 400
    code = "VALIDATION_ERROR"

    def __init__(self, detail: str | None = None, *, extra: dict[str, Any] | None = None):
        super().__init__(detail or ERROR_CODES.get(self.code, self.code))
        self.detail = detail or ERROR_CODES.get(self.code, self.code)
        self.extra = extra or {}


class ValidationFailed(DomainError):
    status, code = 422, "VALIDATION_ERROR"


class Unauthenticated(DomainError):
    status, code = 401, "UNAUTHENTICATED"


class Forbidden(DomainError):
    status, code = 403, "FORBIDDEN"


class RoleNotPermitted(DomainError):
    status, code = 403, "ROLE_NOT_PERMITTED"


class SelfApprovalForbidden(DomainError):
    status, code = 403, "SELF_APPROVAL_FORBIDDEN"


class NotFound(DomainError):
    status, code = 404, "NOT_FOUND"


class Conflict(DomainError):
    status, code = 409, "CONFLICT"


class InvalidTransition(DomainError):
    status, code = 409, "INVALID_STATE_TRANSITION"


class VersionHashMismatch(DomainError):
    status, code = 409, "VERSION_HASH_MISMATCH"


class PeriodNotFound(DomainError):
    status, code = 422, "PERIOD_NOT_FOUND"


class PeriodLocked(DomainError):
    status, code = 409, "PERIOD_LOCKED"


class PeriodCloseNotApproved(DomainError):
    status, code = 409, "PERIOD_CLOSE_NOT_APPROVED"


class UnbalancedJournal(DomainError):
    status, code = 422, "UNBALANCED_JOURNAL"


class DraftMismatch(DomainError):
    status, code = 409, "DRAFT_MISMATCH"


class RuleRejected(DomainError):
    status, code = 422, "RULE_REJECTED"


class ImmutableRecord(DomainError):
    status, code = 409, "IMMUTABLE_RECORD"


class DuplicateDocument(DomainError):
    status, code = 409, "DUPLICATE_DOCUMENT"


class UnsupportedDocument(DomainError):
    status, code = 415, "UNSUPPORTED_DOCUMENT"


class ManualEntryRequired(DomainError):
    status, code = 422, "MANUAL_ENTRY_REQUIRED"


class NotEnabledError(DomainError):
    status, code = 501, "NOT_ENABLED"


class AnchorFailed(DomainError):
    status, code = 502, "ANCHOR_FAILED"


class IdempotencyKeyReused(DomainError):
    status, code = 422, "IDEMPOTENCY_KEY_REUSED"


def problem(status: int, code: str, detail: str, instance: str = "", **extra: Any) -> JSONResponse:
    body = {
        "type": f"https://munshi.demo/errors/{code.lower()}",
        "title": ERROR_CODES.get(code, code),
        "status": status,
        "code": code,
        "detail": detail,
        "instance": instance,
        **extra,
    }
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(request: Request, exc: DomainError):
        return problem(exc.status, exc.code, exc.detail, str(request.url.path), **exc.extra)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        errors = [{"loc": list(e.get("loc", [])), "msg": e.get("msg")} for e in exc.errors()]
        return problem(422, "VALIDATION_ERROR", "Request validation failed", str(request.url.path), errors=errors)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND"}.get(exc.status_code, "CONFLICT")
        return problem(exc.status_code, code, str(exc.detail), str(request.url.path))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("unhandled error")
        return problem(500, "INTERNAL", "Unexpected server error", str(request.url.path))
