import pytest
import time
from datetime import datetime, timedelta
from tests import utils
from mongo import Submission, User


def setup_function(_):
    utils.drop_db()


def teardown_function(_):
    utils.drop_db()


def test_param_before():
    admin = utils.user.create_user(role=User.engine.Role.ADMIN)
    problem_id = utils.problem.create_problem(
        owner=admin,
        course='Public',
    ).problem_id
    Submission.add(
        problem_id=problem_id,
        username=admin.username,
        lang=0,
    )
    assert len(Submission.filter(
        user=admin,
        before=datetime.now(),
    )) == 1
    time.sleep(0.01)
    before = datetime.now()
    for _ in range(16):
        Submission.add(
            problem_id=problem_id,
            username=admin.username,
            lang=0,
        )
    assert len(Submission.filter(
        user=admin,
        before=before,
    )) == 1


def test_param_after():
    expected_count = 16
    admin = utils.user.create_user(role=User.engine.Role.ADMIN)
    problem_id = utils.problem.create_problem(
        owner=admin,
        course='Public',
    ).problem_id
    for _ in range(expected_count):
        Submission.add(
            problem_id=problem_id,
            username=admin.username,
            lang=0,
        )
    time.sleep(0.01)
    after = datetime.now()
    for _ in range(expected_count):
        Submission.add(
            problem_id=problem_id,
            username=admin.username,
            lang=0,
        )
    assert len(Submission.filter(
        user=admin,
        after=after,
    )) == expected_count


def test_query_period():
    after = datetime.now()
    expected_count = 16
    admin = utils.user.create_user(role=User.engine.Role.ADMIN)
    problem_id = utils.problem.create_problem(
        owner=admin,
        course='Public',
    ).problem_id
    for _ in range(expected_count):
        Submission.add(
            problem_id=problem_id,
            username=admin.username,
            lang=0,
        )
    assert len(
        Submission.filter(
            user=admin,
            after=after,
            before=datetime.now(),
        )) == expected_count


def test_with_empty_period():
    after = datetime.now()
    before = after - timedelta(minutes=10)
    admin = utils.user.create_user(role=User.engine.Role.ADMIN)
    with pytest.raises(ValueError, match=r'.*period.*'):
        Submission.filter(
            user=admin.username,
            after=after,
            before=before,
        )
