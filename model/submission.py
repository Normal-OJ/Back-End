import os
import requests as rq
import random
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
    submission_id = Submission.add(
        problem_id=problem_id,
        user=engine.User.objects.get(username=user.username),
        lang=language_type,
        timestamp=now)

    # generate token for upload file
    token = assign_token(submission_id)
    return HTTPResponse(
        'submission recieved.\nplease send source code with the given token and submission id.',
        data={
            'submissionId': submission_id,
            'token': token
        })


@submission_api.route('/<submission_id>', methods=['GET'])
@Request.cookies('jwt')
def submission_entry(jwt, submission_id):
    ret = Submission(submission_id).to_mongo()

    # guest
    if jwt is None:
        del ret['code']
    else:
        # get the username who send request
        username = jwt_decode(jwt)['data']['username']
        submission = Submission(submission_id)

        # if view other submission
        if submission.user.username != username:
            del ret['code']

    return HTTPResponse(data=ret)


@submission_api.route('/<submission_id>', methods=['PUT'])
@login_required
@Request.args('token')
def update_submission(user, submission_id, token):
    def judgement():
        '''
        send submission data to sandbox
        '''
        # prepare submission data
        # TODO: get problem testcase
        judge_url = 'localhost:8888/submit'

        # generate token for submission
        token = assign_token(submission_id)

        post_data = {
            'lang': Submission(submission_id).language,
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
    def recieve_source_file(code):
        submission = Submission(submission_id)

        # if source code found
        if code is not None:
            if submission.code:
                return HTTPError(
                    f'{submission} has been uploaded source file!', 403)
            else:
                # save submission source
                print(f'SOURCE: {SOURCE_PATH}')
                submission_path = f'{SOURCE_PATH}/{submission_id}'
                if os.path.isdir(submission_path):
                    raise FileExistsError(f'{submission} code found on server')

                # create submission folder
                os.mkdir(submission_path)
                # tmp file to store zipfile
                tmp_path = f'/tmp/submission/{submission_id}/source.zip'
                os.makedirs(os.path.dirname(tmp_path))
                with open(tmp_path, 'wb') as f:
                    f.write(code.read())
                with ZipFile(tmp_path, 'r') as f:
                    if not is_zipfile(tmp_path):
                        return HTTPError('only accept zip file', 400)
                    f.extractall(submission_path)
                os.remove(tmp_path)
                submission.update(code=True)

                return judgement()
        else:
            return HTTPError(f'can not find the source file\n', 400)

    @Request.json('score', 'problem_status', 'cases')
    def recieve_submission_result(score, problem_status, cases):
        submission = Submission(submission_id).update(
            status=problem_status,
            cases=cases,
            exec_time=cases[-1]['execTime'],
            memory_usage=cases[-1]['memoryUsage'])
        if submission is None:
            HTTPError(
                f'Trying to update an unexisted submission [{submission_id}]',
                404)
        return HTTPResponse(f'submission [{submission_id}] result recieved.')

    ## put handler
    # validate this reques
    submission = Submission(submission_id)

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
        f'submit data to submission [{submission_id}], '
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
        return recieve_submission_result()
    elif request.content_type.startswith('multipart/form-data'):
        return recieve_source_file()
    else:
        return HTTPError(f'Unaccepted Content-Type {request.content_type}',
                         415)
