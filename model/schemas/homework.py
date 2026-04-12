from typing import Any, List, Optional
from .base import BaseSchema


class CreateHomeworkBody(BaseSchema):
    name: Optional[str] = None
    course_name: Optional[str] = None
    markdown: Optional[str] = None
    start: Optional[Any] = None
    end: Optional[Any] = None
    problem_ids: Optional[List[Any]] = None
    scoreboard_status: Optional[Any] = None
    penalty: Optional[Any] = None


class UpdateHomeworkBody(BaseSchema):
    name: Optional[str] = None
    markdown: Optional[str] = None
    start: Optional[Any] = None
    end: Optional[Any] = None
    problem_ids: Optional[List[Any]] = None
    scoreboard_status: Optional[Any] = None
    penalty: Optional[Any] = None


class PatchIpFiltersBody(BaseSchema):
    patches: List[Any]
