import json
import hashlib
import statistics
from dataclasses import asdict
from typing import Optional
from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from urllib import parse
from zipfile import BadZipFile
from mongo import *
from mongo import engine
from mongo import sandbox
from mongo.utils import drop_none
from mongo.problem import *
from .auth import identity_verify, login_required
from .utils import *
from .schemas import (
    ViewProblemListQuery,
    ProblemBody,
    InitiateTestCaseUploadBody,
    CompleteTestCaseUploadBody,
    GetTestdataQuery,
    CloneProblemBody,
    PublishProblemBody,
)

__all__ = ['problem_router']

problem_router = APIRouter()


def permission_error_response():
    return HTTPError('Not enough permission', 403)


def online_error_response():
    return HTTPError('Problem is unavailable', 403)


@problem_router.get('')
def view_problem_list(
        query: ViewProblemListQuery = Depends(),
        user=Depends(login_required),
):
    offset = query.offset
    count = query.count
    tags = query.tags
    problem_id = query.problem_id
    name = query.name
    course = query.course
    try:
        if offset is not None:
            offset = int(offset)
        if count is not None:
            count = int(count)
    except (TypeError, ValueError):
        return HTTPError('offset and count must be integer!', 400)
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
        data = Problem.get_problem_list(**ks)
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
        'submitCount': Problem(p.problem_id).submit_count(user),
    } for p in data]
    return HTTPResponse('Success.', data=data)


@problem_router.get('/manage/{problem_id}')
def get_problem_detailed(
        user: User = identity_verify(0, 1),
        problem: Problem = get_doc('problem_id', Problem, int),
):
    if not problem.permission(user, problem.Permission.MANAGE):
        return permission_error_response()
    if not problem.permission(user=user, req=problem.Permission.ONLINE):
        return online_error_response()
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
    info['submitCount'] = problem.submit_count(user)
    return HTTPResponse('Success.', data=info)


@problem_router.post('/manage')
def create_problem(body: ProblemBody, user: User = identity_verify(0, 1)):
    try:
        pid = Problem.add(user=user, **body.model_dump())
    except ValidationError as e:
        return HTTPError('Invalid or missing arguments.',
                         400,
                         data=e.to_dict())
    except DoesNotExist:
        return HTTPError('Course not found', 404)
    except ValueError as e:
        return HTTPError(str(e), 400)
    return HTTPResponse(data={'problemId': pid})


@problem_router.delete('/manage/{problem_id}')
def delete_problem(
        user: User = identity_verify(0, 1),
        problem: Problem = get_doc('problem_id', Problem, int),
):
    if not problem.permission(user, problem.Permission.MANAGE):
        return permission_error_response()
    if not problem.permission(user=user, req=problem.Permission.ONLINE):
        return online_error_response()
    problem.delete()
    return HTTPResponse()


@problem_router.put('/manage/{problem_id}')
async def manage_problem(
        problem_id: int,
        request: Request,
        user: User = identity_verify(0, 1),
):
    problem = Problem(problem_id)
    if not problem:
        raise NOJException('Problem not found', 404)
    if not problem.permission(user, problem.Permission.MANAGE):
        return permission_error_response()
    if not problem.permission(user=user, req=problem.Permission.ONLINE):
        return online_error_response()

    content_type = request.headers.get('content-type', '')
    if content_type.startswith('application/json'):
        body_data = await request.json()
        try:
            body = ProblemBody(**body_data)
        except Exception:
            return HTTPError('Invalid or missing arguments.', 400)
        try:
            Problem.edit_problem(
                user=user,
                problem_id=problem.id,
                **drop_none(body.model_dump()),
            )
        except ValidationError as ve:
            return HTTPError('Invalid or missing arguments.',
                             400,
                             data=ve.to_dict())
        except engine.DoesNotExist:
            return HTTPError('Course not found.', 404)
        return HTTPResponse()
    elif content_type.startswith('multipart/form-data'):
        from io import BytesIO
        form = await request.form()
        case_upload = form.get('case')
        case = BytesIO(await case_upload.read()) if hasattr(
            case_upload, 'read') else case_upload
        try:
            problem.update_test_case(case)
        except engine.DoesNotExist as e:
            return HTTPError(str(e), 404)
        except (ValueError, BadZipFile) as e:
            return HTTPError(str(e), 400)
        except BadTestCase as e:
            return HTTPError(str(e), 400)
        return HTTPResponse('Success.')
    else:
        return HTTPError('Unknown content type',
                         400,
                         data={'contentType': content_type})


@problem_router.post('/{problem_id}/initiate-test-case-upload')
def initiate_test_case_upload(
        body: InitiateTestCaseUploadBody,
        user: User = identity_verify(0, 1),
        problem: Problem = get_doc('problem_id', Problem, int),
):
    if not problem.permission(user, problem.Permission.MANAGE):
        return permission_error_response()
    if not problem.permission(user=user, req=problem.Permission.ONLINE):
        return online_error_response()
    upload_info = problem.generate_urls_for_uploading_test_case(
        body.length, body.part_size)
    return HTTPResponse(data=asdict(upload_info))


@problem_router.post('/{problem_id}/complete-test-case-upload')
def complete_test_case_upload(
        body: CompleteTestCaseUploadBody,
        user: User = identity_verify(0, 1),
        problem: Problem = get_doc('problem_id', Problem, int),
):
    if not problem.permission(user, problem.Permission.MANAGE):
        return permission_error_response()
    if not problem.permission(user=user, req=problem.Permission.ONLINE):
        return online_error_response()
    from minio.datatypes import Part
    parts = [
        Part(part_number=part['PartNumber'], etag=part['ETag'])
        for part in body.parts
    ]
    try:
        problem.complete_test_case_upload(body.upload_id, parts)
    except BadTestCase as e:
        return HTTPError(str(e), 400)
    return HTTPResponse(status_code=201)


@problem_router.get('/{problem_id}/test-case')
@problem_router.get('/{problem_id}/testcase')
def get_test_case(
        problem_id: int,
        user=Depends(login_required),
        problem: Problem = get_doc('problem_id', Problem, int),
):
    if not problem.permission(user, problem.Permission.MANAGE):
        return permission_error_response()
    if not problem.permission(user=user, req=problem.Permission.ONLINE):
        return online_error_response()
    return StreamingResponse(
        problem.get_test_case(),
        media_type='application/zip',
        headers={
            'Content-Disposition':
            f'attachment; filename="testdata-{problem.id}.zip"'
        },
    )


@problem_router.get('/{problem_id}/testdata')
def get_testdata(
        query: GetTestdataQuery = Depends(),
        problem: Problem = get_doc('problem_id', Problem, int),
):
    if sandbox.find_by_token(query.token) is None:
        return HTTPError('Invalid sandbox token', 401)
    return StreamingResponse(
        problem.get_test_case(),
        media_type='application/zip',
        headers={
            'Content-Disposition':
            f'attachment; filename="testdata-{problem.id}.zip"'
        },
    )


@problem_router.get('/{problem_id}/checksum')
def get_checksum(problem_id: int, query: GetTestdataQuery = Depends()):
    if sandbox.find_by_token(query.token) is None:
        return HTTPError('Invalid sandbox token', 401)
    problem = Problem(problem_id)
    if not problem:
        return HTTPError(f'{problem} not found', 404)
    meta = json.dumps({
        'tasks':
        [json.loads(task.to_json()) for task in problem.test_case.tasks]
    }).encode()
    content = problem.get_test_case().read() + meta
    digest = hashlib.md5(content).hexdigest()
    return HTTPResponse(data=digest)


@problem_router.get('/{problem_id}/meta')
def get_meta(problem_id: int, query: GetTestdataQuery = Depends()):
    if sandbox.find_by_token(query.token) is None:
        return HTTPError('Invalid sandbox token', 401)
    problem = Problem(problem_id)
    if not problem:
        return HTTPError(f'{problem} not found', 404)
    meta = {
        'tasks':
        [json.loads(task.to_json()) for task in problem.test_case.tasks]
    }
    return HTTPResponse(data=meta)


@problem_router.get('/{problem_id}/high-score')
def high_score(
        user=Depends(login_required),
        problem: Problem = get_doc('problem_id', Problem, int),
):
    return HTTPResponse(data={'score': problem.get_high_score(user=user)})


@problem_router.post('/clone')
@problem_router.post('/copy')
def clone_problem(body: CloneProblemBody, user: User = identity_verify(0, 1)):
    try:
        problem = Problem(body.problem_id)
        if not problem:
            return HTTPError('Problem not found', 404)
    except engine.DoesNotExist as e:
        return HTTPError(str(e), 404)
    if not problem.permission(user, problem.Permission.VIEW):
        return HTTPError('Problem can not view.', 403)
    override = drop_none({'status': body.status})
    new_problem_id = problem.copy_to(user=user, target=body.target, **override)
    return HTTPResponse('Success.', data={'problemId': new_problem_id})


@problem_router.post('/publish')
def publish_problem(body: PublishProblemBody,
                    user: User = identity_verify(0, 1)):
    try:
        problem = Problem(body.problem_id)
        if not problem:
            return HTTPError('Problem not found', 404)
    except engine.DoesNotExist as e:
        return HTTPError(str(e), 404)
    if user.role == 1 and problem.owner != user.username:
        return HTTPError('Not the owner.', 403)
    Problem.release_problem(problem.problem_id)
    return HTTPResponse('Success.')


@problem_router.get('/{problem_id}/stats')
def problem_stats(
        user=Depends(login_required),
        problem: Problem = get_doc('problem_id', Problem, int),
):
    if not problem.permission(user, problem.Permission.VIEW):
        return permission_error_response()
    if not problem.permission(user=user, req=problem.Permission.ONLINE):
        return online_error_response()
    ret = {}
    students = []
    for course in problem.courses:
        students += [User(name) for name in course.student_nicknames.keys()]
    students_high_scores = [problem.get_high_score(user=u) for u in students]
    ret['acUserRatio'] = [problem.get_ac_user_count(), len(students)]
    ret['triedUserCount'] = problem.get_tried_user_count()
    ret['average'] = None if len(students) == 0 else statistics.mean(
        students_high_scores)
    ret['std'] = None if len(students) <= 1 else statistics.pstdev(
        students_high_scores)
    ret['scoreDistribution'] = students_high_scores
    ret['statusCount'] = problem.get_submission_status()
    params = {
        'user': user,
        'offset': 0,
        'count': 10,
        'problem': problem.id,
        'status': 0
    }
    ret['top10RunTime'] = [
        s.to_dict() for s in Submission.filter(**params, sort_by='runTime')
    ]
    ret['top10MemoryUsage'] = [
        s.to_dict() for s in Submission.filter(**params, sort_by='memoryUsage')
    ]
    return HTTPResponse('Success.', data=ret)


@problem_router.get('/{problem_id}')
@problem_router.get('/view/{problem_id}')
def view_problem(
        problem_id: int,
        ip: str = Depends(get_ip),
        user=Depends(login_required),
        problem: Problem = get_doc('problem_id', Problem, int),
):
    if not problem.permission(user=user, req=problem.Permission.VIEW):
        return permission_error_response()
    if not problem.permission(user=user, req=problem.Permission.ONLINE):
        return online_error_response()
    if not problem.is_valid_ip(ip):
        return HTTPError('Invalid IP address.', 403)
    data = problem.detailed_info(
        'problemName',
        'description',
        'owner',
        'tags',
        'allowedLanguage',
        'courses',
        'quota',
        defaultCode='defaultCode',
        status='problemStatus',
        type='problemType',
        testCase='testCase__tasks',
    )
    if problem.obj.problem_type == 1:
        data['fillInTemplate'] = problem.obj.test_case.fill_in_template
    data.update({
        'submitCount': problem.submit_count(user),
        'highScore': problem.get_high_score(user=user),
    })
    return HTTPResponse('Problem can view.', data=data)


@problem_router.post('/{problem_id}/migrate-test-case')
def problem_migrate_test_case(
        user: User = identity_verify(0),
        problem: Problem = get_doc('problem_id', Problem, int),
):
    if not problem.permission(user, problem.Permission.MANAGE):
        return permission_error_response()
    problem.migrate_gridfs_to_minio()
    return HTTPResponse('Success.')
