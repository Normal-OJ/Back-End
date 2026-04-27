"""Job lifecycle: enqueue, claim (pending + orphan reclaim), complete."""
import json
from datetime import datetime, timezone
from typing import Optional

from ulid import ULID

from mongo.utils import RedisCache
from .redis_keys import job_key, JOBS_PENDING, JOBS_LEASED


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_tasks_meta(submission) -> list[dict]:
    """Extract testcase metadata from submission for runner."""
    tasks = submission.problem.test_case_info.get("tasks", [])
    return [
        {
            "task_id": idx,
            "case_count": t.get("caseCount", 0),
            "memory_limit": t.get("memoryLimit", 0),
            "time_limit": t.get("timeLimit", 0),
        }
        for idx, t in enumerate(tasks)
    ]


def enqueue_job(submission) -> str:
    """Create a Job from a Submission and push to pending queue. Returns jb_id."""
    jb_id = f"jb_{ULID()}"
    rds = RedisCache().client

    rds.hset(job_key(jb_id), mapping={
        "submission_id": str(submission.id),
        "problem_id": submission.problem_id,
        "language": submission.language,
        "code_minio_path": submission.code_minio_path,
        "checker": 'print("not implement yet. qaq")',
        "tasks_meta_json": json.dumps(_build_tasks_meta(submission)),
        "attempts": 0,
        "created_at": _now_iso(),
    })
    rds.lpush(JOBS_PENDING, jb_id)
    return jb_id


def claim_next_job(rn_id: str) -> Optional[dict]:
    """Try to claim next job for this runner. Returns None if no job available.

    Strategy:
        1. Try pending queue (RPOP for FIFO; LPUSH+RPOP gives FIFO).
        2. (Task 5 will add orphan reclaim here.)
        3. If neither yields a job, return None.
    """
    rds = RedisCache().client

    # Step 1: pending queue
    jb_id_bytes = rds.rpop(JOBS_PENDING)
    if jb_id_bytes is not None:
        jb_id = jb_id_bytes.decode()
        _assign_to_runner(jb_id, rn_id)
        return _build_payload(jb_id)

    # Step 2: orphan reclaim — implemented in Task 5
    return None


def _assign_to_runner(jb_id: str, rn_id: str) -> None:
    """Mark job as leased to this runner (called after RPOP from pending)."""
    rds = RedisCache().client
    rds.hset(job_key(jb_id), mapping={
        "leased_by": rn_id,
        "leased_at": _now_iso(),
    })
    rds.hincrby(job_key(jb_id), "attempts", 1)
    rds.sadd(JOBS_LEASED, jb_id)


def _build_payload(jb_id: str) -> dict:
    """Build the payload returned to the runner via next-job endpoint.

    Note: code_minio_path is returned as-is here. The blueprint layer is
    responsible for converting it to a presigned URL before sending to runner.
    """
    rds = RedisCache().client
    h = rds.hgetall(job_key(jb_id))
    # Decode bytes to str
    h = {k.decode(): v.decode() for k, v in h.items()}
    return {
        "job_id": jb_id,
        "submission_id": h["submission_id"],
        "problem_id": int(h["problem_id"]),
        "language": int(h["language"]),
        "code_minio_path": h["code_minio_path"],
        "checker": h["checker"],
        "tasks": json.loads(h["tasks_meta_json"]),
    }
