import os
import requests as rq
import random
import json
from zipfile import ZipFile, is_zipfile
from requests import status_codes
from flask import Blueprint, request
from datetime import datetime, timedelta

from mongo import *
from mongo import engine
from .utils import *
from .auth import *

__all__ = ['submission_api']
submission_api = Blueprint('submission_api', __name__)

# submission api config
RATE_LIMIT = int(os.environ.get('SUBMISSION_RATE_LIMIT', 180))
SOURCE_PATH = os.environ.get('SUBMISSION_SOURCE_PATH', 'submissions')
os.makedirs(SOURCE_PATH, exist_ok=True)
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
            f'Please wait for {RATE_LIMIT - delta} seconds to submit.',
            429)  # Too many request

    # check user permission
    # 1. if the problem is in a contest and this user is not a participant
    # 2. user is in a contest and the problem doesn't belong to that contest
    # 3. if the user doesn't bolong to the course and the problem does

    if language_type is None or problem_id is None:
        return HTTPError(f'post data missing!',
                         400,
                         data={
                             'languageType': language_type,
                             'problemId': problem_id
                         })

    # insert submission to DB
    try:
        submission_id = Submission.add(
            problem_id=problem_id,
            user=engine.User.objects.get(username=user.username),
            lang=language_type,
            timestamp=now)
    except ValidationError:
        return HTTPError(f'invalid data!', 404)

    user.update(last_submit=datetime.now())

    # generate token for upload file
    token = assign_token(submission_id)
    return HTTPResponse(
        'submission recieved.\n'
        'please send source code with the given token and submission id.',
        data={
            'submissionId': submission_id,
            'token': token
        })


@submission_api.route('/', methods=['GET'])
@Request.args('offset', 'count', 'problem_id', 'submission_id', 'username',
              'status', 'language_type')
def get_submission_list(offset, count, problem_id, submission_id, username,
                        status, language_type):
    '''
    get the list of submission data
    include:
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
        return HTTPError('offset and count are required!', 400)

    # casting args
    try:
        offset = int(offset)
        count = int(count)
    except ValueError:
        return HTTPError('offset and count must be integer!', 400)

    # check range
    if offset < 0:
        return HTTPError('offset must >= 0!', 400)
    if count < -1:
        return HTTPError('count must >=-1!', 400)

    # query all
    submissions = engine.Submission.objects.order_by('-timestamp')

    # filter by role
    @identity_verify(0, 1)
    def view_offline_problem_submissions():
        '''
        teachers and admin can view offline problems
        '''
        return True

    def truncate_offline_problem_submissions(submissions):
        pass

    view_offline_problem_submissions() != True or \
        truncate_offline_problem_submissions(submissions)

    # filter by user args
    user = User(username)
    q = {
        'problem_id': problem_id,
        'id': submission_id,
        'status': status,
        'language': language_type,
        'user': user.obj if user else None
    }
    nk = [k for k, v in q.items() if v is None]
    for k in nk:
        del q[k]
    submissions = submissions.filter(**q)

    if offset >= len(submissions):
        return HTTPError(f'offset ({offset}) is out of range!', 400)

    right = min(len(submissions), offset +
                count) if count != -1 else len(submissions)
    submissions = submissions[offset:right]

    usernames = [*map(lambda s: s.user.username, submissions)]
    submissions = submissions.to_json()
    submissions = json.loads(submissions)

    for s, n in zip(submissions, usernames):
        del s['code']
        del s['cases']

        # replace user field with username
        s['username'] = n
        del s['user']

        s['timestamp'] = s['timestamp']['$date']

        s['submissionId'] = s['_id']['$oid']
        del s['_id']

        # field name convertion
        curr = ['memory_usage', 'exec_time', 'problem_id', 'language']
        want = ['memoryUsage', 'runTime', 'problemId', 'languageType']
        for c, w in zip(curr, want):
            s[w] = s[c]
            del s[c]

    unicorns = [
        'https://media.giphy.com/media/xTiTnLmaxrlBHxsMMg/giphy.gif',
        'https://media.giphy.com/media/26AHG5KGFxSkUWw1i/giphy.gif',
        'https://media.giphy.com/media/g6i1lEax9Pa24/giphy.gif',
        'https://media.giphy.com/media/tTyTbFF9uEbPW/giphy.gif'
    ]

    ret = {'unicorn': random.choice(unicorns), 'submissions': submissions}

    return HTTPResponse('here you are, bro', data=ret)


@submission_api.route('/<submission_id>', methods=['GET'])
@login_required
def get_submission(user, submission_id):
    submission = Submission(submission_id)
    if not submission.exist:
        return HTTPError(f'{submission} not found!', 404)

    ret = submission.to_json()
    ret = json.loads(ret)

    if submission.user.username != user.username:
        # normal user can not view other's source
        if user.role == 2:
            del ret['code']
        # TODO: teachers and TAs can view those who in thrie courses
        elif user.role == 1:
            pass

    return HTTPResponse(data=ret)


@submission_api.route('/<submission_id>', methods=['PUT'])
@login_required
@Request.args('token')
def update_submission(user, submission_id, token):
    def judgement(submission):
        '''
        send submission data to sandbox
        '''
        # prepare submission data
        # TODO: get problem testcase
        judge_url = 'localhost:8888/submit'

        # generate token for submission
        token = assign_token(submission_id)

        post_data = {
            'lang': submission.language,
            'submission_id': submission_id,
            'token': token
        }

        # send submission to snadbox for judgement
        # TODO: send submission to sanbox
        # resp = rq.post(judge_url, data=post_data)
        resp = rq.get('https://www.csie.ntnu.edu.tw')

        if resp.status_code == 400:
            return HTTPError('', 400)
        elif resp.status_code != 200:
            # unhandled error
            return HTTPError('', 500)
        else:
            return HTTPResponse('submission recieved.')

    @Request.files('code')
    def recieve_source_file(submission, code):
        # if source code found
        if code is not None:
            if submission.code:
                return HTTPError(
                    f'{submission} has been uploaded source file!', 403)
            else:
                # save submission source
                submission_path = f'{SOURCE_PATH}/{submission_id}'
                if os.path.isdir(submission_path):
                    raise FileExistsError(f'{submission} code found on server')

                # create submission folder
                os.mkdir(submission_path)
                # tmp file to store zipfile
                zip_path = f'/tmp/submission/{submission_id}/source.zip'
                os.makedirs(os.path.dirname(zip_path))
                with open(zip_path, 'wb') as f:
                    f.write(code.read())
                if not is_zipfile(zip_path):
                    os.remove(zip_path)
                    return HTTPError('only accept zip file', 400)
                with ZipFile(zip_path, 'r') as f:
                    f.extractall(submission_path)
                os.remove(zip_path)
                submission.update(code=True, status=-1)

                return judgement(submission)
        else:
            return HTTPError(f'can not find the source file', 400)

    @Request.json('score', 'status', 'cases')
    def recieve_submission_result(submission, score, status, cases):
        try:
            submission.update(status=status,
                              cases=cases,
                              exec_time=cases[-1]['execTime'],
                              memory_usage=cases[-1]['memoryUsage'])
        except ValidationError:
            return HTTPError(f'invalid data!', 400)
        return HTTPResponse(f'submission [{submission_id}] result recieved.')

    ## put handler
    # validate this reques
    submission = Submission(submission_id)

    if not submission.exist:
        return HTTPError(f'{submission} not found!', 404)

    if submission.status >= 0:
        return HTTPError(
            f'submission [{submission.id}] has finished judgement.', 403)

    if verify_token(submission_id, token) == False:
        return HTTPError(f'invalid token.',
                         403,
                         data={
                             'excepted': tokens[submission_id],
                             'got': token
                         })

    # if user not equal, reject
    if user.user_id != submission.user.user_id:
        err_msg = \
        '!!!!Warning!!!!\n'
        f'The user {user} (id: {user.user_id}) is trying to '
        f'submit data to {submission}, '
        f'which shold belong to {submission.user.username} (id: {submission.user.user_id})'
        return HTTPError(err_msg,
                         403,
                         data={
                             'excepted': {
                                 'username': submission.user.username,
                                 'userId': submission.user.user_id
                             },
                             'received': {
                                 'username': submission.user.username,
                                 'userId': submission.user.user_id
                             }
                         })

    if request.content_type == 'application/json':
        return recieve_submission_result(submission)
    elif request.content_type.startswith('multipart/form-data'):
        return recieve_source_file(submission)
    else:
        return HTTPError(f'Unaccepted Content-Type {request.content_type}',
                         415)
