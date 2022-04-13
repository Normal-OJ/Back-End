import secrets
from typing import Optional, Union, List, Dict, Any
from mongo import *
from mongo.utils import drop_none
from . import course as course_lib
from tests import utils

__all__ = ('create_problem', )


def create_problem(
    *,
    course: Optional[Union[str, Course]] = None,
    owner: Optional[Union[str, User]] = None,
    name: Optional[str] = None,
    status: int = 0,
    description: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
    type: Optional[int] = None,
    allowed_language: Optional[int] = None,
    quota: Optional[int] = None,
    default_code: Optional[str] = None,
    test_case_info: Optional[Dict[str, Any]] = None,
) -> Problem:
    if not isinstance(course, Course):
        course = course_lib.create_course(name=course)
    # Determine owner
    if owner is None:
        owner = course.teacher
    elif isinstance(owner, str):
        owner = User(owner)
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
    params = drop_none({
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
    })
    problem = Problem(Problem.add(**params))
    # FIXME: Prevent so many duplicated
    # Update problem testcase meta
    if test_case_info is not None:
        Problem.edit_problem(
            user=owner,
            problem_id=problem.id,
            courses=problem.courses,
            status=problem.problem_status,
            problem_name=problem.problem_name,
            description=problem.description,
            tags=problem.tags,
            type=problem.problem_type,
            test_case_info=test_case_info,
            allowed_language=problem.allowed_language,
            can_view_stdout=problem.can_view_stdout,
            quota=problem.quota,
            default_code=problem.default_code,
        )
        problem.reload('test_case')
    return problem


def cmp_copied_problem(original: Problem, copy: Problem):
    # It shouold be a new problem
    assert original.problem_id != copy.problem_id
    # But some fields are identical
    fields = (
        'problem_name',
        'problem_type',
        'description',
        'tags',
        'can_view_stdout',
        'allowed_language',
        'quota',
    )
    for field in fields:
        old = getattr(original, field)
        new = getattr(copy, field)
        assert old == new, (field, old, new)
    # And some fields shuold be default
    assert len(copy.homeworks) == 0
    assert len(copy.high_scores) == 0


def cmp_copied_problem(original: Problem, copy: Problem):
    # It shouold be a new problem
    assert original.problem_id != copy.problem_id
    # But some fields are identical
    fields = (
        'problem_name',
        'problem_type',
        'description',
        'tags',
        'can_view_stdout',
        'allowed_language',
        'quota',
    )
    for field in fields:
        old = getattr(original, field)
        new = getattr(copy, field)
        assert old == new, (field, old, new)
    # And some fields shuold be default
    assert len(copy.homeworks) == 0
    assert len(copy.high_scores) == 0
