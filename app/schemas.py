from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List


class StudentCreate(BaseModel):
    # No PII required. Only optional display name.
    name: Optional[str] = Field(default=None, max_length=100)


class StudentCreatedOut(BaseModel):
    # Returned only at creation time, includes edit_token
    id: str
    name: Optional[str]
    version: int
    updated_at: str
    edit_token: str


class StudentOut(BaseModel):
    # Returned for general fetches (no edit_token)
    id: str
    name: Optional[str]
    version: int
    updated_at: str


class StudentUpdate(BaseModel):
    # For updates, require edit_token, and allow updating safe fields
    edit_token: str
    name: Optional[str] = Field(default=None, max_length=100)


class StudentHistoryOut(BaseModel):
    history_id: int
    student_id: str
    version: int
    snapshot: Dict[str, Any]
    changed_at: str


class SubmissionIn(BaseModel):
    # Accept arbitrary JSON payload from the student UI
    payload: Dict[str, Any]


class SubmissionOut(BaseModel):
    id: str
    created_at: str
    payload: Dict[str, Any]


class SubmissionWithUserOut(BaseModel):
    id: str
    created_at: str
    payload: Dict[str, Any]
    user_sub: Optional[str] = None
    user_email: Optional[str] = None
    user_name: Optional[str] = None
