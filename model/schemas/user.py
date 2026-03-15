from typing import Optional
from .base import BaseSchema


class AddUserBody(BaseSchema):
    username: str
    password: str
    email: str


class UpdateUserBody(BaseSchema):
    password: Optional[str] = None
    displayed_name: Optional[str] = None
    role: Optional[int] = None


class GetUserListQuery(BaseSchema):
    offset: Optional[str] = None
    count: Optional[str] = None
    course: Optional[str] = None
    role: Optional[str] = None
