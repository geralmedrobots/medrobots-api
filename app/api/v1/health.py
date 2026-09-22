from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.error import ErrorResponse

router = APIRouter(tags=["Health"])


class LivenessResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["ok"]


@router.get(
    "/health",
    response_model=LivenessResponse,
    summary="Liveness probe",
    description=(
        "Reports that the process is running and able to handle requests. "
        "Performs no database or external I/O so it stays fast and cheap to poll."
    ),
)
def liveness() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    description=(
        "Reports whether the API can currently serve requests, including database "
        "connectivity. Returns 503 when a required dependency is unavailable."
    ),
    responses={503: {"description": "Database unavailable", "model": ErrorResponse}},
)
def readiness(session: Annotated[Session, Depends(get_db)]) -> ReadinessResponse:
    session.execute(text("SELECT 1"))
    return ReadinessResponse(status="ok", database="ok")
