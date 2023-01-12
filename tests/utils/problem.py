import secrets
import random
from dataclasses import dataclass, asdict, field
from typing import (
    Optional,
    Union,
    List,
    Dict,
    Any,
    Tuple,
    Iterable,
)
from mongo import *
from mongo.utils import drop_none
from . import course as course_lib

__all__ = (
    'create_problem',
    'cmp_copied_problem',
    'create_test_case_info',
)


@dataclass
class Task:
    task_score: int
    case_count: int
    memory_limit: int
    time_limit: int


@dataclass
class TestCaseInfo:
    language: int
    fill_in_template: str
    tasks: List[Task] = field(default_factory=list)


def generate_task(
    task_score: int,
    case_count_range: Tuple[int, int],
    memory_limit_range: Tuple[int, int],
    time_limit_range: Tuple[int, int],
):
    return Task(
        task_score=task_score,
        case_count=random.randint(*case_count_range),
        memory_limit=random.randint(*memory_limit_range),
        time_limit=random.randint(*time_limit_range),
    )


def conv_key(k: str):
    '''
    convert a `snake_case` string to `camelCase`
    '''
    s, *e = k.split('_')
    return ''.join((s, *(x.capitalize() for x in e)))


def conv_dict(kv_pairs: Iterable[Tuple[str, Any]]):
    return {conv_key(k): v for k, v in kv_pairs}


def create_test_case_info(
        *,
        language: int,
        task_len: int,
        case_count_range: Tuple[int, int] = (1, 10),
        memory_limit_range: Tuple[int, int] = (65536, 16777216),
        time_limit_range: Tuple[int, int] = (1, 4),
) -> Dict[str, Any]:
    per_task_score = 100 // task_len
    tasks = [
        generate_task(
            per_task_score,
            case_count_range,
            memory_limit_range,
            time_limit_range,
        ) for _ in range(task_len)
    ]
    remainder = 100 - per_task_score * task_len
    tasks[-1].task_score += remainder
    return asdict(
        TestCaseInfo(
            language=language,
            fill_in_template='',
            tasks=tasks,
        ),
        dict_factory=conv_dict,
    )


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
