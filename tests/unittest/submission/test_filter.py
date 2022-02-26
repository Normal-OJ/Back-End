import pytest
import secrets
import random
import time
from datetime import datetime, timedelta
from typing import (
    Dict,
    List,
    Optional,
)
from tests import utils
from mongo import (
    Submission,
    User,
    Problem,
)


def setup_function(_):
    utils.drop_db()


def teardown_function(_):
    utils.drop_db()


def add_problem(
    user: User,
    courses: List[str],
    description: Optional[Dict] = None,
    problem_name: Optional[str] = None,
    tags: List[str] = [],
    status: int = 1,
    test_case_info: Optional[Dict] = None,
    can_view_stdout: bool = False,
    allowed_language: int = 7,
    quota: int = -1,
    default_code: str = '',
):
    '''
    Add problem with default arguments
    '''
    if problem_name is None:
        problem_name = secrets.token_hex(16)
    if description is None:
        cnt = random.randrange(5)
        description = {
            'description': secrets.token_hex(),
            'input': secrets.token_hex(),
            'output': secrets.token_hex(),
            'hint': secrets.token_hex(),
            'sample_input': [secrets.token_hex() for _ in range(cnt)],
            'sample_output': [secrets.token_hex() for _ in range(cnt)],
        }
    return Problem.add(
        user=user,
        courses=courses,
        problem_name=problem_name,
        description=description,
        status=status,
        tags=tags,
        quota=quota,
        default_code=default_code,
        type=0,
        test_case_info=test_case_info,
        can_view_stdout=can_view_stdout,
        allowed_language=allowed_language,
    )


def test_param_before(client):
    problem_id = add_problem(
        user=User('first_admin'),
        courses=['Public'],
    )
    Submission.add(
        problem_id=problem_id,
        username='first_admin',
        lang=0,
    )
    assert len(
        Submission.filter(
            user=User('first_admin'),
            before=datetime.now(),
        )) == 1
    time.sleep(0.01)
    before = datetime.now()
    for _ in range(16):
        Submission.add(
            problem_id=problem_id,
            username='first_admin',
            lang=0,
        )
    assert len(Submission.filter(
        user=User('first_admin'),
        before=before,
    )) == 1


def test_param_after(client):
    expected_count = 16
    problem_id = add_problem(
        user=User('first_admin'),
        courses=['Public'],
    )
    for _ in range(expected_count):
        Submission.add(
            problem_id=problem_id,
            username='first_admin',
            lang=0,
        )
    time.sleep(0.01)
    after = datetime.now()
    for _ in range(expected_count):
        Submission.add(
            problem_id=problem_id,
            username='first_admin',
            lang=0,
        )
    assert len(Submission.filter(
        user=User('first_admin'),
        after=after,
    )) == expected_count


def test_query_period(client):
    after = datetime.now()
    expected_count = 16
    problem_id = add_problem(
        user=User('first_admin'),
        courses=['Public'],
    )
    for _ in range(expected_count):
        Submission.add(
            problem_id=problem_id,
            username='first_admin',
            lang=0,
        )
    assert len(
        Submission.filter(
            user='first_admin',
            after=after,
            before=datetime.now(),
        )) == expected_count


def test_with_empty_period(client):
    after = datetime.now()
    before = after - timedelta(minutes=10)
    with pytest.raises(ValueError, match=r'.*period.*'):
        Submission.filter(
            user='first_admin',
            after=after,
            before=before,
        )
