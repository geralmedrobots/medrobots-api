import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.router import router
from app.core.config import Settings
from app.core.logging import configure_logging
from app.db.session import build_engine, build_session_factory

logger = logging.getLogger(__name__)
MAX_BODY_BYTES = 16_384


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    configure_logging(config.log_level)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        engine = build_engine(config.database_url)
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
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.allowed_origins),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @application.middleware("http")
    async def request_logging_and_size(request: Request, call_next: Any):
        started = time.monotonic()
        if request.method in {"POST", "PUT", "PATCH"}:
            if len(await request.body()) > MAX_BODY_BYTES:
                response = JSONResponse(
                    status_code=413,
                    content={
                        "error": {"code": "request_too_large", "message": "Request body too large"}
                    },
                )
                logger.warning(
                    "request method=%s path=%s status=413", request.method, request.url.path
                )
                return response
        response = await call_next(request)
        logger.info(
            "request method=%s path=%s status=%s duration_ms=%.1f",
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

    @application.exception_handler(SQLAlchemyError)
    async def database_error(_request: Request, error: SQLAlchemyError) -> JSONResponse:
        logger.error("database error: %s", type(error).__name__)
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "database_unavailable",
                    "message": "Service temporarily unavailable",
                }
            },
        )

    @application.exception_handler(Exception)
    async def unexpected_error(_request: Request, error: Exception) -> JSONResponse:
        logger.error("unexpected application error: %s", type(error).__name__)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Internal server error"}},
        )

    application.include_router(router)
    return application


app = create_app()
