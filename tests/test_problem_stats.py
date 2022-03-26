import pytest
from mongo import course
from mongo import User
from tests.base_tester import BaseTester
from . import utils


def setup_function(_):
    # TODO: if not called, the client_admin will have invalid token to access
    BaseTester.setup_class()


@pytest.fixture(scope='function')
def context():
    student = utils.user.create_user(role=2)
    course = utils.course.create_course(students=[student])
    teacher = course.teacher
    problem = utils.problem.create_problem(course=course, owner=teacher)
    return {
        'course': course,
        'teacher': teacher,
        'problem': problem,
        'student': student,
    }


def test_problem_stats_with_no_submission(context):
    problem = context['problem']
    assert problem.get_ac_user_count() == 0
    assert problem.get_tried_user_count() == 0
    assert all([v == 0 for v in problem.get_submission_status().values()])
    

def test_problem_stats_with_ac_submissions(context, client_admin, app):
    problem = context['problem']
    student = context['student']
    with app.app_context():
        utils.submission.create_submission(
            problem=problem,
            user=student,
            status=0,
        )
        rv = client_admin.get(f'/problem/{problem.id}/stats')
        assert rv.status_code == 200, rv.data
        data = rv.get_json()['data']
        assert data['acUserRatio'] == [1, 1]
        assert data['triedUserCount'] == 1
        assert data['scoreDistribution'] == [100]
        assert data['average'] == 100
        assert data['std'] == None
        assert data['statusCount'] == { '0': 1 }
