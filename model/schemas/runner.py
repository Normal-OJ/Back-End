from typing import Any, List, Optional
from .base import BaseSchema


class RegisterRunnerBody(BaseSchema):
    registration_token: str
    name: Optional[str] = None


class CompleteJobBody(BaseSchema):
    tasks: List[Any]
