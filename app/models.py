from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Student(Base):
    __tablename__ = "students"

    # Primary key is now a random UUID-based string (no PII)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # PII fields are optional (kept for compatibility, can be unused)
    dob: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)  # YYYYMMDD
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Secret token required to update this record
    edit_token: Mapped[str] = mapped_column(String(128), nullable=False)

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    history: Mapped[list[StudentHistory]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )


class StudentHistory(Base):
    __tablename__ = "student_history"

    history_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String(64), ForeignKey("students.id"), nullable=False, index=True)

    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    student: Mapped[Student] = relationship(back_populates="history")


class User(Base):
    __tablename__ = "users"

    # Google account unique subject (sub)
    google_sub: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    picture: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    last_login_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    google_sub: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("users.google_sub"), index=True, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
