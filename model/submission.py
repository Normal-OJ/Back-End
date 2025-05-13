import io
from typing import Optional
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
from mongo import *
from mongo import engine
from mongo.utils import (
    RedisCache,
    drop_none,
)
from .utils import *
from .auth import *

__all__ = ['submission_api']
submission_api = Blueprint('submission_api', __name__)


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
    problem = Problem(problem_id)
    if not problem:
        return HTTPError('Unexisted problem id.', 404)
    # problem permissoion
    if not problem.permission(user, Problem.Permission.VIEW):
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
    if problem.obj.quota != -1:
        no_grade_permission = not any(
            c.permission(user=user, req=Course.Permission.GRADE)
            for c in map(Course, problem.courses))

        run_out_of_quota = problem.submit_count(user) >= problem.quota
        if no_grade_permission and run_out_of_quota:
            return HTTPError('you have used all your quotas', 403)
    user.problem_submission[str(problem_id)] = problem.submit_count(user) + 1
    user.save()
    # insert submission to DB
    ip_addr = request.headers.get('cf-connecting-ip', request.remote_addr)
    try:
        submission = Submission.add(problem_id=problem_id,
                                    username=user.username,
                                    lang=language_type,
                                    timestamp=now,
                                    ip_addr=ip_addr)
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
@Request.args('offset', 'count', 'problem_id', 'username', 'status',
              'language_type', 'course', 'before', 'after', 'ip_addr')
def get_submission_list(
    user,
    offset,
    count,
    problem_id,
    username,
    status,
    course,
    before,
    after,
    language_type,
    ip_addr,
):
    '''
    get the list of submission data
    '''

    def parse_int(val: Optional[int], name: str):
        if val is None:
            return None
        try:
            return int(val)
        except ValueError:
            raise ValueError(f'can not convert {name} to integer')

    def parse_str(val: Optional[str], name: str):
        if val is None:
            return None
        try:
            return str(val)
        except ValueError:
            raise ValueError(f'can not convert {name} to string')

    def parse_timestamp(val: Optional[int], name: str):
        if val is None:
            return None
        try:
            return datetime.fromtimestamp(val)
        except ValueError:
            raise ValueError(f'can not convert {name} to timestamp')

    cache_key = (
        'SUBMISSION_LIST_API',
        user,
        problem_id,
        username,
        status,
        language_type,
        course,
        offset,
        count,
        before,
        after,
    )

    cache_key = '_'.join(map(str, cache_key))
    cache = RedisCache()
    # check cache
    if cache.exists(cache_key):
        submissions = json.loads(cache.get(cache_key))
        submission_count = submissions['submission_count']
        submissions = submissions['submissions']
    else:
        # convert args
        offset = parse_int(offset, 'offset')
        count = parse_int(count, 'count')
        problem_id = parse_int(problem_id, 'problemId')
        status = parse_int(status, 'status')
        before = parse_timestamp(before, 'before')
        after = parse_timestamp(after, 'after')
        ip_addr = parse_str(ip_addr, 'ip_addr')

        if language_type is not None:
            try:
                language_type = list(map(int, language_type.split(',')))
            except ValueError as e:
                return HTTPError(
                    'cannot parse integers from languageType',
                    400,
                )
        # students can only get their own submissions
        if user.role == User.engine.Role.STUDENT:
            username = user.username
        try:
            params = drop_none({
                'user': user,
                'offset': offset,
                'count': count,
                'problem': problem_id,
                'q_user': username,
                'status': status,
                'language_type': language_type,
                'course': course,
                'before': before,
                'after': after,
                'ip_addr': ip_addr
            })
            submissions, submission_count = Submission.filter(
                **params,
                with_count=True,
            )
            submissions = [s.to_dict() for s in submissions]
            cache.set(
                cache_key,
                json.dumps({
                    'submissions': submissions,
                    'submission_count': submission_count,
                }), 15)
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
        'submissionCount': submission_count,
    }
    return HTTPResponse(
        'here you are, bro',
        data=ret,
    )


@submission_api.route('/<submission>', methods=['GET'])
@login_required
@Request.doc('submission', Submission)
def get_submission(user, submission: Submission):
    user_feedback_perm = submission.permission(user,
                                               Submission.Permission.FEEDBACK)
    # check permission
    if submission.handwritten and not user_feedback_perm:
        return HTTPError('forbidden.', 403)
    # ip validation
    problem = Problem(submission.problem_id)
    if not problem.is_valid_ip(get_ip()):
        return HTTPError('Invalid IP address.', 403)
    if not all(submission.timestamp in hw.duration
               for hw in problem.running_homeworks() if hw.ip_filters):
        return HTTPError('You cannot view this submission during quiz.', 403)
    # serialize submission
    has_code = not submission.handwritten and user_feedback_perm
    has_output = submission.problem.can_view_stdout
    ret = submission.to_dict()
    if has_code:
        try:
            ret['code'] = submission.get_main_code()
        except UnicodeDecodeError:
            ret['code'] = False
    if has_output:
        ret['tasks'] = submission.get_detailed_result()
    else:
        ret['tasks'] = submission.get_result()
    return HTTPResponse(data=ret)


@submission_api.get('/<submission>/output/<int:task_no>/<int:case_no>')
@login_required
@Request.doc('submission', Submission)
def get_submission_output(
    user,
    submission: Submission,
    task_no: int,
    case_no: int,
):
    if not submission.permission(user, Submission.Permission.VIEW_OUTPUT):
        return HTTPError('permission denied', 403)
    try:
        output = submission.get_single_output(task_no, case_no)
    except FileNotFoundError as e:
        return HTTPError(str(e), 400)
    except AttributeError as e:
        return HTTPError(str(e), 102)
    return HTTPResponse('ok', data=output)


@submission_api.route('/<submission>/pdf/<item>', methods=['GET'])
@login_required
@Request.doc('submission', Submission)
def get_submission_pdf(user, submission: Submission, item):
    # check the permission
    if not submission.permission(user, Submission.Permission.FEEDBACK):
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
        max_age=0,
        download_name=f'{item}-{submission.id[-6:] or "missing-id"}.pdf',
    )


@submission_api.route('/<submission>/complete', methods=['PUT'])
@Request.json('tasks: list', 'token: str')
@Request.doc('submission', Submission)
def on_submission_complete(submission: Submission, tasks, token):
    if not Submission.verify_token(submission.id, token):
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


@submission_api.route('/<submission>', methods=['PUT'])
@login_required
@Request.doc('submission', Submission)
@Request.files('code')
def update_submission(user, submission: Submission, code):
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
    if submission.has_code():
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


@submission_api.route('/<submission>/grade', methods=['PUT'])
@login_required
@Request.json('score: int')
@Request.doc('submission', Submission)
def grade_submission(user: User, submission: Submission, score: int):
    if not submission.permission(user, Submission.Permission.GRADE):
        return HTTPError('forbidden.', 403)

    if score < 0 or score > 100:
        return HTTPError('score must be between 0 to 100.', 400)

    # AC if the score is 100, WA otherwise
    submission.update(score=score, status=(0 if score == 100 else 1))
    submission.finish_judging()
    return HTTPResponse(f'{submission} score recieved.')


@submission_api.route('/<submission>/comment', methods=['PUT'])
@login_required
@Request.files('comment')
@Request.doc('submission', Submission)
def comment_submission(user, submission: Submission, comment):
    if not submission.permission(user, Submission.Permission.COMMENT):
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


@submission_api.route('/<submission>/rejudge', methods=['GET'])
@login_required
@Request.doc('submission', Submission)
def rejudge(user, submission: Submission):
    if submission.status == -2 or (submission.status == -1 and
                                   (datetime.now() -
                                    submission.last_send).seconds < 300):
        return HTTPError(f'{submission} haven\'t be judged', 403)
    if not submission.permission(user, Submission.Permission.REJUDGE):
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

@submission_api.post('/<submission>/migrate-code')
@login_required
@identity_verify(0)
@Request.doc('submission', Submission)
def migrate_code(user: User, submission: Submission):
    if not submission.permission(
        user,
        Submission.Permission.MANAGER,
    ):
        return HTTPError('forbidden.', 403)

    submission.migrate_code_to_minio()
    return HTTPResponse('ok')
