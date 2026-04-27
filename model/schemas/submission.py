from typing import Any, List, Optional
from .base import BaseSchema


class CreateSubmissionBody(BaseSchema):
    language_type: Optional[int] = None
    problem_id: Optional[int] = None


class GetSubmissionListQuery(BaseSchema):
    offset: Optional[str] = None
    count: Optional[str] = None
    problem_id: Optional[str] = None
    username: Optional[str] = None
    status: Optional[str] = None
    language_type: Optional[str] = None
    course: Optional[str] = None
    before: Optional[str] = None
    after: Optional[str] = None
    ip_addr: Optional[str] = None


class GradeSubmissionBody(BaseSchema):
    score: int


class UpdateConfigBody(BaseSchema):
    rate_limit: int
    sandbox_instances: List[Any]
