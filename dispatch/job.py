"""Job lifecycle: enqueue, claim (pending + orphan reclaim), complete."""
from contextlib import contextmanager
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from ulid import ULID

from mongo.utils import RedisCache
from .config import JOB_LEASE_TTL_SEC, MAX_ATTEMPTS, SUBMISSION_JOB_LOCK_TTL_SEC
from .redis_keys import (
    job_key,
    submission_current_job_key,
    submission_job_lock_key,
    JOBS_PENDING,
    JOBS_LEASED,
)
from .runner import is_alive
from .scripts import claim_pending_atomic, reclaim_orphan_atomic


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lease_deadline() -> str:
    return (datetime.now(timezone.utc) +
            timedelta(seconds=JOB_LEASE_TTL_SEC)).isoformat()


def _is_lease_expired(deadline: bytes | str | None) -> bool:
    if deadline is None:
        return False
    if isinstance(deadline, bytes):
        deadline = deadline.decode()
    try:
        return datetime.fromisoformat(deadline) <= datetime.now(timezone.utc)
    except ValueError:
        return True


@contextmanager
def _submission_job_lock(submission_id: str):
    rds = RedisCache().client
    lock = rds.lock(
        submission_job_lock_key(submission_id),
        timeout=SUBMISSION_JOB_LOCK_TTL_SEC,
        blocking_timeout=0,
    )
    acquired = lock.acquire(blocking=False)
    if not acquired:
        yield False
        return
    try:
        yield True
    finally:
        lock.release()


def submission_job_lock(submission_id: str):
    return _submission_job_lock(submission_id)


def _current_job_matches(rds, submission_id: str, jb_id: str) -> bool:
    current_jb_id = rds.get(submission_current_job_key(submission_id))
    return current_jb_id is not None and current_jb_id.decode() == jb_id


def _delete_current_job_if_matches(rds, submission_id: str,
                                   jb_id: str) -> None:
    current_jb_id = rds.get(submission_current_job_key(submission_id))
    if current_jb_id is not None and current_jb_id.decode() == jb_id:
        rds.delete(submission_current_job_key(submission_id))


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
    submission_id = str(submission.id)

    rds.hset(job_key(jb_id),
             mapping={
                 "submission_id": submission_id,
                 "problem_id": submission.problem_id,
                 "language": submission.language,
                 "code_minio_path": submission.code_minio_path,
                 "checker": 'print("not implement yet. qaq")',
                 "tasks_meta_json": json.dumps(_build_tasks_meta(submission)),
                 "attempts": 0,
                 "state": "pending",
                 "created_at": _now_iso(),
             })
    rds.set(submission_current_job_key(submission_id), jb_id)
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
    jb_id = claim_pending_atomic(rn_id, JOB_LEASE_TTL_SEC)
    if jb_id is not None:
        return _build_payload(jb_id)

    # Step 2: orphan reclaim — scan leased jobs for dead owners
    leased_ids = rds.smembers(JOBS_LEASED)
    for orphan_id_bytes in leased_ids:
        orphan_id = orphan_id_bytes.decode()
        owner_bytes = rds.hget(job_key(orphan_id), "leased_by")
        state = rds.hget(job_key(orphan_id), "state")
        if state is not None and state != b"leased":
            continue
        if owner_bytes is None:
            continue
        owner = owner_bytes.decode()
        if is_alive(owner) and not _is_lease_expired(
                rds.hget(job_key(orphan_id), "lease_deadline")):
            continue
        # Owner is dead. Try to atomically reclaim.
        reclaim_result = reclaim_orphan_atomic(
            jb_id=orphan_id,
            expected_owner=owner,
            new_owner=rn_id,
            max_attempts=MAX_ATTEMPTS,
            lease_ttl_sec=JOB_LEASE_TTL_SEC,
        )
        if reclaim_result == 1:
            return _build_payload(orphan_id)
        if reclaim_result == -1:
            _on_attempts_exhausted(orphan_id)
            # continue to look at other orphans
        # 0 = lost the race, try next orphan
    return None


def renew_leases(rn_id: str) -> int:
    """Extend lease_deadline for all jobs currently leased by rn_id.

    Called from the heartbeat endpoint so a live runner's long-running
    jobs are never reclaimed as orphans.
    """
    rds = RedisCache().client
    renewed = 0
    for jb_id_bytes in rds.smembers(JOBS_LEASED):
        jb_id = jb_id_bytes.decode()
        leased_by, state = rds.hmget(job_key(jb_id), "leased_by", "state")
        if leased_by is None or leased_by.decode() != rn_id:
            continue
        if state is not None and state != b"leased":
            continue
        rds.hset(job_key(jb_id), "lease_deadline", _lease_deadline())
        renewed += 1
    return renewed


def _assign_to_runner(jb_id: str, rn_id: str) -> None:
    """Mark job as leased to this runner (called after RPOP from pending)."""
    rds = RedisCache().client
    rds.hset(job_key(jb_id),
             mapping={
                 "leased_by": rn_id,
                 "leased_at": _now_iso(),
                 "lease_deadline": _lease_deadline(),
                 "state": "leased",
             })
    rds.hincrby(job_key(jb_id), "attempts", 1)
    rds.sadd(JOBS_LEASED, jb_id)


def _on_attempts_exhausted(jb_id: str) -> str:
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
        return "ok"
    submission_id = submission_id_bytes.decode()
    with _submission_job_lock(submission_id) as acquired:
        if not acquired:
            rds.sadd(JOBS_LEASED, jb_id)
            return "busy"
        try:
            sub = Submission(submission_id)
            if sub:
                sub.update(status=6)  # JE
            _delete_current_job_if_matches(rds, submission_id, jb_id)
        except Exception:
            pass
        finally:
            rds.delete(job_key(jb_id))
    return "ok"


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
    """Process a completed job.

    Returns one of: 'ok', 'wrong_owner', 'not_found', 'stale', 'busy',
    'lease_expired'.

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
    if h.get(b"state") != b"leased":
        return "wrong_owner"
    if _is_lease_expired(h.get(b"lease_deadline")):
        return "lease_expired"

    submission_id = h[b"submission_id"].decode()
    with _submission_job_lock(submission_id) as acquired:
        if not acquired:
            return "busy"
        h = rds.hgetall(job_key(jb_id))
        if not h:
            return "not_found"
        leased_by = h.get(b"leased_by")
        if leased_by is None or leased_by.decode() != rn_id:
            return "wrong_owner"
        if h.get(b"state") != b"leased":
            return "wrong_owner"
        if _is_lease_expired(h.get(b"lease_deadline")):
            return "lease_expired"
        if not _current_job_matches(rds, submission_id, jb_id):
            rds.delete(job_key(jb_id))
            rds.srem(JOBS_LEASED, jb_id)
            return "stale"

        rds.hset(job_key(jb_id), "state", "completing")
        try:
            process_result(submission_id, tasks)
        except Exception:
            rds.hset(job_key(jb_id),
                     mapping={
                         "state": "leased",
                         "lease_deadline": _lease_deadline(),
                     })
            raise

        rds.delete(job_key(jb_id))
        rds.srem(JOBS_LEASED, jb_id)
        _delete_current_job_if_matches(rds, submission_id, jb_id)
        return "ok"


def abort_job(rn_id: str, jb_id: str, reason: str = "") -> str:
    """Release a runner-owned job without completing it.

    Returns one of: 'requeued', 'exhausted', 'wrong_owner', 'not_found',
    'stale', 'busy'.
    """
    rds = RedisCache().client
    h = rds.hgetall(job_key(jb_id))
    if not h:
        return "not_found"
    leased_by = h.get(b"leased_by")
    if leased_by is None or leased_by.decode() != rn_id:
        return "wrong_owner"
    if h.get(b"state") != b"leased":
        return "wrong_owner"

    submission_id = h[b"submission_id"].decode()
    if not _current_job_matches(rds, submission_id, jb_id):
        rds.delete(job_key(jb_id))
        rds.srem(JOBS_LEASED, jb_id)
        return "stale"
    if int(h.get(b"attempts", b"0")) >= MAX_ATTEMPTS:
        rds.srem(JOBS_LEASED, jb_id)
        if _on_attempts_exhausted(jb_id) == "busy":
            return "busy"
        return "exhausted"

    rds.hdel(job_key(jb_id), "leased_by", "leased_at", "lease_deadline")
    rds.hset(job_key(jb_id), "state", "pending")
    if reason:
        rds.hset(job_key(jb_id), "last_error", reason)
    rds.srem(JOBS_LEASED, jb_id)
    rds.lpush(JOBS_PENDING, jb_id)
    return "requeued"
