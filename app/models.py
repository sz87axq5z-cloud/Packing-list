from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Student(Base):
    __tablename__ = "students"

    # Primary key is the management ID: YYYYMMDD + phoneDigits
    id: Mapped[str] = mapped_column(String(32), primary_key=True)

    dob: Mapped[str] = mapped_column(String(8), nullable=False)  # YYYYMMDD
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    history: Mapped[list[StudentHistory]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )


class StudentHistory(Base):
    __tablename__ = "student_history"

    history_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String(32), ForeignKey("students.id"), nullable=False, index=True)

    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    student: Mapped[Student] = relationship(back_populates="history")
