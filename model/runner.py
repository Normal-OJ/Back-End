"""Runner API blueprint: registration, heartbeat, job pickup, completion."""
import secrets
from datetime import timedelta

from flask import Blueprint, request
from mongoengine.errors import ValidationError as MongoValidationError

from mongo import Submission
from mongo.utils import MinioClient
from .schemas import RegisterRunnerBody, CompleteJobBody, AbortJobBody
from .utils import HTTPError, HTTPResponse, parse_body, require_runner_token

from dispatch import runner as runner_mod
from dispatch import job as job_mod
from dispatch.config import (
    RUNNER_REGISTRATION_TOKEN,
    HEARTBEAT_INTERVAL_SEC,
    POLL_INTERVAL_SEC,
    MAX_CONCURRENT_JOBS_PER_RUNNER,
    CODE_PRESIGNED_URL_TTL_SEC,
)

__all__ = ["runner_api"]
runner_api = Blueprint("runner_api", __name__)


@runner_api.post("/register")
@parse_body(RegisterRunnerBody)
def register(body: RegisterRunnerBody):
    if not secrets.compare_digest(body.registration_token,
                                  RUNNER_REGISTRATION_TOKEN):
        return HTTPError("invalid registration token", 401)
    rn_id, rk_token = runner_mod.register(
        name=body.name or "unnamed",
        registration_ip=request.remote_addr or "unknown",
    )
    return HTTPResponse(
        data={
            "runner_id": rn_id,
            "token": rk_token,
            "config": {
                "heartbeat_interval_sec": HEARTBEAT_INTERVAL_SEC,
                "poll_interval_sec": POLL_INTERVAL_SEC,
                "max_concurrent_jobs": MAX_CONCURRENT_JOBS_PER_RUNNER,
            },
        },
        status_code=201,
    )


@runner_api.post("/<runner_id>/heartbeat")
@require_runner_token
def heartbeat(runner_id):
    runner_mod.renew_alive(runner_id)
    job_mod.renew_leases(runner_id)
    return "", 204


@runner_api.get("/<runner_id>/next-job")
@require_runner_token
def next_job(runner_id):
    payload = job_mod.claim_next_job(runner_id)
    if payload is None:
        return "", 204
    # Convert code_minio_path to presigned URL just before sending
    minio_path = payload.pop("code_minio_path")
    minio = MinioClient()
    try:
        payload["code_url"] = minio.client.presigned_get_object(
            minio.bucket,
            minio_path,
            expires=timedelta(seconds=CODE_PRESIGNED_URL_TTL_SEC),
        )
    except Exception:
        job_mod.abort_job(
            rn_id=runner_id,
            jb_id=payload["job_id"],
            reason="failed to prepare job payload",
        )
        return HTTPError("failed to prepare job payload", 503)
    return HTTPResponse(data=payload)


@runner_api.put("/<runner_id>/jobs/<job_id>/complete")
@require_runner_token
@parse_body(CompleteJobBody)
def complete(runner_id, job_id, body: CompleteJobBody):

    def process(submission_id_str: str, tasks: list) -> None:
        Submission(submission_id_str).process_result(tasks)

    plain_tasks = [[case.model_dump() for case in task] for task in body.tasks]
    try:
        result = job_mod.complete_job(
            rn_id=runner_id,
            jb_id=job_id,
            tasks=plain_tasks,
            process_result=process,
        )
    except (MongoValidationError, KeyError) as e:
        return HTTPError(f"malformed result payload: {e}", 400)
    if result == "wrong_owner":
        return HTTPError("job has been reclaimed by another runner", 409)
    if result == "lease_expired":
        return HTTPError("job lease has expired", 409)
    if result == "stale":
        return HTTPError("job is no longer current for this submission", 409)
    if result == "busy":
        return HTTPError("submission is busy", 503)
    if result == "not_found":
        return HTTPError("job not found", 404)
    return "", 204


@runner_api.put("/<runner_id>/jobs/<job_id>/abort")
@require_runner_token
@parse_body(AbortJobBody)
def abort(runner_id, job_id, body: AbortJobBody):
    result = job_mod.abort_job(
        rn_id=runner_id,
        jb_id=job_id,
        reason=body.reason or "",
    )
    if result in {"wrong_owner", "stale"}:
        return HTTPError("job has been reclaimed by another runner", 409)
    if result == "not_found":
        return HTTPError("job not found", 404)
    if result == "busy":
        return HTTPError("submission is busy", 503)
    if result == "error":
        return HTTPError("failed to finalize job", 500)
    return "", 202
