import uuid
from datetime import datetime, timedelta, timezone

from database import Base
from sqlalchemy import Column, DateTime, String


class UserSession(Base):
    __tablename__ = "user_sessions"

    session_id = Column(String, primary_key=True, index=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    last_active = Column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    runtime_data = Column(String, nullable=True)

    @classmethod
    def create_new(cls):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return cls(
            session_id=str(uuid.uuid4()),
            created_at=now,
            last_active=now,
        )

    def is_valid(self):
        # Session expires after 24 hours of inactivity
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return now - self.last_active < timedelta(hours=24)

    def update_activity(self):
        self.last_active = datetime.now(timezone.utc).replace(tzinfo=None)
