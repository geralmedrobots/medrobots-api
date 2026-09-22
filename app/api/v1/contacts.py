from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter
from app.db.session import get_db
from app.schemas.contact import ContactCreate, ContactCreated
from app.schemas.error import ErrorResponse
from app.services.contact_service import submit_contact

router = APIRouter(tags=["Contacts"])


@router.post(
    "/contacts",
    response_model=ContactCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a contact request",
    description="Validates and stores a contact request for later handling by Med Robots.",
    responses={
        413: {"description": "Request body too large", "model": ErrorResponse},
        422: {"description": "Invalid request data", "model": ErrorResponse},
        429: {"description": "Too many requests", "model": ErrorResponse},
        500: {"description": "Unexpected server error", "model": ErrorResponse},
        503: {"description": "Database unavailable", "model": ErrorResponse},
    },
)
@limiter.limit("5/minute")
def submit(
    request: Request, data: ContactCreate, session: Annotated[Session, Depends(get_db)]
) -> ContactCreated:
    return ContactCreated.model_validate(submit_contact(session, data))
