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
                    'status': p.problem_status,
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
        'description': {
            'description': problem.description['description'],
            'input': problem.description['input'],
            'output': problem.description['output'],
            'hint': problem.description['hint'],
            'sampleInput': problem.description['sample_input'],
            'sampleOutput': problem.description['sample_output'],
        },
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
    @Request.json('type')
    def modify_problem(type):
        if type == 2:
            return modify_written_problem()
        else:
            return modify_coding_problem()

    @Request.json(
        'courses: list',
        'status',
        'type',
        'description',
        'tags',
        'problem_name',
        'test_case_info',
        'can_view_stdout',
        'allowed_language',
    )
    def modify_coding_problem(**p_ks):
        if sum(case['caseScore']
               for case in p_ks['test_case_info']['tasks']) != 100:
            return HTTPError("Cases' scores should be 100 in total", 400)

        if request.method == 'POST':
            lock.acquire()
            pid = add_problem(user=user, **p_ks)
            lock.release()
            return HTTPResponse('Success.', data={'problemId': pid})
        elif request.method == 'PUT':
            edit_problem(user=user, **p_ks)
            return HTTPResponse('Success.')

    @Request.json('courses: list', 'status', 'description', 'tags',
                  'problem_name')
    def modify_written_problem(courses, status, problem_name, description,
                               tags):
        if request.method == 'POST':
            lock.acquire()
            pid = add_written_problem(user, courses, status, problem_name,
                                      description, tags)
            lock.release()
            return HTTPResponse('Success.', data={'problemId': pid})
        elif request.method == 'PUT':
            edit_written_problem(user, problem_id, courses, status,
                                 problem_name, description, tags)
            return HTTPResponse('Success.')

    @Request.files('case')
    def modify_problem_test_case(case):
        result = edit_problem_test_case(problem_id, case)
        return HTTPResponse('Success.', data=result)

    # get problem object from DB
    if request.method != 'POST':
        problem = Problem(problem_id).obj
        if problem is None:
            return HTTPError('Problem not exist.', 404)
        if user.role == 1 and problem.owner != user.username:
            return HTTPError('Not the owner.', 403)
    # return detailed problem info
    if request.method == 'GET':
        return HTTPResponse('Success.', data=Problem(problem_id).detailed_info)
    # delete problem
    elif request.method == 'DELETE':
        delete_problem(problem_id)
        return HTTPResponse('Success.')
    # edit problem
    else:
        try:
            # modify problem meta
            if request.content_type.startswith('application/json'):
                return modify_problem()
            # upload testcase file
            elif request.content_type.startswith('multipart/form-data'):
                return modify_problem_test_case()
            else:
                return HTTPError(
                    'Unknown content type',
                    400,
                    data={'contentType': request.content_type},
                )
        except ValidationError as ve:
            if lock.locked():
                lock.release()
            return HTTPError(
                'Invalid or missing arguments.',
                400,
                data=ve.to_dict(),
            )
        except engine.DoesNotExist:
            if lock.locked():
                lock.release()
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
