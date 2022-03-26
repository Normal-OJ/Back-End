import secrets
from typing import Optional, Union, List, Dict, Any
from mongo import *
from . import course as course_lib

__all__ = ('create_problem',)


def create_problem(
    *,
    course: Optional[Union[str, Course]] = None,
    owner: Optional[Union[str, User]] = None,
    name: Optional[str] = None,
    status: Optional[int] = None,
    description: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
    type: Optional[int] = None,
    allowed_language: Optional[int] = None,
    quota: Optional[int] = None,
    default_code: Optional[str] = None,
) -> Problem:
    if not isinstance(course, Course):
        course = course_lib.create_course(name=course)
    if owner is None:
        owner = course.teacher
    if name is None:
        name = secrets.token_hex(8)
    if description is None:
        description = {
            'description': '',
            'input': '',
            'output': '',
            'hint': '',
            'sample_input': [],
            'sample_output': [],
        }
    params = {
        'user': owner,
        'courses': [course],
        'problem_name': name,
        'status': status,
        'description': description,
        'tags': tags,
        'type': type,
        'allowed_language': allowed_language,
        'quota': quota,
        'default_code': default_code,
    }
    pid = Problem.add(**params)
    return Problem(pid)
