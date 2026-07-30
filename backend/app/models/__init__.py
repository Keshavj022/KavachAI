"""SQLAlchemy models package.

Importing this module registers every model on ``Base.metadata`` so
``Base.metadata.create_all`` sees the full schema.
"""

from app.models.alert import Alert
from app.models.call import CallSession
from app.models.decoy import DecoyPackage
from app.models.evidence import Evidence
from app.models.identifier import Identifier, IdentifierLink, report_identifiers
from app.models.report import Report
from app.models.user import TrustedContact, User

__all__ = [
    "Alert",
    "CallSession",
    "DecoyPackage",
    "Evidence",
    "Identifier",
    "IdentifierLink",
    "report_identifiers",
    "Report",
    "TrustedContact",
    "User",
]
