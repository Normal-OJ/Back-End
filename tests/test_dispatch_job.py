import pytest

from config import settings
from mongo.utils import RedisCache
from dispatch import params, redis_keys, scripts
from dispatch import job as job_mod


@pytest.fixture(autouse=True, scope='session')
def setup_minio():
    # Shadow conftest's Docker/MinIO session fixture: these job-lifecycle unit
    # tests touch only fakeredis, so they must not require a container engine.
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


# --- enqueue / claim happy path -----------------------------------------


def test_enqueue_writes_hash_pointer_and_pending(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 1_000_000.0)
    job_id = _enqueue(submission_id='sn_7', problem_id='pb_3', language=1)

    assert job_id.startswith('jb_')
    h = _hash(job_id)
    assert h['submission_id'] == 'sn_7'
    assert h['problem_id'] == 'pb_3'
    assert h['language'] == '1'
    assert h['code_minio_path'] == 'sn_7/main.py'
    assert h['checker'] == 'diff'
    assert h['tasks_meta_json'] == '[]'
    assert h['state'] == 'pending'
    assert h['attempts'] == '0'
    assert h['leased_by'] == ''
    assert h['lease_deadline'] == '0'
    assert h['last_error'] == ''
    assert float(h['created_at']) == 1_000_000.0

    client = _client()
    assert client.get(
        redis_keys.submission_current_job('sn_7')).decode() == job_id
    assert client.lrange(redis_keys.JOBS_PENDING, 0, -1) == [job_id.encode()]


def test_claim_happy_path_moves_pending_to_leased(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 2_000_000.0)
    job_id = _enqueue(submission_id='sn_1')

    payload = job_mod.claim_next_job('rn_a')

    assert payload['job_id'] == job_id
    assert payload['submission_id'] == 'sn_1'
    assert payload['state'] == 'leased'
    assert payload['attempts'] == '1'
    assert payload['leased_by'] == 'rn_a'
    assert float(
        payload['lease_deadline']) == 2_000_000.0 + params.LEASE_TTL_SEC

    client = _client()
    # membership moved pending -> leased
    assert client.lrange(redis_keys.JOBS_PENDING, 0, -1) == []
    assert client.sismember(redis_keys.JOBS_LEASED, job_id)


def test_claim_empty_queue_returns_none():
    assert job_mod.claim_next_job('rn_a') is None


def test_claim_is_fifo(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 10.0)
    first = _enqueue(submission_id='sn_1')
    second = _enqueue(submission_id='sn_2')

    assert job_mod.claim_next_job('rn_a')['job_id'] == first
    assert job_mod.claim_next_job('rn_b')['job_id'] == second


# --- INV4 currency (dispatch-side destroy) ------------------------------


def test_rejudge_supersedes_stale_job_is_destroyed(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 100.0)
    stale = _enqueue(submission_id='sn_9')
    # rejudge: a newer job for the same submission moves the current_job pointer
    current = _enqueue(submission_id='sn_9')
    assert stale != current

    # claim pops the stale one first (FIFO tail), destroys it, returns current
    payload = job_mod.claim_next_job('rn_a')
    assert payload['job_id'] == current

    client = _client()
    # stale hash destroyed; not leased
    assert client.exists(redis_keys.job(stale)) == 0
    assert not client.sismember(redis_keys.JOBS_LEASED, stale)
    # current is the one leased
    assert client.sismember(redis_keys.JOBS_LEASED, current)
    assert client.get(
        redis_keys.submission_current_job('sn_9')).decode() == current


# --- renew --------------------------------------------------------------


def test_renew_extends_deadline_for_owner(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 500.0)
    job_id = _enqueue()
    job_mod.claim_next_job('rn_owner')  # deadline = 530

    monkeypatch.setattr(job_mod, '_now', lambda: 800.0)
    assert job_mod.renew_lease('rn_owner', job_id) is True
    assert float(
        _hash(job_id)['lease_deadline']) == 800.0 + params.LEASE_TTL_SEC


def test_renew_wrong_runner_refused_deadline_untouched(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 500.0)
    job_id = _enqueue()
    job_mod.claim_next_job('rn_owner')
    before = _hash(job_id)['lease_deadline']

    monkeypatch.setattr(job_mod, '_now', lambda: 800.0)
    assert job_mod.renew_lease('rn_intruder', job_id) is False
    assert _hash(job_id)['lease_deadline'] == before


def test_renew_unknown_job_returns_false():
    assert job_mod.renew_lease('rn_owner', 'jb_missing') is False
    # must not resurrect anything
    assert _client().exists(redis_keys.job('jb_missing')) == 0
    assert not _client().sismember(redis_keys.JOBS_LEASED, 'jb_missing')


# --- INV2 reclaim eligibility (lease_deadline only) ---------------------


def test_reclaim_uses_only_lease_deadline_not_runner_liveness(monkeypatch):
    # A job whose runner is very much "alive" (its alive key is present) but whose
    # lease has expired MUST be reclaimable — runner liveness never participates.
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue()
    job_mod.claim_next_job('rn_alive')  # leased, deadline = 1030

    client = _client()
    client.set(redis_keys.runner_alive('rn_alive'), '1', ex=30)  # "alive"
    assert client.exists(redis_keys.runner_alive('rn_alive')) == 1

    # lease expired at now=2000 (> 1030) → reclaimable despite the alive key
    assert _reclaim(job_id, 'rn_new', now=2000.0) == 1
    h = _hash(job_id)
    assert h['leased_by'] == 'rn_new'
    assert h['attempts'] == '2'
    assert float(h['lease_deadline']) == 2000.0 + params.LEASE_TTL_SEC


def test_reclaim_not_expired_returns_zero(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue()
    job_mod.claim_next_job('rn_a')  # deadline = 1030

    # now still before the deadline → not an orphan
    assert _reclaim(job_id, 'rn_new', now=1020.0) == 0
    assert _hash(job_id)['leased_by'] == 'rn_a'


def test_reclaim_missing_or_unleased_returns_zero():
    # never leased
    assert _reclaim('jb_ghost', 'rn_new', now=9999.0) == 0


# --- double-reclaim race ------------------------------------------------


def test_double_reclaim_first_wins_second_gets_zero(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue()
    job_mod.claim_next_job('rn_a')  # deadline = 1030

    # both runners see the same expired lease at now=2000
    assert _reclaim(job_id, 'rn_x', now=2000.0) == 1
    # the winner renewed the deadline to 2030, so the loser now sees a live lease
    assert _reclaim(job_id, 'rn_y', now=2000.0) == 0
    assert _hash(job_id)['leased_by'] == 'rn_x'


# --- INV5 attempts boundary ---------------------------------------------


def test_attempts_accumulate_and_converge_at_max(monkeypatch):
    assert params.MAX_ATTEMPTS == 3
    monkeypatch.setattr(job_mod, '_now', lambda: 0.0)
    job_id = _enqueue()
    job_mod.claim_next_job('rn_a')  # attempts = 1, deadline = 30
    assert _hash(job_id)['attempts'] == '1'

    # reclaim twice, each after the prior lease expires
    assert _reclaim(job_id, 'rn_b', now=100.0) == 1  # attempts = 2
    assert _hash(job_id)['attempts'] == '2'
    assert _reclaim(job_id, 'rn_c', now=200.0) == 1  # attempts = 3
    assert _hash(job_id)['attempts'] == '3'

    # at MAX_ATTEMPTS the next reclaim returns -1 and touches nothing
    before = _hash(job_id)
    assert _reclaim(job_id, 'rn_d', now=300.0) == -1
    assert _hash(job_id) == before
    # job hash + jobs:leased membership remain in place (JE landing is slice 3)
    assert _client().sismember(redis_keys.JOBS_LEASED, job_id)


# --- time gate ----------------------------------------------------------


def test_orphan_scan_is_time_gated(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue()
    job_mod.claim_next_job('rn_a')  # leased, deadline = 1030
    _expire(job_id, deadline='0')  # force the lease expired

    client = _client()
    # Hold the gate manually so the next claim's scan is skipped.
    client.set(redis_keys.DISPATCH_LAST_RECOVERY,
               '1',
               ex=params.ORPHAN_SCAN_INTERVAL_SEC)

    monkeypatch.setattr(job_mod, '_now', lambda: 5000.0)
    # gate held → scan skipped → expired job stays with rn_a, nothing to hand out
    assert job_mod.claim_next_job('rn_b') is None
    assert _hash(job_id)['leased_by'] == 'rn_a'

    # release the gate → next claim scans, reclaims the expired job to the caller
    client.delete(redis_keys.DISPATCH_LAST_RECOVERY)
    payload = job_mod.claim_next_job('rn_b')
    assert payload['job_id'] == job_id
    assert payload['leased_by'] == 'rn_b'


def test_orphan_scan_reclaim_handed_to_caller(monkeypatch):
    monkeypatch.setattr(job_mod, '_now', lambda: 1000.0)
    job_id = _enqueue()
    job_mod.claim_next_job('rn_a')  # leased, deadline = 1030
    _expire(job_id, deadline='0')

    # The first claim already took the gate (its EX runs on fakeredis wall-clock,
    # not our monkeypatched _now); release it so the next claim scans.
    _client().delete(redis_keys.DISPATCH_LAST_RECOVERY)
    monkeypatch.setattr(job_mod, '_now', lambda: 5000.0)
    payload = job_mod.claim_next_job('rn_b')
    assert payload['job_id'] == job_id
    assert payload['leased_by'] == 'rn_b'
    assert payload['attempts'] == '2'
