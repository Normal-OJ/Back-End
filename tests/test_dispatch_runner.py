import hashlib
import os

import pytest

from mongo.utils import RedisCache
from dispatch import config, redis_keys, runner

REG_TOKEN_ENV = 'RUNNER_REGISTRATION_TOKEN'


@pytest.fixture(autouse=True, scope='session')
def setup_minio():
    # Shadow conftest's Docker/MinIO session fixture: these identity-layer unit
    # tests touch only fakeredis, so they must not require a container engine.
    yield


def _reset():
    # Force each test onto a fresh FakeStrictRedis: RedisCache caches its
    # connection pool on the class and dispatch caches one RedisCache instance.
    RedisCache.POOL = None
    runner._cache = None


def setup_function(_):
    # REDIS_PORT must be unset so RedisCache falls back to fakeredis.
    os.environ.pop('REDIS_PORT', None)
    _reset()


def teardown_function(_):
    _reset()
    os.environ.pop(REG_TOKEN_ENV, None)


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# --- registration token -------------------------------------------------


def test_verify_registration_token_accepts_correct(monkeypatch):
    monkeypatch.setenv(REG_TOKEN_ENV, 'super-secret')
    assert runner.verify_registration_token('super-secret') is True


def test_verify_registration_token_rejects_wrong(monkeypatch):
    monkeypatch.setenv(REG_TOKEN_ENV, 'super-secret')
    assert runner.verify_registration_token('nope') is False
    assert runner.verify_registration_token('') is False
    assert runner.verify_registration_token(None) is False


def test_verify_registration_token_unset_env_always_rejected(monkeypatch):
    monkeypatch.delenv(REG_TOKEN_ENV, raising=False)
    assert runner.verify_registration_token('anything') is False
    assert runner.verify_registration_token('') is False


def test_verify_registration_token_empty_env_always_rejected(monkeypatch):
    monkeypatch.setenv(REG_TOKEN_ENV, '')
    assert runner.verify_registration_token('') is False
    assert runner.verify_registration_token('anything') is False


def test_verify_registration_token_non_ascii_candidate_rejected(monkeypatch):
    # candidate is attacker-controlled (JSON body); non-ASCII must fail closed,
    # not raise TypeError from hmac.compare_digest on str inputs.
    monkeypatch.setenv(REG_TOKEN_ENV, 'super-secret')
    assert runner.verify_registration_token('sécret-ü') is False


def test_verify_registration_token_non_ascii_secret(monkeypatch):
    monkeypatch.setenv(REG_TOKEN_ENV, 'sécret-ü')
    assert runner.verify_registration_token('sécret-ü') is True
    assert runner.verify_registration_token('super-secret') is False


@pytest.mark.parametrize('candidate', [b'rk_bytes', 12345, ['x'], {'a': 1}])
def test_verify_registration_token_non_str_candidate_rejected(
        monkeypatch, candidate):
    # JSON bodies can legally carry non-str values; must fail closed, not raise.
    monkeypatch.setenv(REG_TOKEN_ENV, 'super-secret')
    assert runner.verify_registration_token(candidate) is False


# --- register -----------------------------------------------------------


def test_register_creates_zset_meta_and_token_hash(monkeypatch):
    now = 1_000_000.0
    monkeypatch.setattr(runner, '_now', lambda: now)

    reg = runner.register('runner-ec2-1', '10.0.0.7')

    assert reg.runner_id.startswith('rn_')
    assert reg.token.startswith('rk_')

    client = runner._redis()
    # ZSET member with score == registration time
    assert client.zscore(redis_keys.RUNNERS_REGISTERED, reg.runner_id) == now

    # meta hash
    meta = client.hgetall(redis_keys.runner_meta(reg.runner_id))
    meta = {k.decode(): v.decode() for k, v in meta.items()}
    assert meta['name'] == 'runner-ec2-1'
    assert meta['registration_ip'] == '10.0.0.7'
    assert float(meta['registered_at']) == now

    # token_hash stores only the SHA-256 of the token, never the token itself
    stored = client.get(redis_keys.runner_token_hash(reg.runner_id))
    assert stored.decode() == _sha256_hex(reg.token)
    assert reg.token not in stored.decode()

    # 7d TTLs on meta and token_hash
    ttl = config.IDENTITY_TTL_SEC
    assert ttl - 5 <= client.ttl(redis_keys.runner_meta(reg.runner_id)) <= ttl
    assert ttl - 5 <= client.ttl(redis_keys.runner_token_hash(
        reg.runner_id)) <= ttl


def test_register_generates_unique_ids():
    a = runner.register('a', '1.1.1.1')
    b = runner.register('b', '2.2.2.2')
    assert a.runner_id != b.runner_id
    assert a.token != b.token


# --- verify_token -------------------------------------------------------


def test_issued_token_verifies():
    reg = runner.register('r', '1.1.1.1')
    assert runner.verify_token(reg.runner_id, reg.token) is True


def test_wrong_token_fails():
    reg = runner.register('r', '1.1.1.1')
    assert runner.verify_token(reg.runner_id, 'rk_wrong') is False


def test_token_for_different_runner_fails():
    a = runner.register('a', '1.1.1.1')
    b = runner.register('b', '2.2.2.2')
    assert runner.verify_token(a.runner_id, b.token) is False
    assert runner.verify_token(b.runner_id, a.token) is False


def test_revocation_deletes_token_hash_then_401():
    reg = runner.register('r', '1.1.1.1')
    assert runner.verify_token(reg.runner_id, reg.token) is True
    # revoke: delete the token key
    runner._redis().delete(redis_keys.runner_token_hash(reg.runner_id))
    assert runner.verify_token(reg.runner_id, reg.token) is False


def test_verify_token_unknown_runner_fails():
    assert runner.verify_token('rn_does_not_exist', 'rk_whatever') is False


def test_verify_token_missing_args_fails():
    reg = runner.register('r', '1.1.1.1')
    assert runner.verify_token('', '') is False
    assert runner.verify_token(reg.runner_id, '') is False
    assert runner.verify_token(None, None) is False


@pytest.mark.parametrize('bad', [b'rk_bytes', 12345, ['x'], {'a': 1}])
def test_verify_token_non_str_inputs_rejected(bad):
    # Non-str token or runner_id from a JSON body must fail closed, not raise.
    reg = runner.register('r', '1.1.1.1')
    assert runner.verify_token(reg.runner_id, bad) is False
    assert runner.verify_token(bad, reg.token) is False


# --- lazy GC ------------------------------------------------------------


def test_gc_on_register_evicts_expired_identity(monkeypatch):
    t0 = 1_000_000.0
    monkeypatch.setattr(runner, '_now', lambda: t0)
    old = runner.register('old', '1.1.1.1')

    client = runner._redis()
    # fakeredis TTLs run on real wall-clock, not our monkeypatched _now, so
    # simulate the 7d token_hash TTL having fired by deleting the key.
    client.delete(redis_keys.runner_token_hash(old.runner_id))

    # 8 days later a new registration triggers GC of the stale identity
    monkeypatch.setattr(runner, '_now', lambda: t0 + 8 * 86400)
    fresh = runner.register('fresh', '2.2.2.2')

    assert client.zscore(redis_keys.RUNNERS_REGISTERED, old.runner_id) is None
    assert client.exists(redis_keys.runner_meta(old.runner_id)) == 0
    assert client.exists(redis_keys.runner_token_hash(old.runner_id)) == 0
    # fresh identity untouched
    assert client.zscore(redis_keys.RUNNERS_REGISTERED,
                         fresh.runner_id) is not None


def test_gc_on_list_runners_evicts_expired_identity(monkeypatch):
    t0 = 1_000_000.0
    monkeypatch.setattr(runner, '_now', lambda: t0)
    old = runner.register('old', '1.1.1.1')

    client = runner._redis()
    # Simulate the token_hash TTL having fired (see note above).
    client.delete(redis_keys.runner_token_hash(old.runner_id))

    monkeypatch.setattr(runner, '_now', lambda: t0 + 8 * 86400)
    listed = runner.list_runners()

    assert listed == []
    assert client.zscore(redis_keys.RUNNERS_REGISTERED, old.runner_id) is None
    assert client.exists(redis_keys.runner_meta(old.runner_id)) == 0
    assert client.exists(redis_keys.runner_token_hash(old.runner_id)) == 0


def test_gc_spares_stale_member_whose_token_hash_survives(monkeypatch):
    # TOCTOU regression (PR #341): a member older than 7d by score but whose
    # token_hash still exists (clock skew, or a heartbeat that just renewed it)
    # must NOT be swept — TTL is the sole invalidator.
    t0 = 1_000_000.0
    monkeypatch.setattr(runner, '_now', lambda: t0)
    old = runner.register('old', '1.1.1.1')

    # advance past the cutoff WITHOUT deleting token_hash
    monkeypatch.setattr(runner, '_now', lambda: t0 + 8 * 86400)
    runner.register('fresh', '2.2.2.2')  # GC via register
    runner.list_runners()  # GC via list_runners

    client = runner._redis()
    assert client.zscore(redis_keys.RUNNERS_REGISTERED,
                         old.runner_id) is not None
    assert client.exists(redis_keys.runner_meta(old.runner_id)) == 1
    assert runner.verify_token(old.runner_id, old.token) is True


def test_fresh_identity_survives_gc(monkeypatch):
    t0 = 1_000_000.0
    monkeypatch.setattr(runner, '_now', lambda: t0)
    a = runner.register('a', '1.1.1.1')

    # one day later — well within the 7d TTL
    monkeypatch.setattr(runner, '_now', lambda: t0 + 86400)
    b = runner.register('b', '2.2.2.2')

    ids = {r['runner_id'] for r in runner.list_runners()}
    assert a.runner_id in ids
    assert b.runner_id in ids


# --- list_runners -------------------------------------------------------


def test_list_runners_returns_identity_fields(monkeypatch):
    now = 1_000_000.0
    monkeypatch.setattr(runner, '_now', lambda: now)
    reg = runner.register('runner-ec2-1', '10.0.0.7')

    listed = runner.list_runners()
    assert len(listed) == 1
    entry = listed[0]
    assert entry['runner_id'] == reg.runner_id
    assert entry['name'] == 'runner-ec2-1'
    assert entry['last_seen'] == now
    assert float(entry['registered_at']) == now
    # identity layer must not leak secrets
    assert 'token' not in entry
    assert 'token_hash' not in entry


def test_list_runners_empty():
    assert runner.list_runners() == []
