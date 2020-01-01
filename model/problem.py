from flask import Blueprint, request

from mongo import *
from mongo import engine
from .auth import *
from .utils import *
from mongo.problem import *

__all__ = ['problem_api']

problem_api = Blueprint('problem_api', __name__)


@problem_api.route('/', methods=['GET'])
@login_required
@Request.args('offset', 'count')
def view_problem_list(user, offset, count):

    if offset is None or count is None:
        return HTTPError(
            'offset and count are required!',
            400,
        )

    # casting args
    try:
        offset = int(offset)
        count = int(count)
    except ValueError:
        return HTTPError(
            'offset and count must be integer!',
            400,
        )

    # check range
    if offset < 0:
        return HTTPError(
            'offset must >= 0!',
            400,
        )
    if count < -1:
        return HTTPError(
            'count must >=-1!',
            400,
        )

    data = get_problem_list(user, offset, count)
    return HTTPResponse('Success.', data=data)


@problem_api.route('/view/<problem_id>', methods=['GET'])
@login_required
def view_problem(user, problem_id):
    problem = Problem(problem_id).obj
    if problem is None:
        return HTTPError('Problem not exist.', 404)
    if not can_view(user, problem):
        return HTTPError('Problem cannot view.', 403)

    data = {
        'status': problem.problem_status,
        'type': problem.problem_type,
        'problemName': problem.problem_name,
        'description': problem.description,
        'owner': problem.owner,
        'tags': problem.tags
        # 'pdf':
    }
    if problem.problem_type == 1:
        data.update({'fillInTemplate': problem.test_case.fill_in_template})

    return HTTPResponse('Problem can view.', data=data)


@problem_api.route('/manage', methods=['POST'])
@problem_api.route('/manage/<problem_id>', methods=['GET', 'PUT', 'DELETE'])
@identity_verify(0, 1)
def manage_problem(user, problem_id=None):
    @Request.json('courses',
                  'status',
                  'type',
                  'description',
                  'tags',
                  vars_dict={
                      'problem_name': 'problemName',
                      'test_case': 'testCase'
                  })
    def modify_problem(courses, status, type, problem_name, description, tags,
                       test_case):
        if request.method == 'POST':
            number = add_problem(user, courses, status, type, problem_name,
                                 description, tags, test_case)
            return HTTPResponse('Success.', data={'problemId': number})
        elif request.method == 'PUT':
            edit_problem(user, problem_id, courses, status, type, problem_name,
                         description, tags, test_case)
            return HTTPResponse('Success.')

    if request.method != 'POST':
        problem = Problem(problem_id).obj
        if problem is None:
            return HTTPError('Problem not exist.', 404)
        if user.role == 1 and problem.owner != user.username:
            return HTTPError('Not the owner.', 403)

    if request.method == 'GET':
        data = {
            'courses': list(course.course_name for course in problem.courses),
            'status': problem.problem_status,
            'type': problem.problem_type,
            'problemName': problem.problem_name,
            'description': problem.description,
            'tags': problem.tags,
            'testCase': {
                'language': problem.test_case['language'],
                'fillInTemplate': problem.test_case['fill_in_template'],
                'cases': problem.test_case['cases']
            },
            'ACUser': problem.ac_user,
            'submitter': problem.submitter
        }
        return HTTPResponse('Success.', data=data)
    elif request.method == 'DELETE':
        delete_problem(problem_id)
        return HTTPResponse('Success.')
    else:
        try:
            return modify_problem()
        except ValidationError as ve:
            return HTTPError('Invalid or missing arguments.',
                             400,
                             data=ve.to_dict())
        except engine.DoesNotExist:
            return HTTPError('Course not found.', 404)


@problem_api.route('/clone', methods=['POST'])
@identity_verify(0, 1)
@Request.json(vars_dict={'problem_id': 'problemId'})
def clone_problem(user, problem_id):
    problem = Problem(problem_id).obj
    if problem is None:
        return HTTPError('Problem not exist.', 404)
    if not can_view(user, problem):
        return HTTPError('Problem can not view.', 403)

    copy_problem(user, problem_id)
    return HTTPResponse('Success.')


@problem_api.route('/publish', methods=['POST'])
@identity_verify(0, 1)
@Request.json(vars_dict={'problem_id': 'problemId'})
def publish_problem(user, problem_id):
    problem = Problem(problem_id).obj
    if problem is None:
        return HTTPError('Problem not exist.', 404)
    if user.role == 1 and problem.owner != user.username:
        return HTTPError('Not the owner.', 403)

    release_problem(problem_id)
    return HTTPResponse('Success.')
