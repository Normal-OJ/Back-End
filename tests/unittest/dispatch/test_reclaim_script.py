"""Tests for the atomic reclaim Lua script.

The script must be atomic: if two runners try to reclaim the same orphan job,
only one should succeed. It must also enforce the max-attempts limit.
"""
import pytest
from datetime import datetime, timezone
from mongo.utils import RedisCache
from dispatch.scripts import reclaim_orphan_atomic
from dispatch.redis_keys import job_key, JOBS_LEASED


@pytest.fixture(autouse=True)
def clear_redis():
    RedisCache().client.flushdb()
    yield
    RedisCache().client.flushdb()


def _seed_leased_job(jb_id: str, owner: str, attempts: int = 1):
    rds = RedisCache().client
    rds.hset(job_key(jb_id), mapping={
        "leased_by": owner,
        "leased_at": datetime.now(timezone.utc).isoformat(),
        "attempts": attempts,
    })
    rds.sadd(JOBS_LEASED, jb_id)


def test_reclaim_succeeds_when_owner_matches():
    _seed_leased_job("jb_1", owner="rn_old", attempts=1)

    result = reclaim_orphan_atomic(
        jb_id="jb_1",
        expected_owner="rn_old",
        new_owner="rn_new",
        max_attempts=3,
    )

    assert result == 1  # success
    rds = RedisCache().client
    assert rds.hget(job_key("jb_1"), "leased_by") == b"rn_new"
    assert int(rds.hget(job_key("jb_1"), "attempts")) == 2  # incremented


def test_reclaim_fails_when_owner_changed():
    """Another runner already reclaimed it before us."""
    _seed_leased_job("jb_1", owner="rn_someone_else", attempts=1)

    result = reclaim_orphan_atomic(
        jb_id="jb_1",
        expected_owner="rn_old",       # we expected rn_old
        new_owner="rn_new",
        max_attempts=3,
    )

    assert result == 0  # not reclaimed
    assert RedisCache().client.hget(job_key("jb_1"), "leased_by") == b"rn_someone_else"


def test_reclaim_returns_negative_when_max_attempts_reached():
    _seed_leased_job("jb_1", owner="rn_old", attempts=3)

    result = reclaim_orphan_atomic(
        jb_id="jb_1",
        expected_owner="rn_old",
        new_owner="rn_new",
        max_attempts=3,
    )

    assert result == -1  # exhausted
    # Job removed from leased set so caller can mark Submission JE
    assert not RedisCache().client.sismember(JOBS_LEASED, "jb_1")


def test_reclaim_is_atomic_under_concurrent_calls():
    """Simulate two runners reclaiming the same orphan at once.

    Lua scripts are atomic in Redis, so even back-to-back calls can't both succeed.
    """
    _seed_leased_job("jb_1", owner="rn_old", attempts=1)

    r1 = reclaim_orphan_atomic("jb_1", "rn_old", "rn_new1", max_attempts=3)
    r2 = reclaim_orphan_atomic("jb_1", "rn_old", "rn_new2", max_attempts=3)

    assert r1 == 1   # first wins
    assert r2 == 0   # second sees owner already changed
    assert RedisCache().client.hget(job_key("jb_1"), "leased_by") == b"rn_new1"
