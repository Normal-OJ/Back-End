"""Job lifecycle: enqueue / claim / renew / reclaim / complete / abort / JE land
(spec §7.2–§7.5, §8, §9).

This is the Python skin over the Lua state transitions in ``scripts.py``. Every
transition is atomic in Redis; this layer only picks the ``now`` clock (Python
``time.time()``, passed into every script via ARGV — never a server-side TIME),
walks ``jobs:leased`` for the time-gated orphan scan, holds the per-submission
lock around a landing, and shapes payloads.

Slices 2 and 3 of the delivery plan (§15.2) — dark: nothing calls these yet.
The Mongo side is not wired either: result/JE landing is done through injected
callables so this layer stays payload- and storage-agnostic (the keystone slice
closes over ``process_result`` / a JE marker). The remaining seam is the
presigned ``code_url`` signing on the payload plus HTTP status mapping, both
slice 4; they are called out at their seams below.
"""

import contextlib
import enum
import logging
import threading
import time
from typing import Callable, Dict, Optional

from ulid import ULID
import redis.exceptions

from mongo.utils import RedisCache
from . import params
from . import redis_keys
from . import scripts

logger = logging.getLogger(__name__)

JOB_ID_PREFIX = 'jb_'


class CompleteOutcome(enum.Enum):
    """Result of a complete attempt; slice 4 maps these to HTTP status.

    LANDED / STALE_DROPPED → 204 (a stale drop MUST be logged — INV4);
    NOT_OWNER → 409; GONE → 404; BUSY / LAND_FAILED → retryable 5xx.
    """
    LANDED = enum.auto()
    STALE_DROPPED = enum.auto()
    NOT_OWNER = enum.auto()
    GONE = enum.auto()
    BUSY = enum.auto()
    LAND_FAILED = enum.auto()


class AbortOutcome(enum.Enum):
    """Result of an abort attempt; slice 4 maps these to HTTP status.

    REQUEUED / STALE_DROPPED / CONVERGED → 202; NOT_OWNER → 409; GONE → 404.
    """
    REQUEUED = enum.auto()
    STALE_DROPPED = enum.auto()
    CONVERGED = enum.auto()
    NOT_OWNER = enum.auto()
    GONE = enum.auto()


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


@contextlib.contextmanager
def _submission_lock(client, submission_id: str):
    """Non-blocking per-submission landing lock (INV3); yields the acquired flag.

    Landing callers must bail out on False rather than wait: complete answers
    BUSY (the runner retries), the JE sweep leaves the job for the next window.
    A Mongo landing has no completion bound, so a fixed TTL alone cannot hold
    INV3 — a watchdog thread extends the lock every TTL/3 for as long as the
    landing runs, and the TTL only bounds crash recovery. The watchdog is
    stopped and joined before release so an extend can never race the release.
    """
    lock = client.lock(
        redis_keys.submission_job_lock(submission_id),
        timeout=params.JOB_LOCK_TTL_SEC,
        blocking=False,
        # The token must live on the Lock instance, not in thread-local
        # storage: the watchdog extends from its own thread, and each Lock
        # object is private to one landing call anyway.
        thread_local=False,
    )
    acquired = lock.acquire()
    if not acquired:
        yield False
        return
    stop = threading.Event()
    watchdog = threading.Thread(
        target=_keep_lock_alive,
        args=(lock, stop, submission_id),
        daemon=True,
    )
    watchdog.start()
    try:
        yield True
    finally:
        stop.set()
        watchdog.join()
        try:
            lock.release()
        except redis.exceptions.LockError:
            pass


def _keep_lock_alive(lock, stop: threading.Event, submission_id: str) -> None:
    """Extend the landing lock until told to stop (the INV3 watchdog).

    An extend that fails means exclusivity is already lost (the key evaporated —
    Redis data loss, or a pathological stall past the TTL): nothing mid-flight
    can be safely undone, so log loudly and let delete-after-write plus the
    landing contract (re-run tolerance, spec §17.2) absorb the fallout. Closing
    this residual for real takes a fencing token / conditional write on the
    Mongo side — a pre-keystone task, out of this layer's reach.
    """
    while not stop.wait(params.JOB_LOCK_TTL_SEC / 3.0):
        try:
            lock.extend(params.JOB_LOCK_TTL_SEC, replace_ttl=True)
        except redis.exceptions.LockError:
            logger.error('landing lock lost mid-write: submission %s',
                         submission_id)
            return


def _sid_or_reap(client, job_id: str) -> Optional[str]:
    """Read a job's submission_id (the lock name), reaping unidentifiable jobs.

    A vanished hash leaves at most a ghost index entry; a hash that exists but
    lost submission_id can never pass a currency check again and the hash has no
    TTL — destroy both (same policy as the Lua side) so neither lingers
    unindexed forever.
    """
    sid = _decode(client.hget(redis_keys.job(job_id), 'submission_id'))
    if sid is not None:
        return sid
    pipe = client.pipeline()
    pipe.delete(redis_keys.job(job_id))
    pipe.srem(redis_keys.JOBS_LEASED, job_id)
    pipe.execute()
    return None


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


def claim_next_job(
    runner_id: str,
    land_je: Optional[Callable[[str], None]] = None,
) -> Optional[Dict]:
    """Hand ``runner_id`` its next job, or None when there is nothing to do.

    Order matches spec §7.3: first a time-gated orphan scan (at most one runner
    per ``ORPHAN_SCAN_INTERVAL_SEC`` window), whose first successful reclaim goes
    straight to this caller; otherwise fall through to the pending queue.

    ``land_je`` is the injected JE marker (keystone wires it to Mongo); the scan
    uses it to converge attempts-exhausted orphans. None keeps the scan dark —
    exhausted orphans are left in place for a later, wired call to sweep.
    """
    now = _now()
    client = _redis()

    reclaimed = _orphan_scan(client, runner_id, now, land_je)
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


def complete_job(
    runner_id: str,
    job_id: str,
    land_result: Callable[[str], None],
) -> CompleteOutcome:
    """Land ``runner_id``'s result for ``job_id`` (spec §7.4; INV1/INV3/INV4).

    ``land_result(submission_id)`` performs the Mongo landing and raises on
    failure (the keystone closes over the request's tasks payload; this layer
    stays payload-agnostic). The whole landing runs under the per-submission lock
    (INV3): mark completing, land, then delete-after-write. A lease expiring
    during a slow write stays deliberately reclaimable — the lock plus the
    delete-after-write ordering, not lease extension, is what bounds double
    writes (spec §9).

    Contract: this layer guarantees at-least-once invocation, never
    exactly-once. ``land_result`` must therefore tolerate re-invocation both as
    a full re-run after a reclaim and as a retry after its own partial write
    (LAND_FAILED → the runner resends). Verifying/fixing ``process_result`` for
    this is the keystone's pre-wiring task (spec §17.2, ADR-0003 Consequences).
    """
    client = _redis()
    scr = scripts.load(client)

    sid = _sid_or_reap(client, job_id)
    if sid is None:
        return CompleteOutcome.GONE

    with _submission_lock(client, sid) as acquired:
        if not acquired:
            return CompleteOutcome.BUSY
        begin = scr.complete_begin(
            keys=[redis_keys.JOBS_LEASED,
                  redis_keys.job(job_id)],
            args=[job_id, runner_id],
        )
        if begin == -2:
            return CompleteOutcome.GONE
        if begin == 0:
            return CompleteOutcome.NOT_OWNER
        if begin == -1:
            logger.warning(
                'stale result dropped: job %s submission %s runner %s', job_id,
                sid, runner_id)
            return CompleteOutcome.STALE_DROPPED

        try:
            land_result(sid)
        except Exception as exc:
            logger.exception('result landing failed: job %s submission %s',
                             job_id, sid)
            scr.complete_restore(
                keys=[redis_keys.job(job_id)],
                args=[runner_id, str(exc)[:200]],
            )
            return CompleteOutcome.LAND_FAILED

        scr.complete_finish(
            keys=[redis_keys.JOBS_LEASED,
                  redis_keys.job(job_id)],
            args=[job_id],
        )
        return CompleteOutcome.LANDED


def abort_job(
    runner_id: str,
    job_id: str,
    reason: str,
    land_je: Optional[Callable[[str], None]] = None,
) -> AbortOutcome:
    """Requeue or converge ``job_id`` on a runner-reported abort (spec §7.5, INV5).

    ``drain`` never counts against attempts; ``prep_failed`` / ``rejected`` count
    toward the poison ceiling. When counting tips the job to MAX_ATTEMPTS it
    converges to JE: the abort is accepted regardless of whether the JE landing
    succeeds — a failed landing leaves the job in place for the orphan-scan sweep
    to retry (INV1).
    """
    if reason not in ('drain', 'prep_failed', 'rejected'):
        raise ValueError(f'invalid abort reason: {reason!r}')

    client = _redis()

    sid = _sid_or_reap(client, job_id)
    if sid is None:
        return AbortOutcome.GONE

    result = scripts.load(client).abort_requeue(
        keys=[
            redis_keys.JOBS_LEASED,
            redis_keys.JOBS_PENDING,
            redis_keys.job(job_id),
        ],
        args=[job_id, runner_id, reason, params.MAX_ATTEMPTS],
    )
    if result == 1:
        return AbortOutcome.REQUEUED
    if result == -1:
        logger.warning('stale abort dropped: job %s submission %s runner %s',
                       job_id, sid, runner_id)
        return AbortOutcome.STALE_DROPPED
    if result == -2:
        return AbortOutcome.GONE
    if result == 0:
        return AbortOutcome.NOT_OWNER

    _try_land_je(sid, job_id, land_je)
    return AbortOutcome.CONVERGED


def _orphan_scan(
    client,
    runner_id: str,
    now: float,
    land_je: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    """Time-gated sweep of ``jobs:leased``; return an id reclaimed for the caller.

    The ``SET NX EX`` gate on ``dispatch:last_recovery`` lets at most one scan run
    per window (spec §7.3 step 1). Within a winning scan, each expired candidate
    is offered to ``reclaim_expired``: the first ``1`` (reclaimed to this caller)
    is returned immediately; a ``-1`` (attempts exhausted) candidate is converged
    via ``_try_land_je`` and the scan keeps looking for reclaimable work for the
    caller. Iteration is over a materialized snapshot, so a landing that unindexes
    a member mid-scan is harmless.
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
        if result == -1:
            sid = _decode(client.hget(redis_keys.job(job_id), 'submission_id'))
            if sid is not None:
                _try_land_je(sid, job_id, land_je)
    return None


def _try_land_je(
    submission_id: str,
    job_id: str,
    land_je: Optional[Callable[[str], None]],
) -> bool:
    """Land a JE marker for an attempts-exhausted job, or leave it for a retry.

    Runs under the same per-submission lock as ``complete_job``. If a rejudge has
    moved current_job past this job it is a superseded orphan: destroy it (pointer
    untouched). Otherwise land the JE; on landing failure the job is left in place
    — still in ``jobs:leased`` with an expired lease, so the next time-gated scan
    retries the landing (INV1). ``land_je`` None (not wired) touches nothing.
    """
    if land_je is None:
        logger.debug('JE landing skipped (not wired): job %s submission %s',
                     job_id, submission_id)
        return False

    client = _redis()
    with _submission_lock(client, submission_id) as acquired:
        if not acquired:
            return False
        current = _decode(
            client.get(redis_keys.submission_current_job(submission_id)))
        if current != job_id:
            pipe = client.pipeline()
            pipe.delete(redis_keys.job(job_id))
            pipe.srem(redis_keys.JOBS_LEASED, job_id)
            pipe.execute()
            logger.warning('stale JE job destroyed: job %s submission %s',
                           job_id, submission_id)
            return True

        try:
            land_je(submission_id)
        except Exception:
            logger.exception('JE landing failed: job %s submission %s', job_id,
                             submission_id)
            return False

        scripts.load(client).complete_finish(
            keys=[redis_keys.JOBS_LEASED,
                  redis_keys.job(job_id)],
            args=[job_id],
        )
        logger.info('JE landed: job %s submission %s', job_id, submission_id)
        return True


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
