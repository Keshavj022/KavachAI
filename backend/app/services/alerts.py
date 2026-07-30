"""Trusted-contact alerts — Twilio SMS with a simulate-and-log fallback.

Breaking the scammer's isolation tactic is a first-class feature: when a scam
is confirmed we notify a family member so the victim is not alone. If Twilio
credentials are absent (the common case for a demo) the alert is logged and
recorded as ``simulated=True`` — the app never crashes and the UI is honest
about what actually happened.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.models.alert import Alert
from app.models.enums import AlertStatus
from app.models.user import TrustedContact, User

logger = logging.getLogger("kavach.alerts")

_MESSAGE_TEMPLATE = (
    "Kavach alert: {name} may be the target of a phone scam right now. "
    "Please call them and make sure they do not transfer any money or share "
    "any codes. This is an automated safety alert."
)


def _send_via_twilio(to_number: str, body: str) -> bool:
    """Attempt a real SMS. Returns True on success, False on any failure."""
    try:
        from twilio.rest import Client  # imported lazily; optional dependency

        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        client.messages.create(
            to=to_number, from_=settings.twilio_from_number, body=body
        )
        return True
    except Exception as exc:
        logger.warning("Twilio send failed (%s); recording as simulated.", exc)
        return False


def alert_trusted_contacts(db: Session, user: User) -> list[Alert]:
    """Notify all of a user's trusted contacts that they may be under attack.

    Always records an ``Alert`` row per contact. Uses Twilio if configured,
    otherwise logs a simulated alert.
    """
    contacts: list[TrustedContact] = list(user.trusted_contacts)
    if not contacts:
        logger.info("No trusted contacts for user %s; nothing to alert.", user.id)
        return []

    body = _MESSAGE_TEMPLATE.format(name=user.full_name)
    alerts: list[Alert] = []

    for contact in contacts:
        simulated = True
        status = AlertStatus.sent

        if settings.twilio_enabled:
            ok = _send_via_twilio(contact.phone, body)
            simulated = not ok
            status = AlertStatus.sent if ok else AlertStatus.failed
        else:
            # No credentials — log the message that *would* have been sent.
            logger.info(
                "[SIMULATED ALERT] to %s (%s): %s", contact.name, contact.phone, body
            )

        alert = Alert(
            user_id=user.id,
            trusted_contact_id=contact.id,
            channel="sms",
            status=status.value,
            simulated=simulated,
        )
        db.add(alert)
        alerts.append(alert)

    db.commit()
    for a in alerts:
        db.refresh(a)
    return alerts
