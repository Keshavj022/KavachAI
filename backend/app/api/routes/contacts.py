"""Trusted-contact routes: list, add, delete (own contacts only)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import TrustedContact, User
from app.schemas.contact import ContactCreate, ContactOut

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


@router.get("", response_model=list[ContactOut])
def list_contacts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the current user's trusted contacts."""
    stmt = select(TrustedContact).where(TrustedContact.user_id == current_user.id)
    return list(db.scalars(stmt).all())


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def add_contact(
    payload: ContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a trusted contact for the current user."""
    contact = TrustedContact(
        user_id=current_user.id, name=payload.name, phone=payload.phone
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete one of the current user's trusted contacts."""
    contact = db.get(TrustedContact, contact_id)
    if contact is None or contact.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    db.delete(contact)
    db.commit()
