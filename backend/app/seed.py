"""Seed the database with demo users and a synthetic fraud-intelligence graph.

Run with: ``python -m app.seed`` (from the ``backend`` directory).

The seed is idempotent: re-running clears the synthetic fraud data and demo
users and rebuilds them, so the demo always starts from a known-good state.
The fraud graph is synthetic but realistic — several rings of phones / UPI IDs
/ accounts / devices linked by co-report edges, so the authority graph view
and ring clustering have something meaningful to show, and so demo step 7
(instant known-scammer verdict) works out of the box.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database import SessionLocal, init_db
from app.models import (
    Alert,
    CallSession,
    Evidence,
    Identifier,
    IdentifierLink,
    Report,
    TrustedContact,
    User,
    report_identifiers,
)
from app.models.enums import (
    Channel,
    IdentifierType,
    ReportStatus,
    Role,
    ScamCategory,
)

# A number the demo relies on: after a citizen reports it, the second citizen
# who checks it must get an instant known-scammer verdict.
DEMO_SCAM_NUMBER = "+919812345678"
DEMO_SCAM_UPI = "cbi.refund@okhdfc"

# Indian city coordinates for the hotspot map.
_CITIES = [
    ("Delhi", 28.6139, 77.2090),
    ("Mumbai", 19.0760, 72.8777),
    ("Bengaluru", 12.9716, 77.5946),
    ("Hyderabad", 17.3850, 78.4867),
    ("Jaipur", 26.9124, 75.7873),
    ("Kolkata", 22.5726, 88.3639),
    ("Pune", 18.5204, 73.8567),
    ("Ahmedabad", 23.0225, 72.5714),
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _wipe(db: Session) -> None:
    """Remove existing demo/synthetic rows so the seed is repeatable.

    The ``report_identifiers`` association table is cleared explicitly: bulk
    ``delete()`` statements bypass ORM cascade, so without this its rows would
    be orphaned and collide on re-seed.
    """
    db.execute(delete(report_identifiers))
    db.execute(delete(Evidence))
    db.execute(delete(Alert))
    db.execute(delete(Report))
    db.execute(delete(CallSession))
    db.execute(delete(IdentifierLink))
    db.execute(delete(Identifier))
    db.execute(delete(TrustedContact))
    db.execute(delete(User))
    db.commit()


def _create_users(db: Session) -> dict[str, User]:
    """Create the demo users for both roles."""
    users = {
        "citizen": User(
            email="citizen@kavach.demo",
            hashed_password=hash_password("password123"),
            full_name="Anita Sharma",
            role=Role.citizen.value,
            preferred_language="en",
        ),
        "citizen2": User(
            email="citizen2@kavach.demo",
            hashed_password=hash_password("password123"),
            full_name="Rakesh Gupta",
            role=Role.citizen.value,
            preferred_language="en",
        ),
        "authority": User(
            email="authority@kavach.demo",
            hashed_password=hash_password("password123"),
            full_name="Inspector Verma",
            role=Role.authority.value,
            preferred_language="en",
        ),
    }
    db.add_all(users.values())
    db.commit()
    for u in users.values():
        db.refresh(u)

    # Give the first citizen a trusted contact for the alert demo.
    db.add(
        TrustedContact(
            user_id=users["citizen"].id, name="Son (Vikram)", phone="+919900112233"
        )
    )
    db.commit()
    return users


def _mk_identifier(
    db: Session,
    id_type: IdentifierType,
    value: str,
    risk: float,
    report_count: int,
    seen_days_ago: int,
) -> Identifier:
    ident = Identifier(
        type=id_type.value,
        value=value,
        risk_score=risk,
        report_count=report_count,
        first_seen=_utcnow() - timedelta(days=seen_days_ago),
    )
    db.add(ident)
    return ident


def _create_fraud_graph(db: Session, users: dict[str, User]) -> None:
    """Seed several fraud rings of linked identifiers plus supporting reports."""
    random.seed(42)

    # --- Ring 1: the "CBI / digital arrest" ring (the demo ring) ---
    ring1 = [
        _mk_identifier(db, IdentifierType.phone, DEMO_SCAM_NUMBER, 0.96, 14, 20),
        _mk_identifier(db, IdentifierType.phone, "+919845000111", 0.88, 9, 18),
        _mk_identifier(db, IdentifierType.upi, DEMO_SCAM_UPI, 0.94, 12, 19),
        _mk_identifier(db, IdentifierType.account, "50100234567890", 0.90, 8, 17),
        _mk_identifier(db, IdentifierType.device, "IMEI:355012345678901", 0.85, 6, 21),
    ]

    # --- Ring 2: the "KYC update" ring ---
    ring2 = [
        _mk_identifier(db, IdentifierType.phone, "+919765432100", 0.82, 7, 12),
        _mk_identifier(db, IdentifierType.phone, "+919765432155", 0.79, 5, 11),
        _mk_identifier(db, IdentifierType.upi, "kyc.verify@okaxis", 0.83, 6, 13),
        _mk_identifier(db, IdentifierType.url, "http://sbi-kyc-update.in/verify", 0.87, 8, 10),
    ]

    # --- Ring 3: the "investment / task" ring ---
    ring3 = [
        _mk_identifier(db, IdentifierType.phone, "+919555000222", 0.74, 4, 8),
        _mk_identifier(db, IdentifierType.upi, "profit.trade@ybl", 0.77, 5, 9),
        _mk_identifier(db, IdentifierType.account, "60200987654321", 0.72, 3, 7),
        _mk_identifier(db, IdentifierType.url, "http://quick-earn-tasks.co/join", 0.80, 6, 6),
    ]

    # A few lower-risk, unconnected identifiers for graph realism.
    strays = [
        _mk_identifier(db, IdentifierType.phone, "+919333444555", 0.35, 1, 4),
        _mk_identifier(db, IdentifierType.phone, "+919111222333", 0.22, 1, 2),
    ]

    db.commit()
    for ident in ring1 + ring2 + ring3 + strays:
        db.refresh(ident)

    def _link_ring(members: list[Identifier], weight: float, reason: str) -> None:
        """Fully connect a ring so it clusters cleanly in the graph view."""
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                db.add(
                    IdentifierLink(
                        source_id=members[i].id,
                        target_id=members[j].id,
                        weight=weight,
                        reason=reason,
                    )
                )

    _link_ring(ring1, 0.9, "co-reported")
    _link_ring(ring2, 0.8, "co-reported")
    _link_ring(ring3, 0.7, "shared device")
    # A weak cross-ring link (rings 1 and 2 shared one mule account) to make
    # the graph more interesting than fully disjoint clusters.
    db.add(
        IdentifierLink(
            source_id=ring1[3].id, target_id=ring2[2].id, weight=0.4, reason="shared account"
        )
    )
    db.commit()

    # --- Seed historical reports so the authority dashboard/map is populated.
    _seed_reports(db, users, ring1, ring2, ring3)


def _seed_reports(
    db: Session,
    users: dict[str, User],
    ring1: list[Identifier],
    ring2: list[Identifier],
    ring3: list[Identifier],
) -> None:
    """Create historical reports spread over cities and categories."""
    citizen = users["citizen"]
    samples = [
        (ScamCategory.digital_arrest, Channel.call, ring1,
         "Caller claimed to be CBI, said a parcel in my name had drugs, demanded I stay on video call."),
        (ScamCategory.kyc_update, Channel.sms, ring2,
         "SMS said my bank KYC expired and to verify at a link or account would be blocked."),
        (ScamCategory.investment, Channel.whatsapp, ring3,
         "WhatsApp group offered guaranteed returns for completing paid tasks."),
        (ScamCategory.digital_arrest, Channel.call, ring1,
         "Fake police video call, accused me of money laundering, told me to transfer to a safe account."),
        (ScamCategory.kyc_update, Channel.sms, ring2,
         "Received a KYC update link impersonating my bank."),
    ]

    for idx, (category, channel, ring, content) in enumerate(samples):
        city, lat, lng = _CITIES[idx % len(_CITIES)]
        report = Report(
            user_id=citizen.id,
            channel=channel.value,
            scam_category=category.value,
            content=content,
            status=ReportStatus.filed.value if idx % 2 else ReportStatus.under_review.value,
            created_at=_utcnow() - timedelta(days=idx * 2 + 1),
            location_lat=lat + random.uniform(-0.05, 0.05),
            location_lng=lng + random.uniform(-0.05, 0.05),
            location_label=city,
        )
        # Link the phone + one more identifier from the ring to the report.
        report.identifiers = [ring[0], ring[min(2, len(ring) - 1)]]
        db.add(report)

    db.commit()


def seed() -> None:
    """Entry point: (re)build tables and seed demo data."""
    init_db()
    db = SessionLocal()
    try:
        _wipe(db)
        users = _create_users(db)
        _create_fraud_graph(db, users)
        print("Seed complete.")
        print("  Citizen  : citizen@kavach.demo  / password123")
        print("  Citizen2 : citizen2@kavach.demo / password123")
        print("  Authority: authority@kavach.demo / password123")
        print(f"  Demo scam number seeded: {DEMO_SCAM_NUMBER}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
