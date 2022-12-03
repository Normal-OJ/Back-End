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


def test_penalty_exist(client):

    hw = utils.homework.add_homework(user=User('first_admin'),
                      course='Public',
                      penalty='score=score*(0.8**overtime)',
                      hw_name='test1',
                      markdown = '',
                      scoreboard_status = 0,
                      start = 0,
                      end = 0,
                      problem_ids = [],
                      )
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
    hw = utils.homework.add_homework(user=User('first_admin'),
                      course='Test',
                      penalty='score=score*(0.8**overtime)',
                      problem_ids=[problem.id],
                      start=int(datetime.now().timestamp()) - 86411,
                      end=int(datetime.now().timestamp()) - 86410,
                      hw_name='test',
                      markdown = '',
                      scoreboard_status = 0,)
    with app.app_context():
        submission = utils.submission.create_submission(
            problem=problem,
            user=student,
            lang=0,
            score=100,
        )
        submission.finish_judging()
    assert Homework.get_by_name('Test',
                                'test').student_status[student.username][str(
                                    problem.id)]['score'] == 80


def test_penalty2(client, app):

    course = utils.course.create_course(name='Test', )
    student = utils.user.create_user(
        username='student',
        course=course,
        role=2,
    )

    problem = utils.problem.create_problem(course=course)
    hw = utils.homework.add_homework(user=User('first_admin'),
                      course='Test',
                      penalty='score=score*(0.7**overtime)',
                      problem_ids=[problem.id],
                      start=int(datetime.now().timestamp()) - 86411,
                      end=int(datetime.now().timestamp()) - 86410,
                      hw_name='test',
                      markdown = '',
                      scoreboard_status = 0,)
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
        'Test', 'test').student_status[student.username][str(
            problem.id)]['score'] == 85 and Homework.get_by_name(
                'Test', 'test').student_status[student.username][str(
                    problem.id)]['rawScore'] == 100


def test_no_penalty(client, app):

    course = utils.course.create_course(name='Test', )
    student = utils.user.create_user(
        username='student',
        course=course,
        role=2,
    )

    problem = utils.problem.create_problem(course=course)
    hw = utils.homework.add_homework(user=User('first_admin'),
                      course='Test',
                      penalty='',
                      problem_ids=[problem.id],
                      start=int(datetime.now().timestamp()) - 86411,
                      end=int(datetime.now().timestamp()) - 86410,
                      hw_name='test',
                      markdown = '',
                      scoreboard_status = 0,)
    with app.app_context():
        submission = utils.submission.create_submission(
            problem=problem,
            user=student,
            lang=0,
            score=100,
        )
        submission.finish_judging()
    assert Homework.get_by_name('Test',
                                'test').student_status[student.username][str(
                                    problem.id)]['score'] == 0


def test_penalty_in_time(client, app):

    course = utils.course.create_course(name='Test', )
    student = utils.user.create_user(
        username='student',
        course=course,
        role=2,
    )

    problem = utils.problem.create_problem(course=course)
    hw = utils.homework.add_homework(user=User('first_admin'),
                      course='Test',
                      penalty='score=score*(0.7**overtime)',
                      problem_ids=[problem.id],
                      start=int(datetime.now().timestamp()) - 1,
                      end=int(datetime.now().timestamp()) + 86400,
                      hw_name='test',
                      markdown = '',
                      scoreboard_status = 0,)
    with app.app_context():
        submission = utils.submission.create_submission(
            problem=problem,
            user=student,
            lang=0,
            score=100,
        )
        submission.finish_judging()
    assert Homework.get_by_name('Test',
                                'test').student_status[student.username][str(
                                    problem.id)]['score'] == 100