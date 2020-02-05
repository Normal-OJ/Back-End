from flask import Blueprint, request
from urllib import parse

from mongo import *
from mongo import engine
from .auth import *
from .utils import *
from mongo.problem import *
import threading

__all__ = ['problem_api']

problem_api = Blueprint('problem_api', __name__)
lock = threading.Lock()


@problem_api.route('/', methods=['GET'])
@login_required
@Request.args('offset', 'count', 'problem_id', 'tags', 'name')
def view_problem_list(user, offset, count, problem_id, tags, name):

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
        return HTTPError('count must >=-1!', 400)

    try:
        problem_id, name, tags = (parse.unquote(p or '') or None
                                  for p in [problem_id, name, tags])

        data = get_problem_list(
            user,
            offset,
            count,
            problem_id,
            name,
            tags and tags.split(','),
        )
        data = [
            *map(
                lambda p: {
                    'problemId': p.problem_id,
                    'problemName': p.problem_name,
                    'ACUser': p.ac_user,
                    'submitter': p.submitter,
                    'tags': p.tags,
                    'type': p.problem_type,
                }, data)
        ]
    except IndexError:
        return HTTPError('offset out of range!', 403)
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
    @Request.json('courses: list', 'status', 'type', 'description', 'tags',
                  'problem_name', 'test_case_info', 'can_view_stdout')
    def modify_problem(courses, status, type, problem_name, description, tags,
                       test_case_info, can_view_stdout):
        if sum(case['caseScore'] for case in test_case_info['cases']) != 100:
            return HTTPError("Cases' scores should be 100 in total", 400)

        if request.method == 'POST':
            lock.acquire()
            pid = add_problem(user, courses, status, type, problem_name,
                              description, tags, test_case_info,
                              can_view_stdout)
            lock.release()
            return HTTPResponse('Success.', data={'problemId': pid})
        elif request.method == 'PUT':
            result = edit_problem(user, problem_id, courses, status, type,
                                  problem_name, description, tags,
                                  test_case_info)
            return HTTPResponse('Success.', data=result)

    @Request.files('case')
    def modify_problem_test_case(case):
        result = edit_problem_test_case(problem_id, case)
        return HTTPResponse('Success.', data=result)

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
                'language':
                problem.test_case['language'],
                'fillInTemplate':
                problem.test_case['fill_in_template'],
                'cases':
                list({
                    'input': case.input,
                    'output': case.output,
                    'caseScore': case.case_score,
                    'memoryLimit': case.memory_limit,
                    'timeLimit': case.time_limit
                } for case in problem.test_case['cases'])
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
            if request.content_type == 'application/json':
                return modify_problem()
            elif request.content_type.startswith('multipart/form-data'):
                return modify_problem_test_case()
        except ValidationError as ve:
            if lock.locked:
                lock.release()
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

    lock.acquire()
    copy_problem(user, problem_id)
    lock.release()
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
