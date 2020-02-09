import os
import requests as rq
import random
import json
import pathlib
import string
import secrets
from flask import Blueprint, request
from datetime import datetime, timedelta
from functools import wraps
from flask import current_app

from mongo import *
from mongo import engine
from .utils import *
from .auth import *
from .submission_config import SubmissionConfig

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
@Request.json('language_type: int', 'problem_id')
def create_submission(user, language_type, problem_id):
    # the user reach the rate limit for submitting
    now = datetime.now()
    delta = timedelta.total_seconds(now - user.last_submit)
    if delta <= SubmissionConfig.RATE_LIMIT:
        return HTTPError(
            'Submit too fast!\n'
            f'Please wait for {SubmissionConfig.RATE_LIMIT - delta:.2f} seconds to submit.',
            429)  # Too many request

    # check for fields
    if any([language_type is None, problem_id is None]):
        return HTTPError(
            'post data missing!',
            400,
            data={
                'languageType': language_type,
                'problemId': problem_id
            },
        )

    # search for problem
    problem = Problem(problem_id).obj
    if problem is None:
        return HTTPError('Unexisted problem id', 404)

    if not can_view(user, problem):
        return HTTPError('problem permission denied!', 403)

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

    user.update(last_submit=now)
    user.submissions.append(submission.obj)
    user.save()
    # update problem
    submission.problem.submitter += 1
    submission.problem.save()

    return HTTPResponse(
        'submission recieved.\n'
        'please send source code with given submission id later.',
        data={
            'submissionId': submission.id,
        },
    )


@submission_api.route('/', methods=['GET'])
@login_required
@Request.args(
    'offset',
    'count',
    'problem_id',
    'submission_id',
    'username',
    'status',
    'language_type',
)
def get_submission_list(
    user,
    offset,
    count,
    problem_id,
    submission_id,
    username,
    status,
    language_type,
):
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
    '''
    try:
        submissions = Submission.filter(
            user=user,
            offset=offset,
            count=count,
            problem=problem_id,
            submission=submission_id,
            q_user=username,
            status=status,
            language_type=language_type,
        )
    except ValueError as e:
        return HTTPError(str(e), 400)

    submissions = [Submission(s.id).to_dict() for s in submissions]

    for s in submissions:
        del s['code']
        del s['tasks']

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
    if not can_view(user, submission.problem):
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
            del case['stdout']
            del case['stderr']

    # give user source code
    if 'code' in ret:
        ext = ['.c', '.cpp', '.py']
        ret['code'] = submission.get_code(f'main{ext[submission.language]}')

    return HTTPResponse(data=ret)


@submission_api.route('/count', methods=['GET'])
@login_required
@Request.args(
    'problem_id',
    'submission_id',
    'username',
    'status',
    'language_type',
)
def get_submission_count(
    user,
    problem_id,
    submission_id,
    username,
    status,
    language_type,
):
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
        )
    except ValueError as e:
        return HTTPError(str(e), 400)
    return HTTPResponse('Padoru~', data={'count': len(submissions)})


@submission_api.route('/<submission_id>/complete', methods=['PUT'])
@Request.json('tasks: dict', 'token: str')
@submission_required
def on_submission_complete(submission, tasks, token):
    if not secrets.compare_digest(token, SubmissionConfig.SANDBOX_TOKEN):
        return HTTPError('you are not sandbox :(', 403)
    try:
        submission.process_result(tasks)
    except (ValidationError, KeyError) as e:
        return HTTPError(f'invalid data!\n{e}', 400)
    return HTTPResponse(f'{submission} result recieved.')


@submission_api.route('/<submission_id>', methods=['PUT'])
@login_required
@submission_required
def update_submission(user, submission):
    @Request.files('code')
    def recieve_source_file(code):
        # if source code not found
        if code is None:
            return HTTPError(
                f'can not find the source file',
                400,
            )

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
        return HTTPResponse(f'{submission} send to judgement.')

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

    return recieve_source_file()
