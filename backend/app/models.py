from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    cycles = relationship("Cycle", back_populates="user", cascade="all, delete-orphan")
    push_subscriptions = relationship(
        "PushSubscription", back_populates="user", cascade="all, delete-orphan"
    )


class Cycle(Base):
    __tablename__ = "cycles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    cycle_length = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    user = relationship("User", back_populates="cycles")


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "endpoint", name="uix_user_endpoint"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    endpoint = Column(String, nullable=False)
    p256dh_key = Column(String, nullable=False)
    auth_key = Column(String, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    user = relationship("User", back_populates="push_subscriptions")


class NotificationLog(Base):
    __tablename__ = "notification_logs"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "notification_type",
            "cycle_reference_date",
            name="uix_user_type_ref_date",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # "period_1_day", "period_3_days", "fertile_1_day"
    notification_type = Column(String, nullable=False)
    cycle_reference_date = Column(Date, nullable=False)
    sent_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    user = relationship("User")
