"""Centralized Redis key naming for the pull-dispatch namespace (spec §8).

Pure constants and functions — no I/O. Job-related keys are defined now even
though this slice does not use them, so the whole §8 schema lives in one place.
"""

# --- identity (soft state; ADR-0004) ------------------------------------
# ZSET: member=rn_id, score=last heartbeat epoch
RUNNERS_REGISTERED = 'runners:registered'

# --- job queue ----------------------------------------------------------
JOBS_PENDING = 'jobs:pending'  # LIST of pending jb_id
JOBS_LEASED = 'jobs:leased'  # SET of leased jb_id
DISPATCH_LAST_RECOVERY = 'dispatch:last_recovery'  # STRING time gate (SET NX EX)


def runner_meta(runner_id: str) -> str:
    """HASH {name, registered_at, registration_ip}, TTL 7d."""
    return f'runner:{runner_id}:meta'


def runner_token_hash(runner_id: str) -> str:
    """STRING SHA-256(rk_token), TTL 7d."""
    return f'runner:{runner_id}:token_hash'


def runner_alive(runner_id: str) -> str:
    """STRING "1", TTL 30s — monitoring only, never used for decisions."""
    return f'runner:{runner_id}:alive'


def job(job_id: str) -> str:
    """HASH holding a job's full state."""
    return f'job:{job_id}'


def submission_current_job(submission_id: str) -> str:
    """STRING currency pointer (INV4)."""
    return f'submission:{submission_id}:current_job'


def submission_job_lock(submission_id: str) -> str:
    """Per-submission serialization lock (INV3)."""
    return f'submission:{submission_id}:job_lock'
