"""Job lifecycle: enqueue / claim / renew / reclaim (spec §7.2, §7.3, §8, §9).

This is the Python skin over the Lua state transitions in ``scripts.py``. Every
transition is atomic in Redis; this layer only picks the ``now`` clock (Python
``time.time()``, passed into every script via ARGV — never a server-side TIME),
walks ``jobs:leased`` for the time-gated orphan scan, and shapes payloads.

Slice 2 of the delivery plan (§15.2) — dark: nothing calls these yet. The
``complete``/``abort``/JE-landing transitions are slice 3; presigned ``code_url``
signing on the payload is slice 4. Both are called out at their seams below.
"""

import time
from typing import Dict, Optional

from ulid import ULID

from mongo.utils import RedisCache
from . import params
from . import redis_keys
from . import scripts

JOB_ID_PREFIX = 'jb_'

# One shared RedisCache instance, mirroring runner.py: under fakeredis each
# RedisCache owns an isolated dataset, so enqueue/claim/renew must share one to
# stay coherent; in production they all share the pooled real Redis anyway.
_cache: Optional[RedisCache] = None


def _redis():
    global _cache
    if _cache is None:
        _cache = RedisCache()
    return _cache.client


def _now() -> float:
    return time.time()


def _decode(value) -> Optional[str]:
    if value is None:
        return None
    return value.decode() if isinstance(value, bytes) else value


def enqueue_job(
    submission_id: str,
    problem_id: str,
    language: int,
    code_minio_path: str,
    checker: str,
    tasks_meta_json: str,
) -> str:
    """Enqueue a fresh judging job for ``submission_id`` (spec §8, §9).

    Writes the job hash, points ``submission:<sid>:current_job`` at it (last
    enqueue wins — that is exactly how a rejudge supersedes an in-flight job; the
    stale one is destroyed lazily on the dispatch side by ``claim_pending``, INV4,
    never proactively here), then LPUSHes onto the FIFO pending queue.
    """
    now = _now()
    job_id = JOB_ID_PREFIX + str(ULID())

    client = _redis()
    job_key = redis_keys.job(job_id)

    pipe = client.pipeline()
    pipe.hset(
        job_key,
        mapping={
            'submission_id': submission_id,
            'problem_id': problem_id,
            'language': language,
            'code_minio_path': code_minio_path,
            'checker': checker,
            'tasks_meta_json': tasks_meta_json,
            'leased_by': '',
            'lease_deadline': '0',
            'state': 'pending',
            'attempts': 0,
            'created_at': repr(now),
            'last_error': '',
        },
    )
    pipe.set(redis_keys.submission_current_job(submission_id), job_id)
    pipe.lpush(redis_keys.JOBS_PENDING, job_id)
    pipe.execute()

    return job_id


def claim_next_job(runner_id: str) -> Optional[Dict]:
    """Hand ``runner_id`` its next job, or None when there is nothing to do.

    Order matches spec §7.3: first a time-gated orphan scan (at most one runner
    per ``ORPHAN_SCAN_INTERVAL_SEC`` window), whose first successful reclaim goes
    straight to this caller; otherwise fall through to the pending queue.
    """
    now = _now()
    client = _redis()

    reclaimed = _orphan_scan(client, runner_id, now)
    if reclaimed is not None:
        return _payload(client, reclaimed)

    job_id = scripts.load(client).claim_pending(
        keys=[redis_keys.JOBS_PENDING, redis_keys.JOBS_LEASED],
        args=[now, runner_id, params.LEASE_TTL_SEC],
    )
    if job_id is None:
        return None
    return _payload(client, _decode(job_id))


def renew_lease(runner_id: str, job_id: str) -> bool:
    """Extend the lease on ``job_id`` iff ``runner_id`` still owns it (spec §7.2).

    Thin wrapper over ``renew_lease`` Lua; heartbeat wiring is slice 4.
    """
    now = _now()
    result = scripts.load(_redis()).renew_lease(
        keys=[redis_keys.JOBS_LEASED,
              redis_keys.job(job_id)],
        args=[job_id, runner_id, now, params.LEASE_TTL_SEC],
    )
    return result == 1


def _orphan_scan(client, runner_id: str, now: float) -> Optional[str]:
    """Time-gated sweep of ``jobs:leased``; return an id reclaimed for the caller.

    The ``SET NX EX`` gate on ``dispatch:last_recovery`` lets at most one scan run
    per window (spec §7.3 step 1). Within a winning scan, each expired candidate
    is offered to ``reclaim_expired``: the first ``1`` (reclaimed to this caller)
    is returned immediately; ``-1`` (attempts exhausted) candidates are skipped
    and left in place — the JE landing sweep that removes them is slice 3.
    """
    acquired = client.set(
        redis_keys.DISPATCH_LAST_RECOVERY,
        '1',
        nx=True,
        ex=params.ORPHAN_SCAN_INTERVAL_SEC,
    )
    if not acquired:
        return None

    reclaim = scripts.load(client).reclaim_expired
    for member in client.smembers(redis_keys.JOBS_LEASED):
        job_id = _decode(member)
        result = reclaim(
            keys=[redis_keys.JOBS_LEASED,
                  redis_keys.job(job_id)],
            args=[
                job_id,
                runner_id,
                now,
                params.LEASE_TTL_SEC,
                params.MAX_ATTEMPTS,
            ],
        )
        if result == 1:
            return job_id
    return None


def _payload(client, job_id: str) -> Optional[Dict]:
    """Shape a job hash into a claim payload (spec §7.3), or None if it vanished.

    Returns ``job_id`` plus the raw hash fields the HTTP layer will need. Typed
    coercion and the presigned ``code_url`` are slice 4's concern, not this one's.
    """
    raw = client.hgetall(redis_keys.job(job_id))
    if not raw:
        return None
    fields: Dict[str, Optional[str]] = {
        _decode(k): _decode(v)
        for k, v in raw.items()
    }
    fields['job_id'] = job_id
    return fields
