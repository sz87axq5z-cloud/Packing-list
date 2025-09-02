from pydantic import BaseModel, Field, constr
from typing import Optional, Any, Dict

DobStr = constr(pattern=r"^\d{8}$")
PhoneStr = constr(pattern=r"^\d{7,20}$")

class StudentCreate(BaseModel):
    dob: DobStr = Field(..., description="YYYYMMDD e.g., 20010403")
    phone: PhoneStr = Field(..., description="Digits only e.g., 09012345678")
    name: Optional[str] = Field(default=None, max_length=100)

class StudentOut(BaseModel):
    id: str
    dob: str
    phone: str
    name: Optional[str]
    version: int
    updated_at: str

class StudentHistoryOut(BaseModel):
    history_id: int
    student_id: str
    version: int
    snapshot: Dict[str, Any]
    changed_at: str
