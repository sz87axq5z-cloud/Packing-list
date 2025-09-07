import secrets
import uuid


def generate_student_id() -> str:
    """Generate a random, non-guessable ID (UUID v4 hex)."""
    return uuid.uuid4().hex  # 32 hex chars


def generate_edit_token() -> str:
    """Generate a secret edit token to authorize updates."""
    return secrets.token_urlsafe(16)  # ~22 url-safe chars
