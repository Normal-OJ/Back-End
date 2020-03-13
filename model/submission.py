import os
import io
import requests as rq
import random
import json
import pathlib
import string
import secrets
from flask import Blueprint, request, send_file, current_app
from datetime import datetime, timedelta
from functools import wraps
from zipfile import ZipFile

from mongo import *
from mongo import engine
from .utils import *
from .auth import *

__all__ = ['submission_api']
submission_api = Blueprint('submission_api', __name__)


def submission_required(func):
    '''
    get submission via route param "submission_id"
    '''
    @wraps(func)
    def wrapper(*args, **ks):
        submission = Submission(request.view_args.get('submission_id'))
        if not submission:
            return HTTPError(
                f'{submission} not exist',
                404,
            )
        del ks['submission_id']
        ks.update({'submission': submission})
        return func(*args, **ks)

    return wrapper


@submission_api.route('/', methods=['POST'])
@login_required
@Request.json('language_type: int', 'problem_id: int')
def create_submission(user, language_type, problem_id):
    # the user reach the rate limit for submitting
    now = datetime.now()
    delta = timedelta.total_seconds(now - user.last_submit)
    if delta <= Submission.config.rate_limit:
        wait_for = Submission.config.rate_limit - delta
        return HTTPError(
            'Submit too fast!\n'
            f'Please wait for {wait_for:.2f} seconds to submit.',
            429,
            data={
                'waitFor': wait_for,
            },
        )  # Too many request
    # check for fields
    if problem_id is None:
        return HTTPError(
            'problemId is required!',
            400,
        )
    # search for problem
    current_app.logger.debug(f'got problem id {problem_id}')
    problem = Problem(problem_id)
    if problem.obj is None:
        return HTTPError('Unexisted problem id.', 404)
    # problem permissoion
    if not can_view(user, problem.obj):
        return HTTPError('problem permission denied!', 403)
    # check deadline
    for homework in problem.obj.homeworks:
        if now > homework.duration.end:
            return HTTPError('this homework is overdue', 403)
    # handwritten problem doesn't need language type
    if language_type is None:
        if problem.problem_type != 2:
            return HTTPError(
                'post data missing!',
                400,
                data={
                    'languageType': language_type,
                    'problemId': problem_id
                },
            )
        language_type = 3
    # not allowed language
    if not problem.allowed(language_type):
        return HTTPError(
            'not allowed language',
            403,
            data={
                'allowed': problem.obj.allowed_language,
                'got': language_type
            },
        )
    # insert submission to DB
    try:
        submission = Submission.add(
            problem_id=problem_id,
            username=user.username,
            lang=language_type,
            timestamp=now,
        )
    except ValidationError:
        return HTTPError('invalid data!', 400)
    except engine.DoesNotExist as e:
        return HTTPError(str(e), 404)
    # update user
    user.update(
        last_submit=now,
        push__submissions=submission.obj,
    )
    # update problem
    submission.problem.update(inc__submitter=1)
    return HTTPResponse(
        'submission recieved.\n'
        'please send source code with given submission id later.',
        data={
            'submissionId': submission.id,
        },
    )


@submission_api.route('/', methods=['GET'])
@login_required
@Request.args('offset', 'count', 'problem_id', 'submission_id', 'username',
              'status', 'language_type', 'course')
def get_submission_list(user, offset, count, problem_id, submission_id,
                        username, status, language_type, course):
    '''
    get the list of submission data
    avaliable filter:
        - submission id
        - problem id
        - timestamp
        - status
        - runtime
        - score
        - language
        - course
    '''
    try:
        submissions = Submission.filter(user=user,
                                        offset=offset,
                                        count=count,
                                        problem=problem_id,
                                        submission=submission_id,
                                        q_user=username,
                                        status=status,
                                        language_type=language_type,
                                        course=course)
    except ValueError as e:
        return HTTPError(str(e), 400)
    submissions = [Submission(s.id).to_dict() for s in submissions]
    # no need to display code and task results in list
    for s in submissions:
        del s['code']
        del s['tasks']
    # unicorn gifs
    unicorns = [
        'https://media.giphy.com/media/xTiTnLmaxrlBHxsMMg/giphy.gif',
        'https://media.giphy.com/media/26AHG5KGFxSkUWw1i/giphy.gif',
        'https://media.giphy.com/media/g6i1lEax9Pa24/giphy.gif',
        'https://media.giphy.com/media/tTyTbFF9uEbPW/giphy.gif'
    ]
    ret = {
        'unicorn': random.choice(unicorns),
        'submissions': submissions,
    }
    return HTTPResponse(
        'here you are, bro',
        data=ret,
    )


@submission_api.route('/<submission_id>', methods=['GET'])
@login_required
@submission_required
def get_submission(user, submission):
    ret = submission.to_dict()
    # can not view the problem, also the submission
    # and handwritten submission doesn't have source code
    if not can_view(user, submission.problem) or submission.handwritten:
        del ret['code']
    # you can view self submission
    elif user.username != submission.user.username:
        # TA and teacher can view students' submissions
        permissions = []
        for course in submission.problem.courses:
            permissions.append(perm(course, user) >= 2)
        if not any(permissions):
            del ret['code']
    # check user's stdout/stderr
    if not submission.problem.can_view_stdout:
        for task in ret['tasks']:
            for case in task['cases']:
                del case['output']
    else:
        for task in ret['tasks']:
            for case in task['cases']:
                output = GridFSProxy(case.pop('output'))
                with ZipFile(output) as zf:
                    case['stdout'] = zf.read('stdout').decode('utf-8')
                    case['stderr'] = zf.read('stderr').decode('utf-8')
    # give user source code
    if 'code' in ret:
        ext = ['.c', '.cpp', '.py'][submission.language]
        ret['code'] = submission.get_code(f'main{ext}')
    return HTTPResponse(data=ret)


@submission_api.route('/<submission_id>/pdf/<item>', methods=['GET'])
@login_required
@submission_required
def get_submission_pdf(user, submission, item):
    ret = submission.to_dict()
    # can not view the problem, also the submission
    if not can_view(user, submission.problem):
        return HTTPError('forbidden.', 403)
    # you can view self submission
    elif user.username != submission.user.username:
        # TA and teacher can view students' submissions
        permissions = []
        for course in submission.problem.courses:
            permissions.append(perm(course, user) >= 2)
        if not any(permissions):
            return HTTPError('forbidden.', 403)
    if not submission.handwritten:
        return HTTPError('it is not a handwritten submission.', 400)

    if item not in ['comment', 'upload']:
        return HTTPError('/<submission_id>/pdf/<"upload" or "comment">', 400)

    try:
        data = submission.get_comment(
        ) if item == 'comment' else submission.get_code(f'main.pdf', True)
    except FileNotFoundError as e:
        return HTTPError('File not found.', 404)
    return send_file(
        io.BytesIO(data),
        mimetype='application/pdf',
        as_attachment=True,
        attachment_filename=f'{item}-{submission.id[:6]}.pdf',
    )


@submission_api.route('/count', methods=['GET'])
@login_required
@Request.args('problem_id', 'submission_id', 'username', 'status',
              'language_type', 'course')
def get_submission_count(user, problem_id, submission_id, username, status,
                         language_type, course):
    try:
        submissions = Submission.filter(
            user=user,
            offset=0,
            count=-1,
            problem=problem_id,
            submission=submission_id,
            q_user=username,
            status=status,
            language_type=language_type,
            course=course,
        )
    except ValueError as e:
        return HTTPError(str(e), 400)
    return HTTPResponse('Padoru~', data={'count': len(submissions)})


@submission_api.route('/<submission_id>/complete', methods=['PUT'])
@Request.json('tasks: list', 'token: str')
@submission_required
def on_submission_complete(submission, tasks, token):
    if not verify_token(submission.id, token):
        return HTTPError('i don\'t know you', 403)
    try:
        submission.process_result(tasks)
    except (ValidationError, KeyError) as e:
        return HTTPError(
            'invalid data!\n'
            f'{type(e).__name__}: {e}',
            400,
        )
    return HTTPResponse(f'{submission} result recieved.')


@submission_api.route('/<submission_id>', methods=['PUT'])
@login_required
@submission_required
@Request.files('code')
def update_submission(user, submission, code):
    # put handler
    # validate this reques
    if submission.status >= 0:
        return HTTPError(
            f'{submission} has finished judgement.',
            403,
        )
    # if user not equal, reject
    if not secrets.compare_digest(submission.user.username, user.username):
        return HTTPError('user not equal!', 403)
    # if source code not found
    if code is None:
        return HTTPError(
            f'can not find the source file',
            400,
        )
    # or empty file
    if len(code.read()) == 0:
        return HTTPError('empty file', 400)
    code.seek(0)
    # has been uploaded
    if submission.code:
        return HTTPError(
            f'{submission} has been uploaded source file!',
            403,
        )
    try:
        success = submission.submit(code)
    except FileExistsError:
        exit(10086)
    except ValueError as e:
        return HTTPError(str(e), 400)
    except JudgeQueueFullError as e:
        return HTTPResponse(str(e), 202)
    except ValidationError as e:
        return HTTPError(str(e), data=e.to_dict())
    if success:
        return HTTPResponse(
            f'{submission} {"is finished." if submission.handwritten else "send to judgement."}'
        )
    else:
        return HTTPError('Some error occurred, please contact the admin', 500)


@submission_api.route('/<submission_id>/grade', methods=['PUT'])
@Request.json('score')
@submission_required
@identity_verify(0, 1)
def grade_submission(user, submission, score):
    submission.update(score=score)
    return HTTPResponse(f'{submission} score recieved.')


@submission_api.route('/<submission_id>/comment', methods=['PUT'])
@Request.files('comment')
@submission_required
def comment_submission(submission, comment):
    if comment is None:
        return HTTPError(
            f'can not find the comment',
            400,
        )
    try:
        submission.comment(comment)
    except ValueError as e:
        return HTTPError(str(e), 400)
    return HTTPResponse(f'{submission} comment recieved.')


@submission_api.route('/<submission_id>/rejudge', methods=['GET'])
@login_required
@submission_required
def rejudge(user, submission):
    if submission.status < 0:
        return HTTPError(f'{submission} haven\'t be judged', 403)
    submission.rejudge()
    return HTTPResponse('success.')


@submission_api.route('/config', methods=['GET', 'PUT'])
@login_required
@identity_verify(0)
def config(user):
    config = Submission.config

    def get_config():
        return HTTPResponse('success.', data={
            'rateLimit': config.rate_limit,
            'sandboxInstances': [{
                'name': sandbox.name,
                'url': sandbox.url,
                'token': sandbox.token,
            }for sandbox in config.sandbox_instances]
        })

    @Request.json('rate_limit: int', 'sandbox_instances: list')
    def modify_config(rate_limit, sandbox_instances):
        try:
            config.update(rate_limit=rate_limit,
                          sandbox_instances=sandbox_instances)
            config.reload()
        except ValidationError as e:
            return HTTPError(str(e), 400)

        return HTTPResponse('success.'+str(engine.SubmissionConfig.objects))

    methods = {'GET': get_config, 'PUT': modify_config}
    return methods[request.method]()
