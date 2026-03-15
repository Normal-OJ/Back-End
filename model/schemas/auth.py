from typing import Any, Dict, Optional
from .base import BaseSchema


class LoginBody(BaseSchema):
    username: str
    password: str


class SignupBody(BaseSchema):
    username: str
    password: str
    email: str


class ChangePasswordBody(BaseSchema):
    old_password: str
    new_password: str


class CheckUsernameBody(BaseSchema):
    username: str


class CheckEmailBody(BaseSchema):
    email: str


class ResendEmailBody(BaseSchema):
    email: str


class ActivateUserBody(BaseSchema):
    profile: Dict[str, Any]
    agreement: bool


class PasswordRecoveryBody(BaseSchema):
    email: str


class AddUserBody(BaseSchema):
    username: str
    password: str
    email: str


class BatchSignupBody(BaseSchema):
    new_users: str
    course: Optional[str] = None
    force: Optional[bool] = None


class GetMeQuery(BaseSchema):
    fields: Optional[str] = None
