import io
import requests as rq
import random
import secrets
import json
from flask import (
    Blueprint,
    send_file,
    request,
    current_app,
)
from datetime import datetime, timedelta
from functools import wraps
from mongo import *
from mongo import engine
from mongo.utils import can_view_problem, RedisCache
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
    if delta <= Submission.config().rate_limit:
        wait_for = Submission.config().rate_limit - delta
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
    if not can_view_problem(user, problem.obj):
        return HTTPError('problem permission denied!', 403)
    # check deadline
    for homework in problem.obj.homeworks:
        if now < homework.duration.start:
            return HTTPError('this homework hasn\'t start.', 403)
    # ip validation
    if not problem.is_valid_ip(get_ip()):
        return HTTPError('Invalid IP address.', 403)
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
    # check if the user has used all his quota
    if problem.obj.quota != -1 and max(
            perm(course, user)
            for course in problem.obj.courses) < 2 and problem.submit_count(
                user) >= problem.obj.quota:
        return HTTPError('you have used all your quotas', 403)
    user.problem_submission[str(problem_id)] = problem.submit_count(user) + 1
    user.save()
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
    except TestCaseNotFound as e:
        return HTTPError(str(e), 403)
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
    cache_key = f'submissions_{user}_{problem_id}_{submission_id}_{username}_{status}_{language_type}_{course}'
    cache = RedisCache()
    try:
        # convert args
        if offset is None or count is None:
            raise ValueError('offset and count are required!')
        try:
            offset = int(offset)
            count = int(count)
        except ValueError:
            raise ValueError('offset and count must be integer!')
        if offset < 0:
            raise ValueError(f'offset must >= 0! get {offset}')
        if count < -1:
            raise ValueError(f'count must >=-1! get {count}')

        # check cache
        if cache.exists(cache_key):
            submissions = json.loads(cache.get(cache_key))
        else:
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

            submissions = [
                s.to_dict(
                    has_code=False,
                    has_output=False,
                    has_code_detail=False,
                ) for s in submissions
                if not s.handwritten or s.permission(user) > 1
            ]
            cache.set(cache_key, json.dumps(submissions), 15)

        # truncate
        if offset >= len(submissions) and len(submissions):
            raise ValueError(f'offset ({offset}) is out of range!')
        right = min(offset + count, len(submissions))
        if count == -1:
            right = len(submissions)
        submissions = submissions[offset:right]
    except ValueError as e:
        return HTTPError(str(e), 400)

        # unicorn gifs
    unicorns = [
        'https://media.giphy.com/media/xTiTnLmaxrlBHxsMMg/giphy.gif',
        'https://media.giphy.com/media/26AHG5KGFxSkUWw1i/giphy.gif',
        'https://media.giphy.com/media/g6i1lEax9Pa24/giphy.gif',
        'https://media.giphy.com/media/tTyTbFF9uEbPW/giphy.gif',
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
    # check permission
    if submission.handwritten and submission.permission(user) < 2:
        return HTTPError('forbidden.', 403)
    # ip validation
    problem = Problem(submission.problem_id)
    if not problem.is_valid_ip(get_ip()):
        return HTTPError('Invalid IP address.', 403)
    if not all(submission.timestamp in hw.duration
               for hw in problem.running_homeworks() if hw.ip_filters):
        return HTTPError('You can not view this submission during quiz.', 403)
    # serialize submission
    ret = submission.to_dict(
        has_code=submission.permission(user) >= 2
        and not submission.handwritten,
        has_output=submission.problem.can_view_stdout,
        has_code_detail=bool(submission.code),
    )
    return HTTPResponse(data=ret)


@submission_api.route(
    '/<submission_id>/output/<int:task_no>/<int:case_no>',
    methods=['GET'],
)
@Request.args('text')
@login_required
@submission_required
def get_submission_output(
    user,
    submission,
    task_no,
    case_no,
    text,
):
    if submission.permission(user) < 2:
        return HTTPError('permission denied', 403)
    if text is None:
        text = True
    else:
        try:
            text = {'true': True, 'false': False}[text]
        except KeyError:
            return HTTPError('Invalid `text` value.', 400)
    try:
        output = submission.get_output(
            task_no,
            case_no,
            text=text,
        )
    except FileNotFoundError as e:
        return HTTPError(str(e), 400)
    except AttributeError as e:
        return HTTPError(str(e), 102)
    return HTTPResponse('ok', data=output)


@submission_api.route('/<submission_id>/pdf/<item>', methods=['GET'])
@login_required
@submission_required
def get_submission_pdf(user, submission, item):
    # check the permission
    if submission.permission(user) < 2:
        return HTTPError('forbidden.', 403)
    # non-handwritten submissions have no pdf file
    if not submission.handwritten:
        return HTTPError('it is not a handwritten submission.', 400)
    if item not in ['comment', 'upload']:
        return HTTPError('/<submission_id>/pdf/<"upload" or "comment">', 400)
    try:
        if item == 'comment':
            data = submission.get_comment()
        else:
            data = submission.get_code('main.pdf', binary=True)
    except FileNotFoundError as e:
        return HTTPError('File not found.', 404)
    return send_file(
        io.BytesIO(data),
        mimetype='application/pdf',
        as_attachment=True,
        cache_timeout=0,
        attachment_filename=f'{item}-{submission.id[-6:] or "missing-id"}.pdf',
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
        return HTTPError(str(e), 400, data=e.to_dict())
    except TestCaseNotFound as e:
        return HTTPError(str(e), 403)
    if success:
        return HTTPResponse(
            f'{submission} {"is finished." if submission.handwritten else "send to judgement."}'
        )
    else:
        return HTTPError('Some error occurred, please contact the admin', 500)


@submission_api.route('/<submission_id>/grade', methods=['PUT'])
@login_required
@Request.json('score: int')
@submission_required
def grade_submission(user, submission, score):
    if submission.permission(user) < 3:
        return HTTPError('forbidden.', 403)

    if score < 0 or score > 100:
        return HTTPError('score must be between 0 to 100.', 400)

    # AC if the score is 100, WA otherwise
    submission.update(score=score, status=(0 if score == 100 else 1))
    submission.finish_judging()
    return HTTPResponse(f'{submission} score recieved.')


@submission_api.route('/<submission_id>/comment', methods=['PUT'])
@login_required
@Request.files('comment')
@submission_required
def comment_submission(user, submission, comment):
    if submission.permission(user) < 3:
        return HTTPError('forbidden.', 403)

    if comment is None:
        return HTTPError(
            f'can not find the comment',
            400,
        )
    try:
        submission.add_comment(comment)
    except ValueError as e:
        return HTTPError(str(e), 400)
    return HTTPResponse(f'{submission} comment recieved.')


@submission_api.route('/<submission_id>/rejudge', methods=['GET'])
@login_required
@submission_required
def rejudge(user, submission):
    if submission.status == -2 or (
            submission.status == -1 and
        (datetime.now() - submission.last_send).seconds < 300):
        return HTTPError(f'{submission} haven\'t be judged', 403)
    if submission.permission(user) < 3:
        return HTTPError('forbidden.', 403)
    try:
        success = submission.rejudge()
    except FileExistsError:
        exit(10086)
    except ValueError as e:
        return HTTPError(str(e), 400)
    except JudgeQueueFullError as e:
        return HTTPResponse(str(e), 202)
    except ValidationError as e:
        return HTTPError(str(e), data=e.to_dict())
    if success:
        return HTTPResponse(f'{submission} is sent to judgement.')
    else:
        return HTTPError('Some error occurred, please contact the admin', 500)


@submission_api.route('/config', methods=['GET', 'PUT'])
@login_required
@identity_verify(0)
def config(user):
    config = Submission.config()

    def get_config():
        ret = config.to_mongo()
        del ret['_cls']
        del ret['_id']
        return HTTPResponse('success.', data=ret)

    @Request.json('rate_limit: int', 'sandbox_instances: list')
    def modify_config(rate_limit, sandbox_instances):
        # try to convert json object to Sandbox instance
        try:
            sandbox_instances = [
                *map(
                    lambda s: engine.Sandbox(**s),
                    sandbox_instances,
                )
            ]
        except engine.ValidationError as e:
            return HTTPError(
                'wrong Sandbox schema',
                400,
                data=e.to_dict(),
            )
        # skip if during testing
        if not current_app.config['TESTING']:
            resps = []
            # check sandbox status
            for sb in sandbox_instances:
                resp = rq.get(f'{sb.url}/status')
                if not resp.ok:
                    resps.append((sb.name, resp))
            # some exception occurred
            if len(resps) != 0:
                return HTTPError(
                    'some error occurred when check sandbox status',
                    400,
                    data=[{
                        'name': name,
                        'statusCode': resp.status_code,
                        'response': resp.text,
                    } for name, resp in resps],
                )
        try:
            config.update(
                rate_limit=rate_limit,
                sandbox_instances=sandbox_instances,
            )
        except ValidationError as e:
            return HTTPError(str(e), 400)

        return HTTPResponse('success.')

    methods = {'GET': get_config, 'PUT': modify_config}
    return methods[request.method]()
