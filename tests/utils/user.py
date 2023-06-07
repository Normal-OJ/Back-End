import secrets
from typing import Optional, Union
from mongo import *
from . import course as course_lib
from .utils import drop_none

__all__ = ('create_user', )


def create_user(
    *,
    username: Optional[str] = None,
    password: Optional[str] = None,
    email: Optional[str] = None,
    displayed_name: Optional[str] = None,
    role: Optional[User.engine.Role] = None,
    course: Optional[Union['Course', str]] = None,
) -> User:
    """signup a new user
    
    Args:
        username (Optional[str], optional): Defaults as random 8 bytes hex string.
        password (Optional[str], optional): Defaults as random 16 bytes URL-safe string.
        email (Optional[str], optional): Defaults as username + '@noj.tw'.
        displayed_name (Optional[str], optional): Defaults as the same as username.
        role (Optional[User.engine.Role], optional): Defaults as student (User.engine.Role.STUDENT).
        course (Optional[Union[&#39;Course&#39;, str]], optional): Defaults to None.

    Returns:
        User: User object of the new user
    """
    if username is None:
        username = secrets.token_hex(8)
    if (user := User(username)):
        return user
    if password is None:
        password = secrets.token_urlsafe(16)
    if email is None:
        email = f'{username}@noj.tw'
    u = {
        'username': username,
        'password': password,
        'email': email,
    }
    activate_payload = drop_none({'displayedName': displayed_name})
    new_user = User.signup(**u)
    new_user.activate(activate_payload)
    if role is not None:
        new_user.update(role=role)
        new_user.reload('role')
    if isinstance(course, str):
        course = course_lib.create_course(name=course)
    if course is not None:
        new_student_nicknames = {
            **course.student_nicknames,
            u['username']: u['username'],
        }
        course.update_student_namelist(new_student_nicknames)
        new_user.reload('courses')
    return new_user


def create_user_many(k: int, **kwargs):
    return [create_user(**kwargs) for _ in range(k)]