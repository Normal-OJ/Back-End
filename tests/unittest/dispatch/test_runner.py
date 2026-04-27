import pytest
from mongo.utils import RedisCache
from dispatch import runner as runner_mod
from dispatch.config import RUNNER_ALIVE_TTL_SEC
from dispatch.redis_keys import (
    RUNNERS_REGISTERED,
    runner_meta_key,
    runner_token_key,
    runner_alive_key,
)


@pytest.fixture(autouse=True)
def clear_redis():
    """Clear Redis state between tests (fakeredis persists across tests)."""
    RedisCache().client.flushdb()
    yield
    RedisCache().client.flushdb()


def test_register_returns_id_and_token():
    rn_id, rk_token = runner_mod.register(name="my-runner", registration_ip="1.2.3.4")
    assert rn_id.startswith("rn_")
    assert rk_token.startswith("rk_")
    assert len(rk_token) > 30  # actually random


def test_register_persists_to_redis():
    rn_id, rk_token = runner_mod.register(name="my-runner", registration_ip="1.2.3.4")
    rds = RedisCache().client

    # Meta hash exists with name + ip
    meta = rds.hgetall(runner_meta_key(rn_id))
    assert meta[b"name"] == b"my-runner"
    assert meta[b"registration_ip"] == b"1.2.3.4"
    assert b"registered_at" in meta

    # Token hash exists (NOT plaintext token)
    stored_hash = rds.get(runner_token_key(rn_id))
    assert stored_hash is not None
    assert stored_hash.decode() != rk_token  # plaintext NOT stored

    # In registered set
    assert rds.sismember(RUNNERS_REGISTERED, rn_id)

    # Initial alive key exists with TTL
    assert rds.exists(runner_alive_key(rn_id))
    assert 0 < rds.ttl(runner_alive_key(rn_id)) <= RUNNER_ALIVE_TTL_SEC


def test_register_each_call_unique_token():
    _, t1 = runner_mod.register(name="a", registration_ip="1.1.1.1")
    _, t2 = runner_mod.register(name="b", registration_ip="1.1.1.1")
    assert t1 != t2


def test_verify_token_returns_true_for_correct_token():
    rn_id, rk_token = runner_mod.register(name="x", registration_ip="1.1.1.1")
    assert runner_mod.verify_token(rn_id, rk_token) is True


def test_verify_token_returns_false_for_wrong_token():
    rn_id, _ = runner_mod.register(name="x", registration_ip="1.1.1.1")
    assert runner_mod.verify_token(rn_id, "rk_wrongtoken") is False


def test_verify_token_returns_false_for_unknown_runner():
    assert runner_mod.verify_token("rn_nonexistent", "rk_anything") is False


def test_renew_alive_resets_ttl():
    rn_id, _ = runner_mod.register(name="x", registration_ip="1.1.1.1")
    rds = RedisCache().client
    # Manually set short TTL
    rds.expire(runner_alive_key(rn_id), 5)
    assert rds.ttl(runner_alive_key(rn_id)) <= 5

    runner_mod.renew_alive(rn_id)
    assert (RUNNER_ALIVE_TTL_SEC - 5) < rds.ttl(runner_alive_key(rn_id)) <= RUNNER_ALIVE_TTL_SEC


def test_is_alive_returns_true_when_key_exists():
    rn_id, _ = runner_mod.register(name="x", registration_ip="1.1.1.1")
    assert runner_mod.is_alive(rn_id) is True


def test_is_alive_returns_false_when_key_expired():
    rn_id, _ = runner_mod.register(name="x", registration_ip="1.1.1.1")
    RedisCache().client.delete(runner_alive_key(rn_id))
    assert runner_mod.is_alive(rn_id) is False
