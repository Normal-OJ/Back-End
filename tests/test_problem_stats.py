import math
from random import randint, shuffle
import pytest
from mongo import course
from mongo import User
from mongo.engine import Problem
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


def test_get_correct_query_result_with_no_submission(context):
    problem = context['problem']
    assert problem.get_ac_user_count() == 0
    assert problem.get_tried_user_count() == 0
    assert all([v == 0 for v in problem.get_submission_status().values()])


@pytest.mark.parametrize('status', [
    {
        '0': 1
    },
    {
        '1': 1
    },
    {
        '0': 1,
        '1': 2
    },
    {
        '1': 3,
        '2': 4,
        '6': 1
    },
    {
        '-1': 2,
        '0': 3,
        '3': 4
    },
])
def test_get_correct_query_result_with_multiple_status(context, status, app):
    problem = context['problem']
    student = context['student']
    with app.app_context():
        for k, v in status.items():
            for _ in range(v):
                utils.submission.create_submission(problem=problem,
                                                   user=student,
                                                   status=int(k))
        ac_user_count = 1 if status.get('0') else 0
        assert problem.get_ac_user_count() == ac_user_count
        assert problem.get_tried_user_count() == 1
        submission_count = problem.get_submission_status()
        assert all([
            status.get(str(k), 0) == v for k, v in submission_count.items()
        ]), submission_count


@pytest.mark.parametrize('role', ['admin', 'teacher', 'student'])
def test_get_correct_stats_with_ac_submission(context, forge_client, role,
                                              app):
    problem = context['problem']
    student = context['student']
    with app.app_context():
        utils.submission.create_submission(
            problem=problem,
            user=student,
            status=0,
        )
        client = forge_client(username=context[role].username)
        rv = client.get(f'/problem/{problem.id}/stats')
        assert rv.status_code == 200, rv.data
        data = rv.get_json()['data']
        assert data['acUserRatio'] == [1, 1]
        assert data['triedUserCount'] == 1
        assert data['scoreDistribution'] == [100]
        assert data['average'] == 100
        assert data['std'] == None
        assert data['statusCount'] == {'0': 1}


@pytest.mark.parametrize('role', [1, 2])
def test_clients_without_permission(context, forge_client, role, app):
    problem = context['problem']
    user_from_other_course = utils.user.create_user(role=role)
    with app.app_context():
        client = forge_client(user_from_other_course)
        rv = client.get(f'/problem/{problem.id}/stats')
        assert rv.status_code == 403, rv.data


@pytest.mark.parametrize('td', [
    {
        'stu_submissions': [
            [{
                'status': 0,
                'score': 100
            }],
            [{
                'status': 1,
                'score': 50
            }, {
                'status': 1,
                'score': 75
            }],
        ],
        'high_scores': [100, 75],
        'average':
        87.5,
        'std':
        12.5,
        'ac_user':
        1,
        'tried_user':
        2,
        'status_count': {
            '0': 1,
            '1': 2
        },
    },
    {
        'stu_submissions': [
            [{
                'status': 0,
                'score': 100
            }, {
                'status': 0,
                'score': 100
            }],
            [{
                'status': 0,
                'score': 100
            }],
        ],
        'high_scores': [100, 100],
        'average':
        100,
        'std':
        0,
        'ac_user':
        2,
        'tried_user':
        2,
        'status_count': {
            '0': 3
        },
    },
    {
        'stu_submissions': [
            [{
                'status': 0,
                'score': 100
            }, {
                'status': 0,
                'score': 100
            }],
            [{
                'status': 1,
                'score': 50
            }, {
                'status': 2,
                'score': 25
            }],
            [{
                'status': 2,
                'score': 25
            }, {
                'status': 0,
                'score': 100
            }],
            [],
        ],
        'high_scores': [100, 50, 100, 0],
        'average':
        62.5,
        'std':
        41.4578098794,
        'ac_user':
        2,
        'tried_user':
        3,
        'status_count': {
            '0': 3,
            '1': 1,
            '2': 2
        },
    },
])
def test_multiple_student(context, forge_client, td, app):
    stu_submissions = td['stu_submissions']
    problem = context['problem']
    course = context['course']
    students = [context['student']] + [
        utils.user.create_user(role=2, course=course)
        for _ in range(len(stu_submissions) - 1)
    ]
    with app.app_context():
        for i in range(len(stu_submissions)):
            for s in stu_submissions[i]:
                utils.submission.create_submission(
                    problem=problem,
                    user=students[i],
                    status=s['status'],
                    score=s['score'],
                )
        client = forge_client(username=context['student'].username)
        rv = client.get(f'/problem/{problem.id}/stats')
        assert rv.status_code == 200, rv.data
        data = rv.get_json()['data']
        assert data['acUserRatio'] == [td['ac_user'], len(students)]
        assert data['triedUserCount'] == td['tried_user']
        assert sorted(data['scoreDistribution']) == sorted(td['high_scores'])
        assert data['average'] == sum(td['high_scores']) / len(students)
        assert math.isclose(data['std'], td['std'])
        assert data['statusCount'] == td['status_count']


def test_it_wont_count_teacher_and_admin_score(context, forge_client, app):
    problem = context['problem']
    course = context['course']
    student = context['student']
    teacher = context['student']
    admin = context['student']
    with app.app_context():
        utils.submission.create_submission(
            problem=problem,
            user=student,
            status=0,
        )
        utils.submission.create_submission(
            problem=problem,
            user=teacher,
            status=1,
            score=50,
        )
        utils.submission.create_submission(
            problem=problem,
            user=admin,
            status=0,
        )
        client = forge_client(username=context['student'].username)
        rv = client.get(f'/problem/{problem.id}/stats')
        assert rv.status_code == 200, rv.data
        data = rv.get_json()['data']
        assert data['acUserRatio'] == [1, 1]
        assert data['triedUserCount'] == 1
        assert data['average'] == 100
        assert data['std'] == None
        assert data['scoreDistribution'] == [100]
        assert data['statusCount'] == {'0': 2, '1': 1}


def test_top_10_runtime_submissions(context, forge_client, app):
    problem = context['problem']
    student = context['student']
    with app.app_context():
        runtimes = [
            0, 0, 2, 5, 10, 100, 200, 300, 400, 500, 700, 800, 900, 1000
        ]
        shuffled_runtimes = runtimes.copy()
        shuffle(shuffled_runtimes)
        for v in shuffled_runtimes:
            utils.submission.create_submission(problem=problem,
                                               user=student,
                                               status=0,
                                               exec_time=v)
        client = forge_client(username=context['student'].username)
        rv = client.get(f'/problem/{problem.id}/stats')
        assert rv.status_code == 200, rv.data
        data = rv.get_json()['data']
        top_10_runtimes = [s['runTime'] for s in data['top10RunTime']]
        assert top_10_runtimes == runtimes[:10]


def test_top_10_memory_submissions(context, forge_client, app):
    problem = context['problem']
    student = context['student']
    with app.app_context():
        memory = [0, 0, 2, 5, 10, 100, 200, 300, 400, 500, 700, 800, 900, 1000]
        shuffled_memory = memory.copy()
        shuffle(shuffled_memory)
        for v in shuffled_memory:
            utils.submission.create_submission(problem=problem,
                                               user=student,
                                               status=0,
                                               memory_usage=v)
        client = forge_client(username=context['student'].username)
        rv = client.get(f'/problem/{problem.id}/stats')
        assert rv.status_code == 200, rv.data
        data = rv.get_json()['data']
        top_10_memory = [s['memoryUsage'] for s in data['top10MemoryUsage']]
        assert top_10_memory == memory[:10]


def test_cached_highscore(context, forge_client, app):
    problem = context['problem']
    student = context['student']
    with app.app_context():
        utils.submission.create_submission(problem=problem,
                                           user=student,
                                           status=1,
                                           score=50)
        client = forge_client(username=context['student'].username)
        rv = client.get(f'/problem/{problem.id}/stats')
        assert rv.status_code == 200, rv.data
        data = rv.get_json()['data']
        assert data['scoreDistribution'] == [50]

        cached_rv = client.get(f'/problem/{problem.id}/stats')
        assert cached_rv.status_code == 200, cached_rv.data
        cached_data = cached_rv.get_json()['data']
        assert cached_data['scoreDistribution'] == [50]


# def test_performance(context, forge_client, app):
#     problem = context['problem']
#     course = context['course']
#     students = [context['student']] + [
#         utils.user.create_user(role=2, course=course)
#         for _ in range(99)
#     ]
#     with app.app_context():
#         for i in range(1000):
#             utils.submission.create_submission(
#                 problem=problem,
#                 user=students[randint(0, len(students) - 1)],
#             )
#         client = forge_client(username=context['student'].username)
#         rv = client.get(f'/problem/{problem.id}/stats')
#         assert rv.status_code == 200, rv.data
#         assert 0
