from sqlalchemy.orm import Session

from app.db.models.contact import Contact
from app.schemas.contact import ContactCreate


def create_contact(session: Session, data: ContactCreate) -> Contact:
    contact = Contact(**data.model_dump())
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact
