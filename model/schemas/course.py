from typing import Any, Dict, List, Optional
from .base import BaseSchema


class ModifyCoursesBody(BaseSchema):
    course: Optional[str] = None
    new_course: Optional[str] = None
    teacher: Optional[str] = None


class UpdateCourseBody(BaseSchema):
    TAs: Optional[List[str]] = None
    student_nicknames: Optional[Dict[str, Any]] = None


class AddGradeBody(BaseSchema):
    title: Optional[str] = None
    content: Optional[str] = None
    score: Optional[Any] = None


class UpdateGradeBody(BaseSchema):
    title: Optional[str] = None
    new_title: Optional[str] = None
    content: Optional[str] = None
    score: Optional[Any] = None


class DeleteGradeBody(BaseSchema):
    title: Optional[str] = None


class GetCourseScoreboardQuery(BaseSchema):
    pids: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
