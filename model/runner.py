import io
import secrets
from flask import Blueprint, request, send_file
from datetime import datetime, timedelta
from mongo import *
from mongo import engine
from mongo.utils import RedisCache, MinioClient
from .utils import *

__all__ = ['runner_api']
runner_api = Blueprint('runner_api', __name__)

# Claim timeout: if a runner doesn't complete within this time,
# the job becomes available again (like GitHub Actions runner timeout)
CLAIM_TIMEOUT_SECONDS = 600


def _verify_runner_token(req):
    """Verify the runner token from request headers or params."""
    token = req.headers.get('X-Runner-Token', '')
    config = Submission.config()
    for sb in config.sandbox_instances:
        if secrets.compare_digest(token, sb.token):
            return True
    return False


def _get_runner_name(req):
    """Get runner name from request headers."""
    return req.headers.get('X-Runner-Name', 'unknown')


@runner_api.before_request
def check_runner_auth():
    if not _verify_runner_token(request):
        return HTTPError('invalid runner token', 403)


@runner_api.route('/jobs', methods=['GET'])
def get_pending_jobs():
    """
    Runner polls this endpoint to find available jobs.
    Returns pending submissions that are not claimed or whose claim has expired.

    Similar to GitHub Actions: runner asks "any work for me?"
    """
    from mongoengine.queryset.visitor import Q
    now = datetime.now()
    claim_deadline = now - timedelta(seconds=CLAIM_TIMEOUT_SECONDS)

    # Find submissions that are:
    # 1. status=-1 (judging / ready to be judged)
    # 2. Not claimed, OR claim has expired
    # 3. Not handwritten (language != 3)
    pending = engine.Submission.objects(
        Q(status=-1) & Q(language__ne=3)
        & (Q(claimed_by=None) | Q(claimed_at=None)
           | Q(claimed_at__lte=claim_deadline)), ).order_by('last_send')

    jobs = []
    for sub in pending:
        # Skip if no code uploaded yet
        if sub.code_minio_path is None and (sub.code is None
                                            or sub.code.grid_id is None):
            continue
        jobs.append({
            'submissionId': str(sub.id),
            'problemId': sub.problem.problem_id,
            'language': sub.language,
            'timestamp': sub.timestamp.timestamp(),
        })
        # Return at most 10 jobs per poll
        if len(jobs) >= 10:
            break

    return HTTPResponse('ok', data={'jobs': jobs})


@runner_api.route('/jobs/<submission_id>/claim', methods=['POST'])
def claim_job(submission_id: str):
    """
    Runner claims a job for processing.

    Similar to GitHub Actions: runner picks up a job from the queue.
    Uses optimistic locking via claimed_at to prevent double-claiming.
    """
    from mongoengine.queryset.visitor import Q
    now = datetime.now()
    claim_deadline = now - timedelta(seconds=CLAIM_TIMEOUT_SECONDS)
    runner_name = _get_runner_name(request)

    # Atomic conditional update to prevent race conditions
    updated = engine.Submission.objects(
        Q(id=submission_id) & Q(status=-1)
        & (Q(claimed_by=None) | Q(claimed_at=None)
           | Q(claimed_at__lte=claim_deadline)), ).update_one(
               set__claimed_by=runner_name,
               set__claimed_at=now,
           )

    if updated == 0:
        # Either not found, not pending, or already claimed
        try:
            sub = engine.Submission.objects.get(id=submission_id)
        except engine.DoesNotExist:
            return HTTPError('submission not found', 404)
        if sub.status != -1:
            return HTTPError('submission is not pending', 409)
        return HTTPError('already claimed by another runner', 409)

    sub = engine.Submission.objects.get(id=submission_id)

    # Generate and assign a token for result callback
    token = Submission.assign_token(submission_id)

    # Build job metadata
    problem = sub.problem
    test_case = problem.test_case
    tasks = []
    for t in test_case.tasks:
        tasks.append({
            'taskScore': t.task_score,
            'caseCount': t.case_count,
            'memoryLimit': t.memory_limit,
            'timeLimit': t.time_limit,
        })

    return HTTPResponse(
        'job claimed',
        data={
            'submissionId': str(sub.id),
            'problemId': problem.problem_id,
            'language': sub.language,
            'token': token,
            'meta': {
                'language': sub.language,
                'tasks': tasks,
            },
        },
    )


@runner_api.route('/jobs/<submission_id>/code', methods=['GET'])
def get_job_code(submission_id: str):
    """
    Runner downloads the source code zip for a claimed job.
    """
    try:
        sub = engine.Submission.objects.get(id=submission_id)
    except engine.DoesNotExist:
        return HTTPError('submission not found', 404)

    # Verify this runner has claimed this job
    runner_name = _get_runner_name(request)
    if sub.claimed_by != runner_name:
        return HTTPError('not claimed by this runner', 403)

    # Get code from minio or gridfs
    if sub.code_minio_path is not None:
        minio_client = MinioClient()
        try:
            resp = minio_client.client.get_object(
                minio_client.bucket,
                sub.code_minio_path,
            )
            data = resp.read()
        finally:
            if 'resp' in locals():
                resp.close()
                resp.release_conn()
    elif sub.code is not None and sub.code.grid_id is not None:
        data = sub.code.read()
    else:
        return HTTPError('code not found', 404)

    return send_file(
        io.BytesIO(data),
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'{submission_id}.zip',
    )


@runner_api.route('/jobs/<submission_id>/testdata', methods=['GET'])
def get_job_testdata(submission_id: str):
    """
    Runner downloads the testdata zip for a claimed job's problem.
    """
    try:
        sub = engine.Submission.objects.get(id=submission_id)
    except engine.DoesNotExist:
        return HTTPError('submission not found', 404)

    runner_name = _get_runner_name(request)
    if sub.claimed_by != runner_name:
        return HTTPError('not claimed by this runner', 403)

    problem = sub.problem
    test_case = problem.test_case
    if test_case.case_zip_minio_path is not None:
        minio_client = MinioClient()
        try:
            resp = minio_client.client.get_object(
                minio_client.bucket,
                test_case.case_zip_minio_path,
            )
            data = resp.read()
        finally:
            if 'resp' in locals():
                resp.close()
                resp.release_conn()
    elif test_case.case_zip is not None and test_case.case_zip.grid_id is not None:
        data = test_case.case_zip.read()
    else:
        return HTTPError('testdata not found', 404)

    return send_file(
        io.BytesIO(data),
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'testdata-{problem.problem_id}.zip',
    )


@runner_api.route('/jobs/<submission_id>/complete', methods=['PUT'])
def on_job_complete(submission_id: str):
    """
    Runner reports job completion with results.
    Reuses the existing submission completion logic.

    This is the same as the existing /submission/<id>/complete endpoint,
    but authenticated via runner token instead of per-submission token.
    """
    data = request.json
    if data is None:
        return HTTPError('missing JSON body', 400)

    tasks = data.get('tasks')
    token = data.get('token')
    if tasks is None or token is None:
        return HTTPError('missing tasks or token', 400)

    # Verify the completing runner is the one that claimed this job
    try:
        sub = engine.Submission.objects.get(id=submission_id)
    except engine.DoesNotExist:
        return HTTPError('submission not found', 404)

    runner_name = _get_runner_name(request)
    if sub.claimed_by != runner_name:
        return HTTPError('not claimed by this runner', 403)

    submission = Submission(submission_id)
    if not submission:
        return HTTPError('submission not found', 404)

    if not Submission.verify_token(submission.id, token):
        return HTTPError('invalid submission token', 403)

    try:
        submission.process_result(tasks)
    except (engine.ValidationError, KeyError) as e:
        return HTTPError(
            f'invalid data!\n{type(e).__name__}: {e}',
            400,
        )

    # Clear claim fields after successful completion
    submission.update(claimed_by=None, claimed_at=None)

    return HTTPResponse(f'{submission} result received.')


@runner_api.route('/heartbeat', methods=['POST'])
def runner_heartbeat():
    """
    Runner sends periodic heartbeat to extend claim timeout.

    Similar to GitHub Actions: runner reports it's still alive.
    """
    data = request.json or {}
    submission_id = data.get('submissionId')
    if submission_id is None:
        return HTTPResponse('ok')

    try:
        sub = engine.Submission.objects.get(id=submission_id)
    except engine.DoesNotExist:
        return HTTPError('submission not found', 404)

    runner_name = _get_runner_name(request)
    if sub.claimed_by != runner_name:
        return HTTPError('not claimed by this runner', 403)

    # Extend the claim
    sub.update(claimed_at=datetime.now())
    return HTTPResponse('heartbeat received')
