import os
import requests as rq
import random
import json
import pathlib
from zipfile import ZipFile, is_zipfile
from requests import status_codes
from flask import Blueprint, request
from datetime import datetime, timedelta
from functools import wraps

from mongo import *
from mongo import engine
from .utils import *
from .auth import *

__all__ = ['submission_api']
submission_api = Blueprint('submission_api', __name__)

# submission api config
RATE_LIMIT = int(os.environ.get('SUBMISSION_RATE_LIMIT', 180))
SOURCE_PATH = pathlib.Path(
    os.environ.get('SUBMISSION_SOURCE_PATH', 'submissions'))
SOURCE_PATH.mkdir(exist_ok=True)
TMP_DIR = pathlib.Path(
    os.environ.get('SUBMISSION_TMP_DIR', '/tmp' / SOURCE_PATH))
TMP_DIR.mkdir(exist_ok=True)
JUDGE_URL = os.environ.get('JUDGE_URL', 'http://sandbox:1450/submit')

# TODO: save tokens in db
tokens = {}


def get_token():
    ret = hex(int(str(random.random())[2:]))[2:]
    ret += hex(int(str(random.random())[2:]))[2:]
    return ret[:24]


def assign_token(submission_id, token_pool=tokens):
    '''
    generate a token for the submission
    '''
    token = get_token()
    token_pool[submission_id] = token
    return token


def verify_token(submission_id, token):
    if submission_id not in tokens:
        return False
    return tokens[submission_id] == token


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
@Request.json('language_type', 'problem_id')
def create_submission(user, language_type, problem_id):
    # the user reach the rate limit for submitting
    now = datetime.now()
    delta = timedelta.total_seconds(now - user.last_submit)
    if delta <= RATE_LIMIT:
        return HTTPError(
            'Submit too fast!\n'
            f'Please wait for {RATE_LIMIT - delta:.2f} seconds to submit.',
            429)  # Too many request

    # check for fields
    if language_type is None or problem_id is None:
        return HTTPError(
            f'post data missing!',
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

    # permission check
    # 1. if the problem is in a contest and this user is not a participant
    if user.contest:
        if problem_id not in user.contest.problem_ids:
            return HTTPError(
                f'problem not belong to the contest {user.contest.name} and you are current in it.',
                403,
            )
    # 2. user is not in a contest and the problem belong to a contest
    elif len(problem.course_ids) != 0:
        contest_names = [
            engine.Contest(id=_id).name for _id in problem.contest_ids
        ]
        contest_names = '\n'.join(contest_names)
        return HTTPError(
            f'you are not a particenpate of these contests:\n {contest_names}',
            403,
        )
    # 3. if the user doesn't bolong to the course and the problem does
    course_names = ''
    course_permissions = []
    for course_id in problem.course_ids:
        course = Course(course_id)
        course_permissions.append(perm(course, user))
        course_names += course.name + '\n'
    if any(course_permissions):
        return HTTPError(
            f'You are not a student of these courses: {course_names}',
            403,
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
        return HTTPError(f'invalid data!', 400)
    except engine.DoesNotExist as e:
        return HTTPError(str(e), 404)

    user.update(last_submit=now)
    user.submissions.append(submission)

    # generate token for upload file
    token = assign_token(submission.id)
    return HTTPResponse(
        'submission recieved.\n'
        'please send source code with the given token and submission id.',
        data={
            'submissionId': submission.id,
            'token': token
        },
    )


@submission_api.route('/', methods=['GET'])
@Request.args('offset', 'count', 'problem_id', 'submission_id', 'username',
              'status', 'language_type')
def get_submission_list(offset, count, problem_id, submission_id, username,
                        status, language_type):
    '''
    get the list of submission data
    avaliable filter:
        - submission id
        - problem id
        - timestamp
        - status
        - runtime
        - score
        - memory usage
        - language
    '''
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

    # query all
    submissions = engine.Submission.objects.order_by('-timestamp')

    # filter by user args
    user = User(username)
    q = {
        'problem': Problem(problem_id).obj,
        'id': submission_id,
        'status': status,
        'language': language_type,
        'user': user.obj if user else None
    }
    nk = [k for k, v in q.items() if v is None]
    for k in nk:
        del q[k]
    submissions = submissions.filter(**q)

    # filter by role
    @identity_verify(0, 1, 2)
    def get_user(user) -> User:
        return user

    def can_view_offline(user, submission):
        # everyone can view online submission
        if submission.problem.problem_status == 0:
            return True
        # guest can not view offline problem
        if not isinstance(user, User):
            return False
        # user
        return any(
            perm(Course(id=course_id), user) >= 2
            for course_id in submission.problem.course_ids)

    user = get_user()
    submissions = [
        submission for submission in submissions
        if can_view_offline(user, submission)
    ]

    if offset >= len(submissions):
        return HTTPError(
            f'offset ({offset}) is out of range!',
            400,
        )

    right = min(len(submissions), offset +
                count) if count != -1 else len(submissions)
    submissions = submissions[offset:right]

    usernames = [s.user.username for s in submissions]
    submissions = [Submission(s.id).to_py_obj for s in submissions]

    for s, n in zip(submissions, usernames):
        del s['code']
        del s['cases']

        # replace user field with username
        s['username'] = n
        del s['user']

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
    ret = submission.to_py_obj

    if submission.user.username != user.username:
        # normal user can not view other's source
        if user.role == 2:
            del ret['code']
        # teachers and TAs can view those who in thrie courses
        elif user.role == 1:
            try:
                for course_id in submission.problem.course_ids:
                    course = Course(id=course_id)
                    if perm(course, user) <= 1:
                        del ret['code']
                        break
            except engine.DoesNotExist:
                return HTTPError(
                    f'course {course_id} not found',
                    404,
                )

    return HTTPResponse(data=ret)


@submission_api.route('/<submission_id>', methods=['PUT'])
@login_required
@submission_required
@Request.args('token')
def update_submission(user, submission, token):
    def judgement(zip_path: pathlib.Path):
        '''
        send submission data to sandbox
        '''
        ## prepare submission data
        # prepare problem testcase
        # get testcases
        cases = submission.problem.test_case.cases
        # metadata
        meta = {}
        meta['cases'] = []
        # problem path
        testcase_dir = zip_path.parent / 'testcase'
        testcase_dir.mkdir()
        testcase_zip_path = zip_path.parent / 'testcase.zip'

        with ZipFile(testcase_zip_path, 'w') as zf:
            for i, case in enumerate(cases):
                meta['cases'].append({
                    'caseScore': case['caseScore'],
                    'memoryLimit': case['memoryLimit'],
                    'timeLimit': case['timeLimit']
                })

                task_dir = testcase_dir / str(i)
                task_dir.mkdir()

                with open(task_dir / 'in', 'w') as f:
                    f.write(case['input'])
                with open(task_dir / 'out', 'w') as f:
                    f.write(case['output'])

                zf.write(task_dir / 'in', f'{i}/in')
                zf.write(task_dir / 'out', f'{i}/out')

            with open(testcase_dir / 'meta.json', 'w') as f:
                json.dump(meta, f)
            zf.write(testcase_dir / 'meta.json', 'meta.json')

        # generate token for submission
        token = assign_token(submission.id)
        # setup post body
        post_data = {
            'languageId': submission.language,
            'token': token,
            'checker': 'print("not implement yet. qaq")',
        }
        files = {
            'code': (
                f'{submission.id}-source.zip',
                open(zip_path, 'rb'),
            ),
            'testcase': (
                f'{submission.id}-testcase.zip',
                open(testcase_zip_path, 'rb'),
            ),
        }

        judge_url = f'{JUDGE_URL}/{submission.id}'

        # send submission to snadbox for judgement
        resp = rq.post(
            judge_url, data=post_data, files=files,
            cookies=request.cookies)  # cookie: for debug, need better solution

        if resp.status_code == 400:
            return HTTPError(
                resp.text,
                400,
            )
        if resp.status_code != 200:
            # unhandled error
            return HTTPError(
                resp.text,
                500,
            )
        return HTTPResponse(f'{submission} recieved.')

    @Request.files('code')
    def recieve_source_file(code):
        # if source code found
        if code is not None:
            if submission.code:
                return HTTPError(
                    f'{submission} has been uploaded source file!',
                    403,
                )
            else:
                # save submission source
                submission_dir = SOURCE_PATH / submission.id
                if submission_dir.is_dir():
                    raise FileExistsError(f'{submission} code found on server')

                # create submission folder
                submission_dir.mkdir()
                # tmp file to store zipfile
                zip_path = TMP_DIR / submission.id / 'source.zip'
                zip_path.parent.mkdir()
                zip_path.write_bytes(code.read())
                if not is_zipfile(zip_path):
                    zip_path.unlink()
                    return HTTPError(
                        'only accept zip file',
                        400,
                    )
                with ZipFile(zip_path, 'r') as f:
                    f.extractall(submission_dir)
                submission.update(code=True, status=-1)

                return judgement(zip_path)
        else:
            return HTTPError(
                f'can not find the source file',
                400,
            )

    @Request.json('score', 'status', 'cases')
    def recieve_submission_result(score, status, cases):
        try:
            for case in cases:
                del case['exitCode']
            submission.update(
                status=status,
                cases=cases,
                exec_time=cases[-1]['execTime'],
                memory_usage=cases[-1]['memoryUsage'],
            )
        except ValidationError:
            return HTTPError(
                f'invalid data!',
                400,
            )
        return HTTPResponse(f'{submission} result recieved.')

    ## put handler
    # validate this reques
    if submission.status >= 0:
        return HTTPError(
            f'{submission} has finished judgement.',
            403,
        )

    if verify_token(submission.id, token) == False:
        return HTTPError(
            f'invalid token.',
            403,
            data={
                'excepted': tokens[submission.id],
                'got': token
            },
        )

    # if user not equal, reject
    if user.user_id != submission.user.user_id:
        err_msg = \
        '!!!!Warning!!!!\n'
        f'The user {user} (id: {user.user_id}) is trying to '
        f'submit data to {submission}, '
        f'which shold belong to {submission.user.username} (id: {submission.user.user_id})'
        return HTTPError(
            err_msg,
            403,
            data={
                'excepted': {
                    'username': submission.user.username,
                    'userId': submission.user.user_id,
                },
                'received': {
                    'username': submission.user.username,
                    'userId': submission.user.user_id,
                }
            },
        )

    if request.content_type == 'application/json':
        return recieve_submission_result()
    elif request.content_type.startswith('multipart/form-data'):
        return recieve_source_file()
    else:
        return HTTPError(
            f'Unaccepted Content-Type {request.content_type}',
            415,
        )
