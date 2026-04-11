from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=True)  # nullable for Google-only accounts
    email = Column(String, nullable=True, index=True)
    google_sub = Column(String, unique=True, nullable=True)
    stripe_customer_id = Column(String, nullable=True)
    subscription_id = Column(String, nullable=True)
    subscription_status = Column(String, nullable=True)
    subscription_plan = Column(String, nullable=True)
    credit_balance = Column(Integer, default=0, nullable=False)
    active_plan = Column(String, default="free", nullable=False)
    plan_status = Column(String, default="inactive", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_testing = Column(Boolean, default=False, nullable=False)

    collections = relationship("FileCollection", back_populates="owner", cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="user", cascade="all, delete-orphan")
    payment_records = relationship("PaymentRecord", back_populates="user", cascade="all, delete-orphan")


class FileCollection(Base):
    __tablename__ = "file_collections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    format_template = Column(String, default="ARTIST_TITLE_PRODUCERS_MIX_VERSION", nullable=False)
    delimiter = Column(String, default="underscore", nullable=False)
    case_style = Column(String, default="keep", nullable=False)
    safe_cleanup = Column(Boolean, default=True, nullable=False)
    total_size_bytes = Column(BigInteger, default=0, nullable=False)
    status = Column(String, default="uploaded", nullable=False)
    download_count = Column(Integer, default=0, nullable=False)
    preview_generated_at = Column(DateTime, nullable=True)
    downloaded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="collections")
    files = relationship("File", back_populates="collection", cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="collection")


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("file_collections.id", ondelete="CASCADE"), nullable=False)
    external_id = Column(String, unique=True, nullable=False, index=True)
    original_path = Column(String, nullable=False)
    current_path = Column(String, nullable=False)
    file_size = Column(BigInteger)
    extension = Column(String)
    extracted_json = Column(Text, nullable=True)
    resolved_json = Column(Text, nullable=True)
    status = Column(String, default="pending", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    collection = relationship("FileCollection", back_populates="files")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    collection_id = Column(Integer, ForeignKey("file_collections.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String, nullable=False)
    summary = Column(String, nullable=False)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="activity_logs")
    collection = relationship("FileCollection", back_populates="activity_logs")


class PaymentRecord(Base):
    __tablename__ = "payment_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    stripe_checkout_session_id = Column(String, unique=True, nullable=True, index=True)
    stripe_invoice_id = Column(String, unique=True, nullable=True, index=True)
    stripe_customer_id = Column(String, nullable=True)
    stripe_price_id = Column(String, nullable=True)
    plan_key = Column(String, nullable=False)
    plan_type = Column(String, nullable=False, default="one_time")
    amount_cents = Column(Integer, nullable=False, default=0)
    currency = Column(String, nullable=False, default="usd")
    credits = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="pending")
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="payment_records")


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    severity = Column(String, default="info", nullable=False)  # info | success | warn | danger
    is_published = Column(Boolean, default=False, nullable=False, index=True)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    # Phase 2 targeting — present in schema, unused by Phase 1 UI
    target_funnel_stage = Column(String, nullable=True)
    target_plan_status = Column(String, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    user_agent = Column(String, nullable=True)
    ip_hash = Column(String, nullable=True)


class UIComment(Base):
    __tablename__ = "ui_comments"

    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    block_key = Column(String, nullable=False, index=True)
    page_path = Column(String, nullable=False, index=True)
    body = Column(Text, nullable=False)
    status = Column(String, default="open", nullable=False, index=True)  # open | resolved
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    author = relationship("User")
