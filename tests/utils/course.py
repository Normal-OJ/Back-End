import secrets
from typing import Union, List, Optional
from mongo import *
from mongo import engine
from . import user as user_lib

__all__ = ('create_course')


def create_course(
    *,
    teacher: Optional[Union[User, str]] = None,
    name: Optional[str] = None,
    students: Optional[Union[List[Union[User, Union[str, None]]], int]] = None,
) -> Course:
    """create a new course

    Args:
        teacher (Optional[Union[User, str]], optional): It will create new user if provide None.
        name (Optional[str], optional): Defaults as random 8 bytes hex string.
        students (Optional[Union[List[Union[User, str]], int]], optional): if provide int, it will create the same amount of new users as course students, or provide list with User/str/None.

    Returns:
        Course: Course object of the new course
    """
    if name is None:
        name = secrets.token_hex(8)
    if (course := Course(name)):
        return course
    if not isinstance(teacher, User):
        teacher = user_lib.create_user(username=teacher)
    Course.add_course(name, teacher)
    course = Course(name)
    if students is not None:
        if isinstance(students, int):
            students = [user_lib.create_user() for _ in range(students)]
        for student in students:
            if isinstance(student, User):
                course.add_user(student)
            else:
                course.add_user(user_lib.create_user(username=student))
    return course
