import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import router
from app.core.config import Settings
from app.core.logging import configure_logging
from app.core.rate_limit import limiter
from app.core.request_id import REQUEST_ID_HEADER, resolve_request_id
from app.db.session import build_engine, build_session_factory

logger = logging.getLogger(__name__)
MAX_BODY_BYTES = 16_384
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    configure_logging(config.log_level)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        engine = build_engine(config)
        application.state.session_factory = build_session_factory(engine)
        logger.info("startup environment=%s version=%s", config.environment, config.app_version)
        try:
            yield
        finally:
            engine.dispose()
            logger.info("shutdown")

    application = FastAPI(
        title=config.app_name,
        version=config.app_version,
        description="Med Robots contact API. Not deployed to production.",
        lifespan=lifespan,
    )
    application.state.limiter = limiter
    application.add_middleware(SlowAPIMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.allowed_origins),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Idempotency-Key", "X-Request-ID"],
    )

    @application.middleware("http")
    async def request_logging_and_size(request: Request, call_next: Any):
        started = time.monotonic()
        request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
        request.state.request_id = request_id
        response = None
        origin = request.headers.get("origin")
        is_preflight = (
            request.method == "OPTIONS" and "access-control-request-method" in request.headers
        )
        if origin and origin not in config.allowed_origins and not is_preflight:
            response = JSONResponse(
                status_code=403,
                content={"error": {"code": "origin_not_allowed", "message": "Origin not allowed"}},
            )
        if request.method in {"POST", "PUT", "PATCH"}:
            if (
                request.headers.get("content-length", "").isdigit()
                and int(request.headers["content-length"]) > MAX_BODY_BYTES
            ):
                response = JSONResponse(
                    status_code=413,
                    content={
                        "error": {"code": "request_too_large", "message": "Request body too large"}
                    },
                )
            elif response is None:
                chunks = []
                size = 0
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > MAX_BODY_BYTES:
                        response = JSONResponse(
                            status_code=413,
                            content={
                                "error": {
                                    "code": "request_too_large",
                                    "message": "Request body too large",
                                }
                            },
                        )
                        break
                    chunks.append(chunk)
                if response is None:
                    request._body = b"".join(chunks)
        if response is None:
            response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            (time.monotonic() - started) * 1000,
        )
        return response

    @application.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, error: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(part) for part in item["loc"]), "message": item["msg"]}
            for item in error.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Invalid request data",
                    "details": details,
                }
            },
        )

    @application.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, error: StarletteHTTPException) -> JSONResponse:
        messages = {
            404: ("not_found", "Not found"),
            405: ("method_not_allowed", "Method not allowed"),
        }
        code, message = messages.get(error.status_code, ("http_error", "Request failed"))
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": code, "message": message}},
            headers=error.headers,
        )

    @application.exception_handler(RateLimitExceeded)
    async def rate_limit_error(_request: Request, _error: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"error": {"code": "rate_limit_exceeded", "message": "Too many requests"}},
        )

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        # Only the exception type is logged: bound parameters may contain personal data.
        logger.error("database error request_id=%s type=%s", request_id, type(error).__name__)
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "database_unavailable",
                    "message": "Service temporarily unavailable",
                }
            },
            headers={REQUEST_ID_HEADER: request_id} if request_id else None,
        )

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.exception("unexpected application error request_id=%s", request_id)
        headers = dict(SECURITY_HEADERS)
        if request_id:
            headers[REQUEST_ID_HEADER] = request_id
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Internal server error"}},
            headers=headers,
        )

    application.include_router(router)
    return application


app = create_app()
