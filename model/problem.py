from flask import Blueprint, request

from mongo import *
from .auth import *
from .utils import *
from mongo.problem import *

__all__ = ['problem_api']

problem_api = Blueprint('problem_api', __name__)


@problem_api.route('/', methods=['GET'])
@login_required
@Request.json('offset', 'count')
def view_problem_list(user, offset, count):
    data = get_problem_list(user.role, offset, count)
    return HTTPResponse(data=data)


@problem_api.route('/<problem_id>', methods=['GET'])
@login_required
def view_problem(user, problem_id):
    problem = Problem(problem_id).obj
    if problem is None:
        return HTTPError('Problem not exist.', 404)
    if user.role == 2 and problem.problem_status == 1:
        return HTTPError('Problem cannot view.', 403)

    data = {
        'owner': problem.owner,
        'description': problem.description,
        #'pdf':
    }
    if problem.problem_type == 1:
        data.update({'fillInTemplate': problem.test_case.fill_in_template})

    return HTTPResponse('Problem can view.', data=data)


@problem_api.route(
    '/manage/<problem_id>', methods=['GET', 'POST', 'PUT', 'DELETE'])
@identity_verify(0, 1)
def manage_problem(user, problem_id):
    @Request.json(
        'status',
        'type',
        'description',
        'tags',
        vars_dict={
            'problem_name': 'problemName',
            'test_case': 'testCase'
        })
    def modify_problem(status, type, problem_name, description, tags,
                       test_case):
        edit_problem(user, problem_id, status, type, problem_name, description,
                     tags, test_case)

    if request.method == 'POST':
        problem = Problem(problem_id).obj
        if problem is not None:
            return HTTPError('Problem exist.', 403)
    else:
        problem = Problem(problem_id).obj
        if problem is None:
            return HTTPError('Problem not exist.', 404)
        if user.role == 1 and problem.owner != user.username:
            return HTTPError('Not the owner.', 403)

    if request.method == 'GET':
        data = {
            'problemName': problem.problem_name,
            'status': problem.problem_status,
            'type': problem.problem_type,
            'description': problem_type.description,
            'tags': problem.tags,
            'testCase': problem.test_case,
            'ACUser': problem.ac_user,
            'submitter': problem.submitter
        }
        return HTTPResponse('Success.', data=data)
    elif request.method == 'DELETE':
        delete_problem(problem_id)
        return HTTPResponse('Success.')
    else:
        modify_problem()
        return HTTPResponse('Success.')
