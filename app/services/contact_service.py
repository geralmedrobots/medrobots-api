from sqlalchemy.orm import Session

from app.db.models.contact import Contact
from app.repositories.contact_repository import create_contact
from app.schemas.contact import ContactCreate


def submit_contact(session: Session, data: ContactCreate) -> Contact:
    return create_contact(session, data)
