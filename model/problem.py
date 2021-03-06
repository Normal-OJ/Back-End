from flask import Blueprint, request, send_file
from urllib import parse
from zipfile import BadZipFile
from mongo import *
from mongo import engine
from .auth import *
from .utils import *
from mongo.utils import can_view_problem
from mongo.problem import *
import threading

__all__ = ['problem_api']

problem_api = Blueprint('problem_api', __name__)
lock = threading.Lock()


@problem_api.route('/', methods=['GET'])
@login_required
@Request.args(
    'offset',
    'count',
    'problem_id',
    'tags',
    'name',
    'course',
)
def view_problem_list(
    user,
    offset,
    count,
    tags,
    problem_id,
    name,
    course,
):
    # casting args
    try:
        if offset is not None:
            offset = int(offset)
        if count is not None:
            count = int(count)
    except (TypeError, ValueError):
        return HTTPError(
            'offset and count must be integer!',
            400,
        )
    problem_id, name, tags, course = (parse.unquote(p or '') or None
                                      for p in (problem_id, name, tags,
                                                course))
    try:
        ks = {
            'user': user,
            'offset': offset,
            'count': count,
            'tags': tags and tags.split(','),
            'problem_id': problem_id,
            'name': name,
            'course': course,
        }
        ks = {k: v for k, v in ks.items() if v is not None}
        data = get_problem_list(**ks)
    except IndexError:
        return HTTPError('invalid offset', 400)
    data = [{
        'problemId': p.problem_id,
        'problemName': p.problem_name,
        'status': p.problem_status,
        'ACUser': p.ac_user,
        'submitter': p.submitter,
        'tags': p.tags,
        'type': p.problem_type,
        'quota': p.quota,
        'submitCount': Problem(p.problem_id).submit_count(user)
    } for p in data]
    return HTTPResponse('Success.', data=data)


@problem_api.route('/view/<int:problem_id>', methods=['GET'])
@login_required
def view_problem(user, problem_id):
    problem = Problem(problem_id)
    if not problem:
        return HTTPError('Problem not exist.', 404)
    if not can_view_problem(user, problem.obj):
        return HTTPError('Problem cannot view.', 403)
    # filter data
    data = problem.detailed_info(
        'problemName',
        'description',
        'owner',
        'tags',
        'allowedLanguage',
        'courses',
        'quota',
        status='problemStatus',
        type='problemType',
        testCase='testCase__tasks',
    )
    if problem.obj.problem_type == 1:
        data.update({'fillInTemplate': problem.obj.test_case.fill_in_template})
    data.update({'submitCount': problem.submit_count(user)})
    return HTTPResponse('Problem can view.', data=data)


@problem_api.route('/manage', methods=['POST'])
@problem_api.route('/manage/<int:problem_id>',
                   methods=['GET', 'PUT', 'DELETE'])
@identity_verify(0, 1)
def manage_problem(user, problem_id=None):
    @Request.json('type', 'courses: list', 'status', 'type', 'description',
                  'tags', 'problem_name', 'quota')
    def modify_problem(**p_ks):
        if p_ks['type'] == 2:
            return modify_general_problem(**p_ks)
        else:
            return modify_coding_problem(**p_ks)

    @Request.json(
        'test_case_info',
        'can_view_stdout',
        'allowed_language',
    )
    def modify_coding_problem(**p_ks):
        scores = (c['taskScore'] for c in p_ks['test_case_info']['tasks'])
        if sum(scores) != 100:
            return HTTPError("Cases' scores should be 100 in total", 400)
        return modify_general_problem(**p_ks)

    def modify_general_problem(**p_ks):
        if request.method == 'POST':
            with lock as _:
                pid = add_problem(user=user, **p_ks)
            return HTTPResponse('Success.', data={'problemId': pid})
        elif request.method == 'PUT':
            edit_problem(
                user=user,
                problem_id=problem_id,
                **p_ks,
            )
            return HTTPResponse('Success.')

    @Request.files('case')
    def modify_problem_test_case(case):
        try:
            result = edit_problem_test_case(problem_id, case)
        except engine.DoesNotExist as e:
            return HTTPError(str(e), 404)
        except (ValueError, BadZipFile) as e:
            return HTTPError(str(e), 400)
        except BadTestCase as e:
            return HTTPError(str(e), 400, data=e.dict)
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
        problem = Problem(problem_id)
        info = problem.detailed_info(
            'courses',
            'problemName',
            'description',
            'tags',
            'testCase',
            'ACUser',
            'submitter',
            'allowedLanguage',
            'canViewStdout',
            'quota',
            status='problemStatus',
            type='problemType',
        )
        info.update({'submitCount': problem.submit_count(user)})
        return HTTPResponse(
            'Success.',
            data=info,
        )
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
            return HTTPError(
                'Invalid or missing arguments.',
                400,
                data=ve.to_dict(),
            )
        except engine.DoesNotExist:
            return HTTPError('Course not found.', 404)


@problem_api.route('/<int:problem_id>/testcase', methods=['GET'])
@login_required
@identity_verify(0, 1)
def get_testcase(user, problem_id):
    problem = Problem(problem_id).obj
    if problem is None:
        return HTTPError(f'Unexisted problem id ({problem_id})', 404)
    return send_file(
        problem.test_case.case_zip,
        mimetype='application/zip',
        as_attachment=True,
        attachment_filename=f'testdata-{problem_id}.zip',
    )


@problem_api.route('/<int:problem_id>/high-score', methods=['GET'])
@login_required
def high_score(user, problem_id):
    problem = Problem(problem_id).obj
    if problem is None:
        return HTTPError('problem not exists', 404)
    return HTTPResponse(
        'Mya nee, 10 hrs ver.\n'
        'https://www.youtube.com/watch?v=K7s2BuuPKgg',
        data={
            'score': problem.high_scores.get(
                user.username,
                0,
            ),
        },
    )


@problem_api.route('/clone', methods=['POST'])
@identity_verify(0, 1)
@Request.json(vars_dict={'problem_id': 'problemId'})
def clone_problem(user, problem_id):
    problem = Problem(problem_id).obj
    if problem is None:
        return HTTPError('Problem not exist.', 404)
    if not can_view_problem(user, problem):
        return HTTPError('Problem can not view.', 403)
    with lock as _:
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
