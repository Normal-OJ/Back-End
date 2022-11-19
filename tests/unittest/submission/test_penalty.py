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
    Homework,
)


def setup_function(_):
    utils.drop_db()


def teardown_function(_):
    utils.drop_db()


def add_homework(
    user: User,
    course,
    hw_name: str = 'test',
    problem_ids: List[int] = [],
    markdown: str = '',
    scoreboard_status: int = 0,
    start: Optional[float] = int(datetime.now().timestamp()),
    end: Optional[float] = int(datetime.now().timestamp()),
    penalty: Optional[str] = '',
):
    '''
    Add problem with default arguments
    '''
    if hw_name is None:
        problem_name = secrets.token_hex(16)

    return Homework.add(
        user=user,
        course_name=course,
        markdown=markdown,
        hw_name=hw_name,
        start=start,
        end=end,
        penalty=penalty,
        problem_ids=problem_ids,
        scoreboard_status=scoreboard_status,
    )


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


def test_penalty_exist(client):

    hw = add_homework(user=User('first_admin'),
                      course='Public',
                      penalty='score=score*(0.8**overtime)',
                      hw_name='test1')
    assert Homework.get_by_name(
        'Public', 'test1').penalty == 'score=score*(0.8**overtime)'


def test_penalty(client, app):

    course = utils.course.create_course(name='Test', )
    student = utils.user.create_user(
        username='student',
        course=course,
        role=2,
    )

    problem = utils.problem.create_problem(course=course)
    hw = add_homework(user=User('first_admin'),
                      course='Test',
                      penalty='score=score*(0.8**overtime)',
                      problem_ids=[problem.id],
                      start=int(datetime.now().timestamp()) - 86411,
                      end=int(datetime.now().timestamp()) - 86410,
                      hw_name='qqoot')
    with app.app_context():
        submission = utils.submission.create_submission(
            problem=problem,
            user=student,
            lang=0,
            score=100,
        )
        submission.finish_judging()
    assert Homework.get_by_name('Test',
                                'qqoot').student_status[student.username][str(
                                    problem.id)]['score'] == 80


def test_penalty2(client, app):

    course = utils.course.create_course(name='Test', )
    student = utils.user.create_user(
        username='student',
        course=course,
        role=2,
    )

    problem = utils.problem.create_problem(course=course)
    hw = add_homework(user=User('first_admin'),
                      course='Test',
                      penalty='score=score*(0.7**overtime)',
                      problem_ids=[problem.id],
                      start=int(datetime.now().timestamp()) - 86411,
                      end=int(datetime.now().timestamp()) - 86410,
                      hw_name='qqoot')
    with app.app_context():
        submission = utils.submission.create_submission(
            problem=problem,
            user=student,
            lang=0,
            score=50,
            timestamp=float(int(datetime.now().timestamp()) - 86410),
        )
        submission.finish_judging()
        submission = utils.submission.create_submission(
            problem=problem,
            user=student,
            lang=0,
            score=100,
        )
        submission.finish_judging()
    assert Homework.get_by_name(
        'Test', 'qqoot').student_status[student.username][str(
            problem.id)]['score'] == 85 and Homework.get_by_name(
                'Test', 'qqoot').student_status[student.username][str(
                    problem.id)]['rawScore'] == 100


def test_no_penalty(client, app):

    course = utils.course.create_course(name='Test', )
    student = utils.user.create_user(
        username='student',
        course=course,
        role=2,
    )

    problem = utils.problem.create_problem(course=course)
    hw = add_homework(user=User('first_admin'),
                      course='Test',
                      penalty='',
                      problem_ids=[problem.id],
                      start=int(datetime.now().timestamp()) - 86411,
                      end=int(datetime.now().timestamp()) - 86410,
                      hw_name='qqoot')
    with app.app_context():
        submission = utils.submission.create_submission(
            problem=problem,
            user=student,
            lang=0,
            score=100,
        )
        submission.finish_judging()
    assert Homework.get_by_name('Test',
                                'qqoot').student_status[student.username][str(
                                    problem.id)]['score'] == 100


def test_penalty_in_time(client, app):

    course = utils.course.create_course(name='Test', )
    student = utils.user.create_user(
        username='student',
        course=course,
        role=2,
    )

    problem = utils.problem.create_problem(course=course)
    hw = add_homework(user=User('first_admin'),
                      course='Test',
                      penalty='score=score*(0.7**overtime)',
                      problem_ids=[problem.id],
                      start=int(datetime.now().timestamp()) - 1,
                      end=int(datetime.now().timestamp()),
                      hw_name='qqoot')
    with app.app_context():
        submission = utils.submission.create_submission(
            problem=problem,
            user=student,
            lang=0,
            score=100,
        )
        submission.finish_judging()
    assert Homework.get_by_name('Test',
                                'qqoot').student_status[student.username][str(
                                    problem.id)]['score'] == 100