from datetime import datetime
from typing import Generator

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from .database import Base, engine, SessionLocal
from .models import Student, StudentHistory
from .schemas import StudentCreate, StudentOut
from .utils import build_student_id

app = FastAPI(title="Students API", version="1.0.0")


# Create tables on startup
@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/students", response_model=StudentOut)
def upsert_student(payload: StudentCreate, db: Session = Depends(get_db)):
    # Build management ID from dob + phone
    student_id = build_student_id(payload.dob, payload.phone)

    existing = db.get(Student, student_id)
    now = datetime.utcnow()

    if existing:
        # Save history snapshot before updating
        snapshot = {
            "id": existing.id,
            "dob": existing.dob,
            "phone": existing.phone,
            "name": existing.name,
            "version": existing.version,
            "updated_at": existing.updated_at.isoformat() if existing.updated_at else None,
        }
        hist = StudentHistory(
            student_id=existing.id,
            version=existing.version,
            snapshot=snapshot,
        )
        db.add(hist)

        # Update existing record
        existing.dob = payload.dob
        existing.phone = payload.phone
        existing.name = payload.name
        existing.version = (existing.version or 1) + 1
        existing.updated_at = now
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return StudentOut(
            id=existing.id,
            dob=existing.dob,
            phone=existing.phone,
            name=existing.name,
            version=existing.version,
            updated_at=existing.updated_at.isoformat(),
        )
    else:
        # Create new record
        student = Student(
            id=student_id,
            dob=payload.dob,
            phone=payload.phone,
            name=payload.name,
            version=1,
            updated_at=now,
        )
        db.add(student)
        db.commit()
        db.refresh(student)
        return StudentOut(
            id=student.id,
            dob=student.dob,
            phone=student.phone,
            name=student.name,
            version=student.version,
            updated_at=student.updated_at.isoformat(),
        )


@app.get("/students/{student_id}", response_model=StudentOut)
def get_student(student_id: str, db: Session = Depends(get_db)):
    obj = db.get(Student, student_id)
    if not obj:
        raise HTTPException(status_code=404, detail="student not found")
    return StudentOut(
        id=obj.id,
        dob=obj.dob,
        phone=obj.phone,
        name=obj.name,
        version=obj.version,
        updated_at=obj.updated_at.isoformat() if obj.updated_at else None,
    )
