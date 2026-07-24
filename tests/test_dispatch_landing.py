import logging
import threading
import time

import pytest

from config import settings
from mongo.utils import RedisCache
from dispatch import params, redis_keys, scripts
from dispatch import job as job_mod
from dispatch.job import CompleteOutcome, AbortOutcome


@pytest.fixture(autouse=True, scope='session')
def setup_minio():
    # Shadow conftest's Docker/MinIO session fixture: these landing unit tests
    # touch only fakeredis, so they must not require a container engine.
    yield


@pytest.fixture(autouse=True)
def fresh_fakeredis(monkeypatch):
    # Force each test onto a fresh FakeStrictRedis: RedisCache caches its
    # connection pool on the class and dispatch caches one RedisCache instance.
    # REDIS_PORT must be None in settings so RedisCache falls back to fakeredis.
    monkeypatch.setattr(settings, 'REDIS_HOST', None)
    monkeypatch.setattr(settings, 'REDIS_PORT', None)
    RedisCache.POOL = None
    job_mod._cache = None
    yield
    RedisCache.POOL = None
    job_mod._cache = None


def _enqueue(submission_id='sn_1', problem_id='pb_1', language=2):
    return job_mod.enqueue_job(
        submission_id=submission_id,
        problem_id=problem_id,
        language=language,
        code_minio_path=f'{submission_id}/main.py',
        checker='diff',
        tasks_meta_json='[]',
    )


def _client():
    return job_mod._redis()


def _hash(job_id):
    raw = _client().hgetall(redis_keys.job(job_id))
    return {k.decode(): v.decode() for k, v in raw.items()}


def _reclaim(job_id, runner, now):
    return scripts.load(_client()).reclaim_expired(
        keys=[redis_keys.JOBS_LEASED,
              redis_keys.job(job_id)],
        args=[job_id, runner, now, params.LEASE_TTL_SEC, params.MAX_ATTEMPTS],
    )


def _expire(job_id, deadline='0'):
    _client().hset(redis_keys.job(job_id), 'lease_deadline', deadline)


def _leased(job_id):
    return _client().sismember(redis_keys.JOBS_LEASED, job_id)


def _pending():
    return [
        m.decode() for m in _client().lrange(redis_keys.JOBS_PENDING, 0, -1)
    ]


def _current(submission_id):
    v = _client().get(redis_keys.submission_current_job(submission_id))
    return v.decode() if v is not None else None


class Writer:
    """Injected landing callable; records the sids it lands.

    ``side_effect`` runs mid-write (to simulate a concurrent reclaim / rejudge);
    ``raises`` fires afterwards to model a Mongo write failure; ``sleep`` widens
    the write window so a racing caller is guaranteed to collide on the lock.
    """

    def __init__(self, side_effect=None, raises=None, sleep=0.0):
        self.calls = []
        self._side_effect = side_effect
        self._raises = raises
        self._sleep = sleep

    def __call__(self, submission_id):
        self.calls.append(submission_id)
        if self._sleep:
            time.sleep(self._sleep)
        if self._side_effect is not None:
            self._side_effect()
        if self._raises is not None:
            raise self._raises


# --- INV3 complete: happy path ------------------------------------------


def test_complete_happy_path_lands_once_and_cleans_up(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    job_mod.claim_next_job('rn_a')

    writer = Writer()
    assert job_mod.complete_job('rn_a', job_id,
                                writer) == CompleteOutcome.LANDED

    assert writer.calls == ['sn_1']  # landed exactly once, with the sid
    assert _client().exists(redis_keys.job(job_id)) == 0
    assert not _leased(job_id)
    assert _current('sn_1') is None


def test_second_complete_after_landing_is_gone(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    job_mod.claim_next_job('rn_a')

    first = Writer()
    assert job_mod.complete_job('rn_a', job_id,
                                first) == CompleteOutcome.LANDED

    second = Writer()
    assert job_mod.complete_job('rn_a', job_id, second) == CompleteOutcome.GONE
    assert second.calls == []


def test_concurrent_completes_exactly_one_lands(monkeypatch):
    # Two completes race under the per-submission lock; the writer sleeps so the
    # window is wide. Exactly one LANDED, the loser BUSY (non-blocking acquire
    # failed) or GONE (winner finished first); the writer runs exactly once.
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    job_mod.claim_next_job('rn_a')

    writer = Writer(sleep=0.2)
    barrier = threading.Barrier(2)
    results = {}

    def racer(name):
        barrier.wait()
        results[name] = job_mod.complete_job('rn_a', job_id, writer)

    threads = [
        threading.Thread(target=racer, args=(n, )) for n in ('t1', 't2')
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    landed = [o for o in results.values() if o == CompleteOutcome.LANDED]
    assert len(landed) == 1
    loser = next(o for o in results.values() if o != CompleteOutcome.LANDED)
    assert loser in (CompleteOutcome.BUSY, CompleteOutcome.GONE)
    assert len(writer.calls) == 1


def test_complete_lock_pre_held_returns_busy(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    job_mod.claim_next_job('rn_a')

    _client().set(redis_keys.submission_job_lock('sn_1'),
                  'held')  # someone owns it

    writer = Writer()
    assert job_mod.complete_job('rn_a', job_id, writer) == CompleteOutcome.BUSY
    assert writer.calls == []
    assert _hash(job_id)['state'] == 'leased'  # untouched


def test_complete_reclaim_during_write_still_single_writer(monkeypatch):
    # The lease expires and the job is reclaimed to a new runner mid-write, then
    # the write succeeds: the result still lands and the job is destroyed. The
    # new runner's later complete finds nothing — exactly one landing overall.
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    job_mod.claim_next_job('rn_a')

    def reclaim_away():
        _expire(job_id)
        assert _reclaim(job_id, 'rn_new', now=5000.0) == 1

    writer = Writer(side_effect=reclaim_away)
    assert job_mod.complete_job('rn_a', job_id,
                                writer) == CompleteOutcome.LANDED
    assert _client().exists(redis_keys.job(job_id)) == 0

    rerun = Writer()
    assert job_mod.complete_job('rn_new', job_id,
                                rerun) == CompleteOutcome.GONE
    assert rerun.calls == []


# --- INV4 currency ------------------------------------------------------


def test_complete_stale_is_dropped_not_landed(monkeypatch, caplog):
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job1 = _enqueue(submission_id='sn_x')
    job_mod.claim_next_job('rn_a')
    job2 = _enqueue(submission_id='sn_x')  # rejudge moves the pointer

    writer = Writer()
    with caplog.at_level(logging.WARNING):
        outcome = job_mod.complete_job('rn_a', job1, writer)

    assert outcome == CompleteOutcome.STALE_DROPPED
    assert writer.calls == []
    assert _client().exists(redis_keys.job(job1)) == 0  # destroyed
    assert not _leased(job1)
    assert _current('sn_x') == job2  # pointer untouched
    assert 'stale result dropped' in caplog.text
    assert job1 in caplog.text


def test_complete_rejudge_during_write_does_not_delete_new_pointer(
        monkeypatch):
    # A rejudge fires while Mongo is written: current_job advances to a new job.
    # The write succeeds, the old job is deleted, but the compare-and-delete must
    # leave the NEW pointer (and its job) intact.
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job1 = _enqueue(submission_id='sn_x')
    job_mod.claim_next_job('rn_a')

    new_job = {}

    def rejudge():
        new_job['id'] = _enqueue(submission_id='sn_x')

    writer = Writer(side_effect=rejudge)
    assert job_mod.complete_job('rn_a', job1, writer) == CompleteOutcome.LANDED

    job2 = new_job['id']
    assert _client().exists(redis_keys.job(job1)) == 0
    assert _current('sn_x') == job2  # new pointer survived
    assert _client().exists(redis_keys.job(job2)) == 1
    assert job2 in _pending()


# --- INV1 complete failure ----------------------------------------------


def test_complete_land_failure_restores_and_retries(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    job_mod.claim_next_job('rn_a')

    failing = Writer(raises=RuntimeError('mongo down'))
    assert job_mod.complete_job('rn_a', job_id,
                                failing) == CompleteOutcome.LAND_FAILED

    h = _hash(job_id)
    assert h['state'] == 'leased'  # restored
    assert h['last_error'] == 'mongo down'
    assert _leased(job_id)
    assert _current('sn_1') == job_id  # pointer intact

    ok = Writer()
    assert job_mod.complete_job('rn_a', job_id, ok) == CompleteOutcome.LANDED
    assert ok.calls == ['sn_1']
    assert _client().exists(redis_keys.job(job_id)) == 0
    assert not _leased(job_id)
    assert _current('sn_1') is None


def test_complete_restore_refuses_to_stomp_new_owner(monkeypatch):
    # The lease expires and the job is reclaimed to rn_new before the write
    # raises: restore must NOT overwrite the new owner's state.
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    job_mod.claim_next_job('rn_a')  # attempts = 1

    def reclaim_then_boom():
        _expire(job_id)
        assert _reclaim(job_id, 'rn_new', now=5000.0) == 1  # attempts = 2

    failing = Writer(side_effect=reclaim_then_boom,
                     raises=RuntimeError('boom'))
    assert job_mod.complete_job('rn_a', job_id,
                                failing) == CompleteOutcome.LAND_FAILED

    h = _hash(job_id)
    assert h['leased_by'] == 'rn_new'  # restore left the new owner alone
    assert h['state'] == 'leased'
    assert h['attempts'] == '2'  # the reclaim bump stands


# --- ownership / existence ----------------------------------------------


def test_complete_non_owner_is_refused(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    job_mod.claim_next_job('rn_a')

    writer = Writer()
    assert job_mod.complete_job('rn_b', job_id,
                                writer) == CompleteOutcome.NOT_OWNER
    assert writer.calls == []
    assert _hash(job_id)['leased_by'] == 'rn_a'  # untouched


def test_complete_unknown_job_is_gone_and_resurrects_nothing():
    writer = Writer()
    assert job_mod.complete_job('rn_a', 'jb_missing',
                                writer) == CompleteOutcome.GONE
    assert writer.calls == []
    assert _client().exists(redis_keys.job('jb_missing')) == 0
    assert not _leased('jb_missing')


def test_complete_corrupt_hash_without_sid_is_reaped(monkeypatch):
    # A leased hash that lost submission_id can never pass a currency check and
    # has no TTL: the pre-lock read must destroy it (hash AND index), not just
    # unindex it and leave the hash to linger forever.
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    job_mod.claim_next_job('rn_a')
    _client().hdel(redis_keys.job(job_id), 'submission_id')

    writer = Writer()
    assert job_mod.complete_job('rn_a', job_id, writer) == CompleteOutcome.GONE
    assert writer.calls == []
    assert _client().exists(redis_keys.job(job_id)) == 0
    assert not _leased(job_id)


def test_abort_corrupt_hash_without_sid_is_reaped(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    job_mod.claim_next_job('rn_a')
    _client().hdel(redis_keys.job(job_id), 'submission_id')

    assert job_mod.abort_job('rn_a', job_id, 'drain') == AbortOutcome.GONE
    assert _client().exists(redis_keys.job(job_id)) == 0
    assert not _leased(job_id)
    assert _pending() == []  # reaped, not requeued


# --- abort matrix -------------------------------------------------------


def test_abort_drain_requeues_without_counting(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    job_mod.claim_next_job('rn_a')  # attempts = 1
    assert _hash(job_id)['attempts'] == '1'

    assert job_mod.abort_job('rn_a', job_id, 'drain') == AbortOutcome.REQUEUED

    h = _hash(job_id)
    # claim counted (attempts 0->1); drain refunds it — the drained execution
    # never ran a verdict, so the round-trip nets zero (spec §7.5).
    assert h['attempts'] == '0'
    assert h['state'] == 'pending'
    assert h['leased_by'] == ''
    assert h['lease_deadline'] == '0'
    assert h['last_error'] == 'abort:drain'
    assert job_id in _pending()
    assert not _leased(job_id)


def test_abort_drain_never_converges(monkeypatch):
    # Draining the same job forever must never converge to JE and must never
    # erode the retry budget: attempts is '1' while leased and refunded to '0'
    # after each drain requeue — bounded, never accumulating.
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    land_je = Writer()

    for _ in range(5):
        assert job_mod.claim_next_job(
            'rn_a')['job_id'] == job_id  # still claimable
        assert _hash(job_id)['attempts'] == '1'  # claim bump
        assert job_mod.abort_job('rn_a', job_id, 'drain',
                                 land_je) == AbortOutcome.REQUEUED
        assert _hash(job_id)['attempts'] == '0'  # refunded

    assert land_je.calls == []


def test_drain_preserves_full_budget_for_later_failures(monkeypatch):
    # After any number of drains, a genuinely failing execution path still gets
    # its full retry budget: the JE converges at exactly the same boundary a
    # never-drained job would (claim=1, reclaim=2, reclaim=3, then -1).
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    land_je = Writer()

    for _ in range(
            3):  # rolling restarts churn the job without spending budget
        job_mod.claim_next_job('rn_a')
        assert job_mod.abort_job('rn_a', job_id,
                                 'drain') == AbortOutcome.REQUEUED
    assert _hash(job_id)['attempts'] == '0'

    # now the real failure path, from a clean budget
    job_mod.claim_next_job('rn_a')  # attempts = 1
    assert _reclaim(job_id, 'rn_b', now=2000.0) == 1  # attempts = 2
    assert _reclaim(job_id, 'rn_c', now=3000.0) == 1  # attempts = 3
    # still one real attempt short of the ceiling: no JE yet
    assert land_je.calls == []
    _expire(job_id)
    _client().delete(redis_keys.DISPATCH_LAST_RECOVERY)

    monkeypatch.setattr(job_mod, '_now', lambda: 5000.0)
    assert job_mod.claim_next_job('rn_z', land_je=land_je) is None
    assert land_je.calls == ['sn_1']  # converged at the same boundary
    assert _client().exists(redis_keys.job(job_id)) == 0


@pytest.mark.parametrize('reason', ['prep_failed', 'rejected'])
def test_abort_counting_reason_requeues_below_max(monkeypatch, reason):
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    job_mod.claim_next_job('rn_a')  # attempts = 1

    assert job_mod.abort_job('rn_a', job_id, reason) == AbortOutcome.REQUEUED
    h = _hash(job_id)
    assert h['attempts'] == '2'  # counted, still below MAX_ATTEMPTS
    assert h['last_error'] == f'abort:{reason}'
    assert job_id in _pending()


def test_abort_countable_exhaustion_converges(monkeypatch):
    assert params.MAX_ATTEMPTS == 3
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    land_je = Writer()

    job_mod.claim_next_job('rn_a')  # attempts = 1
    assert job_mod.abort_job('rn_a', job_id, 'prep_failed',
                             land_je) == AbortOutcome.REQUEUED  # attempts = 2
    job_mod.claim_next_job('rn_a')  # attempts = 3
    assert job_mod.abort_job('rn_a', job_id, 'prep_failed',
                             land_je) == AbortOutcome.CONVERGED  # attempts = 4

    assert land_je.calls == ['sn_1']
    assert _client().exists(redis_keys.job(job_id)) == 0
    assert not _leased(job_id)
    assert job_id not in _pending()
    assert _current('sn_1') is None


def test_abort_converge_boundary_at_max(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    job_mod.claim_next_job('rn_a')
    _client().hset(redis_keys.job(job_id), 'attempts',
                   '2')  # one below the ceiling

    land_je = Writer()
    assert job_mod.abort_job('rn_a', job_id, 'rejected',
                             land_je) == AbortOutcome.CONVERGED
    assert land_je.calls == ['sn_1']
    assert _client().exists(redis_keys.job(job_id)) == 0


def test_abort_converge_je_failure_leaves_job_for_sweep(monkeypatch):
    # Exhausted, but the JE landing raises (Mongo down): the abort is still
    # accepted (CONVERGED) and the job REMAINS as an immediately-expired orphan;
    # a later wired claim sweeps it once Mongo recovers (INV1 retry path).
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    job_mod.claim_next_job('rn_a')
    _client().hset(redis_keys.job(job_id), 'attempts', '2')

    failing_je = Writer(raises=RuntimeError('mongo down'))
    assert job_mod.abort_job('rn_a', job_id, 'rejected',
                             failing_je) == AbortOutcome.CONVERGED
    assert _leased(job_id)  # job stays discoverable
    h = _hash(job_id)
    assert h['lease_deadline'] == '0'
    assert int(h['attempts']) >= params.MAX_ATTEMPTS

    # recovery: clear the time gate, then a wired claim sweeps the orphan
    _client().delete(redis_keys.DISPATCH_LAST_RECOVERY)
    monkeypatch.setattr(job_mod, '_now', lambda: 5000.0)
    ok_je = Writer()
    assert job_mod.claim_next_job('rn_x', land_je=ok_je) is None
    assert ok_je.calls == ['sn_1']
    assert _client().exists(redis_keys.job(job_id)) == 0
    assert not _leased(job_id)
    assert _current('sn_1') is None


def test_abort_stale_is_dropped_not_requeued(monkeypatch, caplog):
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job1 = _enqueue(submission_id='sn_x')
    job_mod.claim_next_job('rn_a')
    job2 = _enqueue(submission_id='sn_x')  # rejudge moves the pointer

    land_je = Writer()
    with caplog.at_level(logging.WARNING):
        outcome = job_mod.abort_job('rn_a', job1, 'prep_failed', land_je)

    assert outcome == AbortOutcome.STALE_DROPPED
    assert land_je.calls == []
    assert _client().exists(redis_keys.job(job1)) == 0  # destroyed
    assert job1 not in _pending()
    assert _current('sn_x') == job2  # pointer untouched
    assert 'stale abort dropped' in caplog.text


def test_abort_ownership_existence_and_validation(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    job_mod.claim_next_job('rn_a')

    # non-owner → refused, untouched
    assert job_mod.abort_job('rn_b', job_id, 'drain') == AbortOutcome.NOT_OWNER
    assert _hash(job_id)['leased_by'] == 'rn_a'
    assert not _pending()

    # unknown job → gone
    assert job_mod.abort_job('rn_a', 'jb_missing',
                             'drain') == AbortOutcome.GONE

    # invalid reason → ValueError before any Redis effect
    with pytest.raises(ValueError):
        job_mod.abort_job('rn_a', job_id, 'bogus')
    assert _hash(job_id)['state'] == 'leased'  # nothing happened


# --- JE sweep via orphan scan (reclaim exhaustion) ----------------------


def _exhaust_to_expired_orphan(job_id):
    """Drive a claimed job to MAX_ATTEMPTS via reclaims, then expire its lease."""
    assert _reclaim(job_id, 'rn_b', now=2000.0) == 1  # attempts = 2
    assert _reclaim(job_id, 'rn_c', now=3000.0) == 1  # attempts = 3
    _expire(job_id)
    _client().delete(redis_keys.DISPATCH_LAST_RECOVERY)


def test_scan_sweeps_exhausted_orphan_to_je(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    job_mod.claim_next_job('rn_a')  # attempts = 1
    _exhaust_to_expired_orphan(job_id)

    monkeypatch.setattr(job_mod, '_now', lambda: 5000.0)
    land_je = Writer()
    assert job_mod.claim_next_job('rn_z', land_je=land_je) is None

    assert land_je.calls == ['sn_1']
    assert _client().exists(redis_keys.job(job_id)) == 0
    assert not _leased(job_id)
    assert _current('sn_1') is None


def test_scan_destroys_superseded_orphan_without_je(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job1 = _enqueue(submission_id='sn_1')
    job_mod.claim_next_job('rn_a')  # attempts = 1
    _exhaust_to_expired_orphan(job1)
    job2 = _enqueue(submission_id='sn_1')  # rejudge: fresh, claimable

    monkeypatch.setattr(job_mod, '_now', lambda: 5000.0)
    land_je = Writer()
    # scan destroys the stale orphan without a JE, then hands out the fresh job
    assert job_mod.claim_next_job('rn_z', land_je=land_je)['job_id'] == job2

    assert land_je.calls == []
    assert _client().exists(redis_keys.job(job1)) == 0
    assert not _leased(job1)


def test_scan_dark_default_leaves_orphan_untouched(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    job_mod.claim_next_job('rn_a')
    _exhaust_to_expired_orphan(job_id)

    monkeypatch.setattr(job_mod, '_now', lambda: 5000.0)
    # land_je unset (dark): the exhausted orphan is left exactly as slice 2 left it
    assert job_mod.claim_next_job('rn_z') is None
    assert _client().exists(redis_keys.job(job_id)) == 1
    assert _leased(job_id)


def test_scan_lock_held_skips_sweep(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue(submission_id='sn_1')
    job_mod.claim_next_job('rn_a')
    _exhaust_to_expired_orphan(job_id)
    _client().set(redis_keys.submission_job_lock('sn_1'), 'held')

    monkeypatch.setattr(job_mod, '_now', lambda: 5000.0)
    land_je = Writer()
    assert job_mod.claim_next_job('rn_z', land_je=land_je) is None

    assert land_je.calls == []  # next window retries
    assert _client().exists(redis_keys.job(job_id)) == 1
    assert _leased(job_id)
