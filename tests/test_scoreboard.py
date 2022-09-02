from pprint import pprint
from random import randint
from typing import Dict
import pytest
from mongo import User
from tests.base_tester import BaseTester
from tests.conftest import forge_client
from . import utils


def setup_function(_):
    # TODO: if not called, the client_admin will have invalid token to access
    BaseTester.setup_class()


@pytest.fixture(scope='function')
def context():
    admin = utils.user.create_user(role=0)
    student = utils.user.create_user(role=2)
    course = utils.course.create_course(students=[student])
    teacher = course.teacher
    problem = utils.problem.create_problem(course=course, owner=teacher)
    return {
        'admin': admin,
        'course': course,
        'teacher': teacher,
        'problem': problem,
        'student': student,
    }


@pytest.mark.parametrize('testcase', [
    {
        "problem_count": 1,
        "student_count": 1
    },
    {
        "problem_count": 1,
        "student_count": 2
    },
    {
        "problem_count": 2,
        "student_count": 1
    },
    {
        "problem_count": 2,
        "student_count": 2
    },
    {
        "problem_count": 4,
        "student_count": 3
    },
    {
        "problem_count": 10,
        "student_count": 1
    },
])
def test_get_correct_query_result_with_no_submission(context, testcase):
    course = context['course']
    students = [context['student']] + [
        utils.user.create_user(role=2, course=course)
        for _ in range(testcase['student_count'] - 1)
    ]
    problems = [context['problem']] + [
        utils.problem.create_problem(course=course, owner=course.teacher)
        for _ in range(testcase['problem_count'] - 1)
    ]
    data = course.get_scoreboard(problems)
    assert len(data) == testcase['student_count'], data
    for student in students:
        # find element in array
        row = next(
            filter(
                lambda x: x['user']['username'] == student.username,
                data,
            ),
            None,
        )
        assert row['user'] == student.info
        assert row['avg'] == 0
        assert row['sum'] == 0
        for problem in problems:
            assert row.get(problem.id) == None
            assert row['sum'] == 0
            assert row['avg'] == 0


@pytest.mark.parametrize('testcase', [
    {
        'input': {
            'students': ['alice', 'bob', 'carol', 'dave', 'eve', 'fay'],
            'submissions': {
                'alice': [100],
                'bob': [25, 50],
                'carol': [100, 0, 0],
                'dave': [100, 100],
                'eve': [0, 0],
            }
        },
        'output': [
            {
                'sum': 100,
                'avg': 100.0,
                'user': 'alice',
                '2': {
                    'pid': 2,
                    'count': 1,
                    'max': 100,
                    'min': 100,
                    'avg': 100.0
                },
            },
            {
                'sum': 50,
                'avg': 50.0,
                'user': 'bob',
                '2': {
                    'pid': 2,
                    'count': 2,
                    'max': 50,
                    'min': 25,
                    'avg': 37.5
                },
            },
            {
                'sum': 100,
                'avg': 100.0,
                'user': 'carol',
                '2': {
                    'pid': 2,
                    'count': 3,
                    'max': 100,
                    'min': 0,
                    'avg': 100 / 3
                },
            },
            {
                'sum': 100,
                'avg': 100.0,
                'user': 'dave',
                '2': {
                    'pid': 2,
                    'count': 2,
                    'max': 100,
                    'min': 100,
                    'avg': 100.0
                },
            },
            {
                'sum': 0,
                'avg': 0.0,
                'user': 'eve',
                '2': {
                    'pid': 2,
                    'count': 2,
                    'max': 0,
                    'min': 0,
                    'avg': 0.0
                },
            },
            {
                'sum': 0,
                'avg': 0,
                'user': 'fay'
            },
        ],
    },
])
def test_get_correct_query_result_with_single_problem(context, testcase, app):
    students = testcase['input']['students']
    submissions = testcase['input']['submissions']
    students = [utils.user.create_user(role=2, username=u) for u in students]
    course = utils.course.create_course(students=students)
    problem = utils.problem.create_problem(course=course, owner=course.teacher)
    with app.app_context():
        for username, scores in submissions.items():
            for score in scores:
                utils.submission.create_submission(
                    user=username,
                    problem=problem,
                    score=score,
                )
        data = course.get_scoreboard([problem.id])
        assert len(data) == len(students), data
        output = [{
            **item, 'user': User(item['user']).info
        } for item in testcase['output']]
        data = sorted(data, key=lambda x: x['user']['username'])
        assert data == output


@pytest.mark.parametrize('testcase', [
    {
        'input': {
            'students': ['alice', 'bob', 'carol', 'dave', 'eve', 'fay'],
            'problems': [2, 3],
            'submissions': {
                'alice': ['problem=2&score=100'],
                'bob': ['problem=2&score=25', 'problem=3&score=50'],
                'carol': [
                    'problem=2&score=100', 'problem=2&score=0',
                    'problem=3&score=0', 'problem=3&score=0'
                ],
                'dave': [
                    'problem=3&score=100', 'problem=2&score=100',
                    'problem=2&score=20'
                ],
                'eve': ['problem=2&score=0', 'problem=3&score=0'],
            }
        },
        'output': [
            {
                'sum': 100,
                'avg': 50.0,
                'user': 'alice',
                '2': {
                    'pid': 2,
                    'count': 1,
                    'max': 100,
                    'min': 100,
                    'avg': 100.0
                },
            },
            {
                'sum': 75,
                'avg': 37.5,
                'user': 'bob',
                '2': {
                    'pid': 2,
                    'count': 1,
                    'max': 25,
                    'min': 25,
                    'avg': 25.0
                },
                '3': {
                    'pid': 3,
                    'count': 1,
                    'max': 50,
                    'min': 50,
                    'avg': 50.0
                },
            },
            {
                'sum': 100,
                'avg': 50.0,
                'user': 'carol',
                '2': {
                    'pid': 2,
                    'count': 2,
                    'max': 100,
                    'min': 0,
                    'avg': 100 / 2
                },
                '3': {
                    'pid': 3,
                    'count': 2,
                    'max': 0,
                    'min': 0,
                    'avg': 0.0
                },
            },
            {
                'sum': 200,
                'avg': 100.0,
                'user': 'dave',
                '2': {
                    'pid': 2,
                    'count': 2,
                    'max': 100,
                    'min': 20,
                    'avg': 60.0
                },
                '3': {
                    'pid': 3,
                    'count': 1,
                    'max': 100,
                    'min': 100,
                    'avg': 100.0
                },
            },
            {
                'sum': 0,
                'avg': 0.0,
                'user': 'eve',
                '2': {
                    'pid': 2,
                    'count': 1,
                    'max': 0,
                    'min': 0,
                    'avg': 0.0
                },
                '3': {
                    'pid': 3,
                    'count': 1,
                    'max': 0,
                    'min': 0,
                    'avg': 0.0
                },
            },
            {
                'sum': 0,
                'avg': 0,
                'user': 'fay'
            },
        ],
    },
])
def test_get_correct_query_result_with_multiple_problems(
        context, testcase, app):
    students = testcase['input']['students']
    submissions = testcase['input']['submissions']
    problems = testcase['input']['problems']
    students = [utils.user.create_user(role=2, username=u) for u in students]
    course = utils.course.create_course(students=students)
    for _ in range(len(problems)):
        utils.problem.create_problem(course=course, owner=course.teacher)
    with app.app_context():
        for username, subs in submissions.items():
            for s in subs:
                params = {
                    param.split('=')[0]: int(param.split('=')[1])
                    for param in s.split('&')
                }
                utils.submission.create_submission(
                    user=username,
                    **params,
                )
        data = course.get_scoreboard(problems)
        assert len(data) == len(students), data
        output = [{
            **item, 'user': User(item['user']).info
        } for item in testcase['output']]
        data = sorted(data, key=lambda x: x['user']['username'])
        assert data == output


t1 = 1648832400
t2 = 1648922400
before_t1 = 1648771200
between_t1_t2 = 1648857600
after_t2 = 1648940400
more_after_t2 = 1648942200
test_input = {
    'students': ['alice', 'bob', 'carol', 'dave', 'eve', 'fay'],
    'problems': [2, 3],
    'submissions': {
        'alice': [f'timestamp={t1}&problem=2&score=100'],
        'bob': [
            f'timestamp={t1}&problem=2&score=25',
            f'timestamp={t2}&problem=3&score=50'
        ],
        'carol': [
            f'timestamp={t1}&problem=2&score=100',
            f'timestamp={t2}&problem=2&score=0',
            f'timestamp={t1}&problem=3&score=0',
            f'timestamp={t2}&problem=3&score=0',
        ],
        'dave': [
            f'timestamp={t1}&problem=3&score=100',
            f'timestamp={t1}&problem=2&score=100',
            f'timestamp={t2}&problem=2&score=20',
        ],
        'eve': [
            f'timestamp={t2}&problem=2&score=0',
            f'timestamp={t2}&problem=3&score=0'
        ],
    }
}


@pytest.mark.parametrize('testcase', [
    {
        'input': {
            'start': t1,
            'end': t2,
            **test_input,
        },
        'output': [
            {
                'sum': 100,
                'avg': 50.0,
                'user': 'alice',
                '2': {
                    'pid': 2,
                    'count': 1,
                    'max': 100,
                    'min': 100,
                    'avg': 100.0
                },
            },
            {
                'sum': 75,
                'avg': 37.5,
                'user': 'bob',
                '2': {
                    'pid': 2,
                    'count': 1,
                    'max': 25,
                    'min': 25,
                    'avg': 25.0
                },
                '3': {
                    'pid': 3,
                    'count': 1,
                    'max': 50,
                    'min': 50,
                    'avg': 50.0
                },
            },
            {
                'sum': 100,
                'avg': 50.0,
                'user': 'carol',
                '2': {
                    'pid': 2,
                    'count': 2,
                    'max': 100,
                    'min': 0,
                    'avg': 100 / 2
                },
                '3': {
                    'pid': 3,
                    'count': 2,
                    'max': 0,
                    'min': 0,
                    'avg': 0.0
                },
            },
            {
                'sum': 200,
                'avg': 100.0,
                'user': 'dave',
                '2': {
                    'pid': 2,
                    'count': 2,
                    'max': 100,
                    'min': 20,
                    'avg': 60.0
                },
                '3': {
                    'pid': 3,
                    'count': 1,
                    'max': 100,
                    'min': 100,
                    'avg': 100.0
                },
            },
            {
                'sum': 0,
                'avg': 0.0,
                'user': 'eve',
                '2': {
                    'pid': 2,
                    'count': 1,
                    'max': 0,
                    'min': 0,
                    'avg': 0.0
                },
                '3': {
                    'pid': 3,
                    'count': 1,
                    'max': 0,
                    'min': 0,
                    'avg': 0.0
                },
            },
            {
                'sum': 0,
                'avg': 0,
                'user': 'fay'
            },
        ],
    },
    {
        'input': {
            'start': before_t1,
            'end': t1,
            **test_input,
        },
        'output': [
            {
                'sum': 100,
                'avg': 50.0,
                'user': 'alice',
                '2': {
                    'pid': 2,
                    'count': 1,
                    'max': 100,
                    'min': 100,
                    'avg': 100.0
                },
            },
            {
                'sum': 25,
                'avg': 12.5,
                'user': 'bob',
                '2': {
                    'pid': 2,
                    'count': 1,
                    'max': 25,
                    'min': 25,
                    'avg': 25.0
                },
            },
            {
                'sum': 100,
                'avg': 50.0,
                'user': 'carol',
                '2': {
                    'pid': 2,
                    'count': 1,
                    'max': 100,
                    'min': 100,
                    'avg': 100
                },
                '3': {
                    'pid': 3,
                    'count': 1,
                    'max': 0,
                    'min': 0,
                    'avg': 0.0
                },
            },
            {
                'sum': 200,
                'avg': 100.0,
                'user': 'dave',
                '2': {
                    'pid': 2,
                    'count': 1,
                    'max': 100,
                    'min': 100,
                    'avg': 100.0
                },
                '3': {
                    'pid': 3,
                    'count': 1,
                    'max': 100,
                    'min': 100,
                    'avg': 100.0
                },
            },
            {
                'sum': 0,
                'avg': 0.0,
                'user': 'eve'
            },
            {
                'sum': 0,
                'avg': 0,
                'user': 'fay'
            },
        ],
    },
    {
        'input': {
            'start': between_t1_t2,
            'end': after_t2,
            **test_input,
        },
        'output': [
            {
                'sum': 0,
                'avg': 0.0,
                'user': 'alice'
            },
            {
                'sum': 50,
                'avg': 25.0,
                'user': 'bob',
                '3': {
                    'pid': 3,
                    'count': 1,
                    'max': 50,
                    'min': 50,
                    'avg': 50.0
                },
            },
            {
                'sum': 0,
                'avg': 0,
                'user': 'carol',
                '2': {
                    'pid': 2,
                    'count': 1,
                    'max': 0,
                    'min': 0,
                    'avg': 0.0
                },
                '3': {
                    'pid': 3,
                    'count': 1,
                    'max': 0,
                    'min': 0,
                    'avg': 0.0
                },
            },
            {
                'sum': 20,
                'avg': 10.0,
                'user': 'dave',
                '2': {
                    'pid': 2,
                    'count': 1,
                    'max': 20,
                    'min': 20,
                    'avg': 20.0
                },
            },
            {
                'sum': 0,
                'avg': 0,
                'user': 'eve',
                '2': {
                    'pid': 2,
                    'count': 1,
                    'max': 0,
                    'min': 0,
                    'avg': 0.0
                },
                '3': {
                    'pid': 3,
                    'count': 1,
                    'max': 0,
                    'min': 0,
                    'avg': 0.0
                },
            },
            {
                'sum': 0,
                'avg': 0,
                'user': 'fay'
            },
        ],
    },
    {
        'input': {
            'start': after_t2,
            'end': more_after_t2,
            **test_input,
        },
        'output': [
            {
                'sum': 0,
                'avg': 0,
                'user': 'alice'
            },
            {
                'sum': 0,
                'avg': 0,
                'user': 'bob'
            },
            {
                'sum': 0,
                'avg': 0,
                'user': 'carol'
            },
            {
                'sum': 0,
                'avg': 0,
                'user': 'dave'
            },
            {
                'sum': 0,
                'avg': 0,
                'user': 'eve'
            },
            {
                'sum': 0,
                'avg': 0,
                'user': 'fay'
            },
        ],
    },
])
def test_get_correct_query_result_with_multiple_problems_and_range(
        context, testcase, app):
    students = testcase['input']['students']
    submissions = testcase['input']['submissions']
    problems = testcase['input']['problems']
    students = [utils.user.create_user(role=2, username=u) for u in students]
    course = utils.course.create_course(students=students)
    for _ in range(len(problems)):
        utils.problem.create_problem(course=course, owner=course.teacher)
    with app.app_context():
        for username, subs in submissions.items():
            for s in subs:
                params = {
                    param.split('=')[0]: int(param.split('=')[1])
                    for param in s.split('&')
                }
                s = utils.submission.create_submission(
                    user=username,
                    **params,
                )
                if username == 'eve':
                    print(s.timestamp)
        data = course.get_scoreboard(problems, testcase['input']['start'],
                                     testcase['input']['end'])
        assert len(data) == len(students), data
        output = [{
            **item, 'user': User(item['user']).info
        } for item in testcase['output']]
        data = sorted(data, key=lambda x: x['user']['username'])
        assert data == output, data


@pytest.mark.parametrize('query', [{}, {'pids': ''}])
def test_get_error_for_no_provided_pids(context, forge_client, query: Dict,
                                        app):
    with app.app_context():
        client = forge_client(username=context['student'].username)
        qs = '&'.join(f'{k}={v}' for k, v in query.items())
        rv = client.get(
            f'/course/{context["course"].course_name}/scoreboard?{qs}')
        assert rv.status_code == 400


@pytest.mark.parametrize('pids', ['a', '1,a', '1,2,a', None, 'None', '1,'])
def test_get_error_for_providing_unparsable_pids(context, forge_client,
                                                 pids: str, app):
    with app.app_context():
        client = forge_client(username=context['admin'].username)
        rv = client.get(
            f'/course/{context["course"].course_name}/scoreboard?pids={pids}')
        assert rv.status_code == 400
        assert rv.json['message'] == 'Error occurred when parsing `pids`.'
