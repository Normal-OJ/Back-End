from typing import List, Optional
from .base import BaseSchema


class RegisterRunnerBody(BaseSchema):
    registration_token: str
    name: Optional[str] = None


class CaseResultBody(BaseSchema):
    exitCode: int
    status: str
    stdout: str
    stderr: str
    execTime: int
    memoryUsage: int


class CompleteJobBody(BaseSchema):
    tasks: List[List[CaseResultBody]]


class AbortJobBody(BaseSchema):
    reason: Optional[str] = None
