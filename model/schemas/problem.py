from typing import Any, List, Optional
from .base import BaseSchema


class ViewProblemListQuery(BaseSchema):
    offset: Optional[str] = None
    count: Optional[str] = None
    problem_id: Optional[str] = None
    tags: Optional[str] = None
    name: Optional[str] = None
    course: Optional[str] = None


class ProblemBody(BaseSchema):
    type: Optional[Any] = None
    courses: Optional[List[str]] = None
    status: Optional[Any] = None
    description: Optional[Any] = None
    tags: Optional[Any] = None
    problem_name: Optional[str] = None
    quota: Optional[Any] = None
    test_case_info: Optional[Any] = None
    can_view_stdout: Optional[Any] = None
    allowed_language: Optional[Any] = None
    default_code: Optional[str] = None


class InitiateTestCaseUploadBody(BaseSchema):
    length: int
    part_size: int


class CompleteTestCaseUploadBody(BaseSchema):
    upload_id: Optional[str] = None
    parts: Optional[List[Any]] = None


class GetTestdataQuery(BaseSchema):
    token: Optional[str] = None


class CloneProblemBody(BaseSchema):
    problem_id: int
    target: Optional[str] = None
    status: Optional[Any] = None


class PublishProblemBody(BaseSchema):
    problem_id: Optional[Any] = None
