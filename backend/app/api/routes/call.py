"""Call session lifecycle: start and end."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.call import CallSession
from app.models.user import User
from app.schemas.call import CallStartResponse, CallSummary
from app.services.demo_scripts import list_script_ids

router = APIRouter(prefix="/api/call", tags=["call"])


@router.post("/start", response_model=CallStartResponse, status_code=status.HTTP_201_CREATED)
def start_call(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new call session for the current user."""
    session = CallSession(user_id=current_user.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return CallStartResponse(session_id=session.id, demo_scripts=list_script_ids())


@router.post("/{session_id}/end", response_model=CallSummary)
def end_call(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Finalise a call session and return its summary."""
    session = db.get(CallSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.ended_at is None:
        session.ended_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(session)
    return CallSummary(
        session_id=session.id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        transcript=session.transcript,
        max_confidence=session.max_confidence,
        outcome=session.outcome,
        stage_reached=session.stage_reached,
        interrupted=session.interrupted,
    )
