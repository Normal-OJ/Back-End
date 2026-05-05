import io
import os
import random
import secrets
import json
import httpx
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import StreamingResponse, Response
from datetime import datetime, timedelta
from mongo import *
from mongo import engine
from mongo.utils import (
    RedisCache,
    drop_none,
    is_testing,
)
from .utils import *
from .auth import identity_verify, login_required
from .schemas import (
    CreateSubmissionBody,
    GetSubmissionListQuery,
    OnSubmissionCompleteBody,
    GradeSubmissionBody,
    UpdateConfigBody,
)

__all__ = ['submission_router']
submission_router = APIRouter()


# /config must be defined before /{submission_id} to avoid path conflict
@submission_router.get('/config')
def get_config(user: User = identity_verify(0), ):
    config = Submission.config()
    ret = config.to_mongo()
    del ret['_cls']
    del ret['_id']
    return HTTPResponse('success.', data=ret)


@submission_router.put('/config')
def update_config(
        body: UpdateConfigBody,
        user: User = identity_verify(0),
):
    rate_limit = body.rate_limit
    sandbox_instances = body.sandbox_instances
    config = Submission.config()
    try:
        sandbox_instances = [
            *map(lambda s: engine.Sandbox(**s), sandbox_instances)
        ]
    except engine.ValidationError as e:
        return HTTPError('wrong Sandbox schema', 400, data=e.to_dict())
    if not is_testing():
        resps = []
        for sb in sandbox_instances:
            try:
                resp = httpx.get(f'{sb.url}/status', timeout=5.0)
            except httpx.RequestError as e:
                resps.append((sb.name, e))
                continue
            if not resp.is_success:
                resps.append((sb.name, resp))
        if len(resps) != 0:
            return HTTPError(
                'some error occurred when check sandbox status',
                400,
                data=[{
                    'name':
                    name,
                    'statusCode':
                    resp.status_code
                    if isinstance(resp, httpx.Response) else None,
                    'response':
                    resp.text
                    if isinstance(resp, httpx.Response) else str(resp),
                } for name, resp in resps],
            )
    try:
        config.update(rate_limit=rate_limit,
                      sandbox_instances=sandbox_instances)
    except ValidationError as e:
        return HTTPError(str(e), 400)
    return HTTPResponse('success.')


@submission_router.post('')
def create_submission(
        body: CreateSubmissionBody,
        user=Depends(login_required),
        ip: str = Depends(get_ip),
):
    language_type = body.language_type
    problem_id = body.problem_id
    now = datetime.now()
    delta = timedelta.total_seconds(now - user.last_submit)
    if delta <= Submission.config().rate_limit:
        wait_for = Submission.config().rate_limit - delta
        return HTTPError(
            'Submit too fast!\n'
            f'Please wait for {wait_for:.2f} seconds to submit.',
            429,
            data={'waitFor': wait_for},
        )
    if problem_id is None:
        return HTTPError('problemId is required!', 400)
    problem = Problem(problem_id)
    if not problem:
        return HTTPError('Unexisted problem id.', 404)
    if not problem.permission(user, Problem.Permission.VIEW):
        return HTTPError('problem permission denied!', 403)
    for homework in problem.obj.homeworks:
        if now < homework.duration.start:
            return HTTPError('this homework hasn\'t start.', 403)
    if not problem.is_valid_ip(ip):
        return HTTPError('Invalid IP address.', 403)
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
    if not problem.allowed(language_type):
        return HTTPError(
            'not allowed language',
            403,
            data={
                'allowed': problem.obj.allowed_language,
                'got': language_type
            },
        )
    if problem.obj.quota != -1:
        no_grade_permission = not any(
            c.permission(user=user, req=Course.Permission.GRADE)
            for c in map(Course, problem.courses))
        run_out_of_quota = problem.submit_count(user) >= problem.quota
        if no_grade_permission and run_out_of_quota:
            return HTTPError('you have used all your quotas', 403)
    user.problem_submission[str(problem_id)] = problem.submit_count(user) + 1
    user.save()
    try:
        submission = Submission.add(
            problem_id=problem_id,
            username=user.username,
            lang=language_type,
            timestamp=now,
            ip_addr=ip,
        )
    except ValidationError:
        return HTTPError('invalid data!', 400)
    except engine.DoesNotExist as e:
        return HTTPError(str(e), 404)
    except TestCaseNotFound as e:
        return HTTPError(str(e), 403)
    user.update(last_submit=now, push__submissions=submission.obj)
    submission.problem.update(inc__submitter=1)
    return HTTPResponse(
        'submission recieved.\nplease send source code with given submission id later.',
        data={'submissionId': submission.id},
    )


@submission_router.get('')
def get_submission_list(
        query: GetSubmissionListQuery = Depends(),
        user=Depends(login_required),
):
    offset = query.offset
    count = query.count
    problem_id = query.problem_id
    username = query.username
    status = query.status
    course = query.course
    before = query.before
    after = query.after
    language_type = query.language_type
    ip_addr = query.ip_addr

    def parse_int(val, name):
        if val is None:
            return None
        try:
            return int(val)
        except ValueError:
            raise ValueError(f'can not convert {name} to integer')

    def parse_str(val, name):
        if val is None:
            return None
        return str(val)

    def parse_timestamp(val, name):
        if val is None:
            return None
        try:
            return datetime.fromtimestamp(val)
        except ValueError:
            raise ValueError(f'can not convert {name} to timestamp')

    cache_key = '_'.join(
        map(str, (
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
        )))
    cache = RedisCache()
    if cache.exists(cache_key):
        submissions = json.loads(cache.get(cache_key))
        submission_count = submissions['submission_count']
        submissions = submissions['submissions']
    else:
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
            except ValueError:
                return HTTPError('cannot parse integers from languageType',
                                 400)
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
                'ip_addr': ip_addr,
            })
            submissions, submission_count = Submission.filter(**params,
                                                              with_count=True)
            submissions = [s.to_dict() for s in submissions]
            cache.set(
                cache_key,
                json.dumps({
                    'submissions': submissions,
                    'submission_count': submission_count
                }),
                15,
            )
        except ValueError as e:
            return HTTPError(str(e), 400)
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
    return HTTPResponse('here you are, bro', data=ret)


@submission_router.get('/{submission_id}')
def get_submission(
        ip: str = Depends(get_ip),
        user=Depends(login_required),
        submission: Submission = get_doc('submission_id', Submission),
):
    user_feedback_perm = submission.permission(user,
                                               Submission.Permission.FEEDBACK)
    if submission.handwritten and not user_feedback_perm:
        return HTTPError('forbidden.', 403)
    problem = Problem(submission.problem_id)
    if not problem.is_valid_ip(ip):
        return HTTPError('Invalid IP address.', 403)
    if not all(submission.timestamp in hw.duration
               for hw in problem.running_homeworks() if hw.ip_filters):
        return HTTPError('You cannot view this submission during quiz.', 403)
    has_code = not submission.handwritten and user_feedback_perm
    has_output = submission.problem.can_view_stdout
    ret = submission.to_dict()
    if has_code:
        try:
            ret['code'] = submission.get_main_code()
        except UnicodeDecodeError:
            ret['code'] = False
    ret['tasks'] = submission.get_detailed_result(
    ) if has_output else submission.get_result()
    return HTTPResponse(data=ret)


@submission_router.get('/{submission_id}/output/{task_no}/{case_no}')
def get_submission_output(
        task_no: int,
        case_no: int,
        user=Depends(login_required),
        submission: Submission = get_doc('submission_id', Submission),
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


@submission_router.get('/{submission_id}/pdf/{item}')
def get_submission_pdf(
        item: str,
        user=Depends(login_required),
        submission: Submission = get_doc('submission_id', Submission),
):
    if not submission.permission(user, Submission.Permission.FEEDBACK):
        return HTTPError('forbidden.', 403)
    if not submission.handwritten:
        return HTTPError('it is not a handwritten submission.', 400)
    if item not in ['comment', 'upload']:
        return HTTPError('/<submission_id>/pdf/<"upload" or "comment">', 400)
    try:
        if item == 'comment':
            data = submission.get_comment()
        else:
            data = submission.get_code('main.pdf', binary=True)
    except FileNotFoundError:
        return HTTPError('File not found.', 404)
    return Response(
        content=data,
        media_type='application/pdf',
        headers={
            'Content-Disposition':
            (f'attachment; filename="{item}-{submission.id[-6:] or "missing-id"}.pdf"'
             ),
            'Cache-Control':
            'no-store',
        },
    )


@submission_router.put('/{submission_id}/complete')
def on_submission_complete(
        body: OnSubmissionCompleteBody,
        submission: Submission = get_doc('submission_id', Submission),
):
    if not Submission.verify_token(submission.id, body.token):
        return HTTPError('i don\'t know you', 403)
    try:
        submission.process_result(body.tasks)
    except (ValidationError, KeyError) as e:
        return HTTPError(f'invalid data!\n{type(e).__name__}: {e}', 400)
    return HTTPResponse(f'{submission} result recieved.')


@submission_router.put('/{submission_id}')
def update_submission(
        submission_id: str,
        code: Optional[UploadFile] = File(default=None),
        user=Depends(login_required),
        submission: Submission = get_doc('submission_id', Submission),
        http_client: httpx.Client = Depends(get_http_client),
):
    if submission.status >= 0:
        return HTTPError(f'{submission} has finished judgement.', 403)
    if not secrets.compare_digest(submission.user.username, user.username):
        return HTTPError('user not equal!', 403)
    if code is None:
        return HTTPError('can not find the source file', 400)
    content = code.file.read()
    if len(content) == 0:
        return HTTPError('empty file', 400)
    code_file = io.BytesIO(content)
    if submission.has_code():
        return HTTPError(f'{submission} has been uploaded source file!', 403)
    try:
        success = submission.submit(code_file, client=http_client)
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


@submission_router.put('/{submission_id}/grade')
def grade_submission(
        body: GradeSubmissionBody,
        user: User = Depends(login_required),
        submission: Submission = get_doc('submission_id', Submission),
):
    if not submission.permission(user, Submission.Permission.GRADE):
        return HTTPError('forbidden.', 403)
    if body.score < 0 or body.score > 100:
        return HTTPError('score must be between 0 to 100.', 400)
    submission.update(score=body.score, status=(0 if body.score == 100 else 1))
    submission.finish_judging()
    return HTTPResponse(f'{submission} score recieved.')


@submission_router.put('/{submission_id}/comment')
async def comment_submission(
        submission_id: str,
        comment: Optional[UploadFile] = File(default=None),
        user=Depends(login_required),
        submission: Submission = get_doc('submission_id', Submission),
):
    if not submission.permission(user, Submission.Permission.COMMENT):
        return HTTPError('forbidden.', 403)
    if comment is None:
        return HTTPError('can not find the comment', 400)
    content = await comment.read()
    try:
        submission.add_comment(io.BytesIO(content))
    except ValueError as e:
        return HTTPError(str(e), 400)
    return HTTPResponse(f'{submission} comment recieved.')


@submission_router.get('/{submission_id}/rejudge')
def rejudge(
        user=Depends(login_required),
        submission: Submission = get_doc('submission_id', Submission),
        http_client: httpx.Client = Depends(get_http_client),
):
    if submission.status == -2 or (submission.status == -1 and
                                   (datetime.now() -
                                    submission.last_send).seconds < 300):
        return HTTPError(f'{submission} haven\'t be judged', 403)
    if not submission.permission(user, Submission.Permission.REJUDGE):
        return HTTPError('forbidden.', 403)
    try:
        success = submission.rejudge(client=http_client)
    except ValueError as e:
        return HTTPError(str(e), 400)
    except JudgeQueueFullError as e:
        return HTTPResponse(str(e), 202)
    except ValidationError as e:
        return HTTPError(str(e), 422, data=e.to_dict())
    if success:
        return HTTPResponse(f'{submission} is sent to judgement.')
    else:
        return HTTPError('Some error occurred, please contact the admin', 500)


@submission_router.post('/{submission_id}/migrate-code')
def migrate_code(
        user: User = identity_verify(0),
        submission: Submission = get_doc('submission_id', Submission),
):
    if not submission.permission(user, Submission.Permission.MANAGER):
        return HTTPError('forbidden.', 403)
    submission.migrate_code_to_minio()
    return HTTPResponse('ok')


@submission_router.post('/{submission_id}/migrate-output')
def migrate_output(
        user: User = identity_verify(0),
        submission: Submission = get_doc('submission_id', Submission),
):
    if not submission.permission(user, Submission.Permission.MANAGER):
        return HTTPError('forbidden.', 403)
    submission.migrate_output_to_minio()
    return HTTPResponse('ok')
