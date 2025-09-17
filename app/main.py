from __future__ import annotations
from datetime import datetime, timezone
from typing import Generator

import os
import logging
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, FileResponse
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from authlib.integrations.starlette_client import OAuth
from pydantic import BaseModel
from dotenv import load_dotenv

from .database import Base, engine, SessionLocal
from .models import Student, StudentHistory, User, Submission
from .schemas import (
    StudentCreate,
    StudentCreatedOut,
    StudentOut,
    StudentUpdate,
    SubmissionIn,
    SubmissionOut,
    SubmissionWithUserOut,
)
from .utils import generate_student_id, generate_edit_token

# ---- Helpers ----
def iso_utc(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()

load_dotenv()

app = FastAPI(title="Students API", version="1.0.0")

# --- Session & security config (SessionMiddleware added later) ---
SESSION_SECRET = os.getenv("SESSION_SECRET") or os.getenv("SECRET_KEY") or "dev-secret-change-me"
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
SESSION_SAMESITE = os.getenv("SESSION_SAME_SITE", "lax")  # lax|strict|none

# --- Static Files: serve student page ---
# Serve the local docs/ directory at /student for the student-facing UI
try:
    app.mount("/student", StaticFiles(directory="docs", html=True), name="student")
except Exception:
    # In some environments the directory may not exist; ignore mounting failure
    pass

# --- Middleware: Guard /student paths behind login ---
class StudentGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Authentication disabled: always allow access
        return await call_next(request)

# Add guard first, then add SessionMiddleware so Session runs first (outermost)
app.add_middleware(StudentGuardMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    https_only=SESSION_COOKIE_SECURE,
    same_site=SESSION_SAMESITE,
)

# Optional: CORS for allowed origins (comma-separated)
ALLOW_ORIGINS = [o.strip() for o in os.getenv("ALLOW_ORIGINS", "").split(",") if o.strip()]
if ALLOW_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["POST", "GET", "OPTIONS"],
        allow_headers=["*"],
    )

# Security headers
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    # Minimal CSP; adjust as needed
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; img-src 'self' https: data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'")
    return response

# --- OAuth (Google) Configuration ---
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
OAUTH_REDIRECT_BASE_URL = os.getenv("OAUTH_REDIRECT_BASE_URL")  # e.g., http://127.0.0.1:8000 or https://your-domain.com
STUDENT_URL = os.getenv("STUDENT_URL", "/student/")  # Destination after login

oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


class UserInfo(BaseModel):
    sub: str
    email: str | None = None
    name: str | None = None
    picture: str | None = None


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


def get_current_user(request: Request) -> UserInfo | None:
    """Authentication disabled: always return None (anonymous)."""
    return None


def require_login(request: Request) -> UserInfo:
    # Authentication disabled
    return UserInfo(sub="anonymous")


 


@app.get("/")
def root():
    # Redirect to interactive API docs for convenience
    return RedirectResponse(url="/docs")

# Simple route to access admin viewer
@app.get("/admin", include_in_schema=False)
def admin_page():
    return FileResponse("docs/admin.html")


@app.get("/admin/submissions/{subm_id}", response_model=SubmissionWithUserOut)
def admin_get_submission(subm_id: str, request: Request, db: Session = Depends(get_db)):
    subm = db.get(Submission, subm_id)
    if not subm:
        raise HTTPException(status_code=404, detail="not found")
    usr = db.get(User, subm.google_sub)
    provided_name = None
    try:
        if isinstance(subm.payload, dict):
            ident = (subm.payload.get("identity") or {})
            provided_name = (ident.get("name") or "").strip() or None
    except Exception:
        provided_name = None
    return SubmissionWithUserOut(
        id=subm.id,
        created_at=iso_utc(subm.created_at),
        payload=subm.payload,
        user_sub=(usr.google_sub if usr else subm.google_sub),
        user_email=(usr.email if usr else None),
        user_name=((usr.name if usr else None) or provided_name),
    )


@app.get("/admin/submissions/{subm_id}/view", include_in_schema=False)
def admin_view_submission(subm_id: str):
    return FileResponse("docs/submission.html")


# --- Auth Routes ---
@app.get("/auth/login")
async def auth_login(request: Request):
    # Prefer a fixed base URL when provided to avoid redirect_uri mismatches
    if OAUTH_REDIRECT_BASE_URL:
        base = OAUTH_REDIRECT_BASE_URL.rstrip("/")
        redirect_uri = f"{base}/auth/callback"
    else:
        redirect_uri = request.url_for("auth_callback")
    logging.getLogger(__name__).info("OAuth redirect_uri=%s", redirect_uri)
    # Persist `next` so we can send the user back after OAuth completes
    next_param = request.query_params.get("next")
    if next_param:
        try:
            request.session["next_after_login"] = str(next_param)
        except Exception:
            pass
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/callback")
async def auth_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth error: {e}")
    userinfo = token.get("userinfo")
    if not userinfo:
        # Some providers put userinfo at a different key; fallback to userinfo endpoint
        resp = await oauth.google.parse_id_token(request, token)
        userinfo = resp or {}

    # Persist minimal user info in session
    request.session["user"] = {
        "sub": userinfo.get("sub") or userinfo.get("id"),
        "email": userinfo.get("email"),
        "name": userinfo.get("name"),
        "picture": userinfo.get("picture"),
    }

    # Upsert user in DB
    db = SessionLocal()
    try:
        sub = request.session["user"]["sub"]
        obj = db.get(User, sub)
        now = datetime.utcnow()
        if obj is None:
            obj = User(
                google_sub=sub,
                email=request.session["user"].get("email"),
                name=request.session["user"].get("name"),
                picture=request.session["user"].get("picture"),
                created_at=now,
                last_login_at=now,
            )
            db.add(obj)
        else:
            obj.email = request.session["user"].get("email")
            obj.name = request.session["user"].get("name")
            obj.picture = request.session["user"].get("picture")
            obj.last_login_at = now
            db.add(obj)
        db.commit()
    finally:
        db.close()

    # Redirect to student page or a provided next param
    next_from_session = request.session.pop("next_after_login", None)
    next_url = next_from_session or request.query_params.get("next") or STUDENT_URL
    logging.getLogger(__name__).info("[callback] login ok -> redirect %s", next_url)
    return RedirectResponse(url=next_url)


@app.get("/auth/logout")
async def auth_logout(request: Request):
    request.session.pop("user", None)
    return {"ok": True}


@app.get("/me")
async def me(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="not logged in")
    return user


@app.post("/students", response_model=StudentCreatedOut)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)):
    # Create random ID + edit token; do not store PII unless provided explicitly
    now = datetime.utcnow()
    student_id = generate_student_id()
    edit_token = generate_edit_token()

    student = Student(
        id=student_id,
        name=payload.name,
        edit_token=edit_token,
        version=1,
        updated_at=now,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return StudentCreatedOut(
        id=student.id,
        name=student.name,
        version=student.version,
        updated_at=student.updated_at.isoformat(),
        edit_token=edit_token,
    )


@app.get("/students/{student_id}", response_model=StudentOut)
def get_student(student_id: str, db: Session = Depends(get_db)):
    obj = db.get(Student, student_id)
    if not obj:
        raise HTTPException(status_code=404, detail="student not found")
    return StudentOut(
        id=obj.id,
        name=obj.name,
        version=obj.version,
        updated_at=obj.updated_at.isoformat() if obj.updated_at else None,
    )


# --- Submission endpoints (require login) ---
@app.post("/submissions", response_model=SubmissionOut)
def create_submission(payload: SubmissionIn, request: Request, db: Session = Depends(get_db)):
    # Anonymous submissions allowed
    sid = generate_student_id()
    subm = Submission(id=sid, google_sub=None, payload=payload.payload)
    db.add(subm)
    db.commit()
    db.refresh(subm)
    return SubmissionOut(id=subm.id, created_at=iso_utc(subm.created_at), payload=subm.payload)


@app.get("/submissions", response_model=list[SubmissionOut])
def list_submissions(request: Request, db: Session = Depends(get_db)):
    # Public: show recent submissions (latest 50)
    rows = (
        db.query(Submission)
        .order_by(Submission.created_at.desc())
        .limit(50)
        .all()
    )
    return [SubmissionOut(id=r.id, created_at=iso_utc(r.created_at), payload=r.payload) for r in rows]


# Admin: list all submissions with minimal user info
@app.get("/admin/submissions", response_model=list[SubmissionWithUserOut])
def admin_list_submissions(request: Request, db: Session = Depends(get_db)):
    # Public admin list (no login)
    q = (
        db.query(Submission, User)
        .join(User, Submission.google_sub == User.google_sub, isouter=True)
        .order_by(Submission.created_at.desc())
    )
    out: list[SubmissionWithUserOut] = []
    for subm, usr in q.all():
        provided_name = None
        try:
            if isinstance(subm.payload, dict):
                ident = (subm.payload.get("identity") or {})
                provided_name = (ident.get("name") or "").strip() or None
        except Exception:
            provided_name = None
        out.append(
            SubmissionWithUserOut(
                id=subm.id,
                created_at=iso_utc(subm.created_at),
                payload=subm.payload,
                user_sub=(usr.google_sub if usr else subm.google_sub),
                user_email=(usr.email if usr else None),
                user_name=(usr.name or provided_name if usr else provided_name),
            )
        )
    return out


@app.put("/students/{student_id}", response_model=StudentOut)
def update_student(student_id: str, payload: StudentUpdate, db: Session = Depends(get_db)):
    obj = db.get(Student, student_id)
    if not obj:
        raise HTTPException(status_code=404, detail="student not found")

    # Check edit_token
    if obj.edit_token != payload.edit_token:
        raise HTTPException(status_code=403, detail="invalid edit token")

    # Save history before update
    snapshot = {
        "id": obj.id,
        "dob": obj.dob,
        "phone": obj.phone,
        "name": obj.name,
        "version": obj.version,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }
    hist = StudentHistory(student_id=obj.id, version=obj.version, snapshot=snapshot)
    db.add(hist)

    # Apply updates
    if payload.name is not None:
        obj.name = payload.name
    obj.version = (obj.version or 1) + 1
    obj.updated_at = datetime.utcnow()
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return StudentOut(
        id=obj.id,
        name=obj.name,
        version=obj.version,
        updated_at=obj.updated_at.isoformat() if obj.updated_at else None,
    )
