from typing import Any, Dict, Optional
from .base import BaseSchema


class GetReportQuery(BaseSchema):
    course: Optional[str] = None
    problem_id: Optional[str] = None


class DetectBody(BaseSchema):
    course: Optional[str] = None
    problem_id: Optional[int] = None
    student_nicknames: Optional[Dict[str, Any]] = None
