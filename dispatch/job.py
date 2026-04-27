"""Job lifecycle: enqueue, claim (pending + orphan reclaim), complete."""
import json
from datetime import datetime, timezone
from typing import Optional

from ulid import ULID

from mongo.utils import RedisCache
from .config import MAX_ATTEMPTS
from .redis_keys import job_key, JOBS_PENDING, JOBS_LEASED
from .runner import is_alive
from .scripts import reclaim_orphan_atomic


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_tasks_meta(submission) -> list[dict]:
    """Extract testcase metadata from submission for runner."""
    tasks = submission.problem.test_case_info.get("tasks", [])
    return [{
        "task_id": idx,
        "case_count": t.get("caseCount", 0),
        "memory_limit": t.get("memoryLimit", 0),
        "time_limit": t.get("timeLimit", 0),
    } for idx, t in enumerate(tasks)]


def enqueue_job(submission) -> str:
    """Create a Job from a Submission and push to pending queue. Returns jb_id."""
    jb_id = f"jb_{ULID()}"
    rds = RedisCache().client

    rds.hset(job_key(jb_id),
             mapping={
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
        2. Scan leased jobs for orphans (owner not alive) and try to reclaim
           one atomically.
        3. If neither yields a job, return None.
    """
    rds = RedisCache().client

    # Step 1: pending queue
    jb_id_bytes = rds.rpop(JOBS_PENDING)
    if jb_id_bytes is not None:
        jb_id = jb_id_bytes.decode()
        _assign_to_runner(jb_id, rn_id)
        return _build_payload(jb_id)

    # Step 2: orphan reclaim — scan leased jobs for dead owners
    leased_ids = rds.smembers(JOBS_LEASED)
    for orphan_id_bytes in leased_ids:
        orphan_id = orphan_id_bytes.decode()
        owner_bytes = rds.hget(job_key(orphan_id), "leased_by")
        if owner_bytes is None:
            continue
        owner = owner_bytes.decode()
        if is_alive(owner):
            continue
        # Owner is dead. Try to atomically reclaim.
        reclaim_result = reclaim_orphan_atomic(
            jb_id=orphan_id,
            expected_owner=owner,
            new_owner=rn_id,
            max_attempts=MAX_ATTEMPTS,
        )
        if reclaim_result == 1:
            return _build_payload(orphan_id)
        if reclaim_result == -1:
            _on_attempts_exhausted(orphan_id)
            # continue to look at other orphans
        # 0 = lost the race, try next orphan
    return None


def _assign_to_runner(jb_id: str, rn_id: str) -> None:
    """Mark job as leased to this runner (called after RPOP from pending)."""
    rds = RedisCache().client
    rds.hset(job_key(jb_id),
             mapping={
                 "leased_by": rn_id,
                 "leased_at": _now_iso(),
             })
    rds.hincrby(job_key(jb_id), "attempts", 1)
    rds.sadd(JOBS_LEASED, jb_id)


def _on_attempts_exhausted(jb_id: str) -> None:
    """When a job exhausts max_attempts, mark its Submission as Judge Error.

    Lua script already removed jb_id from JOBS_LEASED set. This function
    cleans the job hash and updates the Submission's status field.
    """
    # Local import to avoid circular dependency at module load time.
    from mongo import Submission

    rds = RedisCache().client
    submission_id_bytes = rds.hget(job_key(jb_id), "submission_id")
    if submission_id_bytes is None:
        rds.delete(job_key(jb_id))
        return
    submission_id = submission_id_bytes.decode()
    try:
        sub = Submission(submission_id)
        if sub:
            sub.update(status=6)  # JE
    except Exception:
        pass
    finally:
        rds.delete(job_key(jb_id))


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


def complete_job(
    rn_id: str,
    jb_id: str,
    tasks: list,
    process_result,
) -> str:
    """Process a completed job. Returns one of: 'ok', 'wrong_owner', 'not_found'.

    Args:
        rn_id: The runner claiming completion.
        jb_id: The job id.
        tasks: Result tasks array (passed through to process_result).
        process_result: Callable(submission_id_str, tasks) -> None. Injected so
            this module doesn't depend directly on mongo.Submission.
    """
    rds = RedisCache().client
    h = rds.hgetall(job_key(jb_id))
    if not h:
        return "not_found"
    leased_by = h.get(b"leased_by")
    if leased_by is None or leased_by.decode() != rn_id:
        return "wrong_owner"

    submission_id = h[b"submission_id"].decode()
    process_result(submission_id, tasks)

    rds.delete(job_key(jb_id))
    rds.srem(JOBS_LEASED, jb_id)
    return "ok"
