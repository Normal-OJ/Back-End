import json
from unittest.mock import MagicMock

import pytest
from mongo.utils import RedisCache
from dispatch import job as job_mod
from dispatch.redis_keys import (
    job_key,
    submission_current_job_key,
    JOBS_PENDING,
    JOBS_LEASED,
)


@pytest.fixture(autouse=True)
def clear_redis():
    RedisCache().client.flushdb()
    yield
    RedisCache().client.flushdb()


def _make_submission(submission_id="sub_1",
                     problem_id=42,
                     language=1,
                     code_minio_path="submissions/sub_1.zip"):
    """Build a minimal submission-like object for enqueue_job tests."""
    sub = MagicMock()
    sub.id = submission_id
    sub.problem_id = problem_id
    sub.language = language
    sub.code_minio_path = code_minio_path
    sub.problem.test_case_info = {
        "tasks": [{
            "caseCount": 3,
            "memoryLimit": 65536,
            "timeLimit": 1000
        }]
    }
    return sub


def test_enqueue_job_creates_hash_and_pushes_to_pending():
    sub = _make_submission()

    jb_id = job_mod.enqueue_job(sub)

    assert jb_id.startswith("jb_")
    rds = RedisCache().client

    # Hash created with all expected fields
    h = rds.hgetall(job_key(jb_id))
    assert h[b"submission_id"] == b"sub_1"
    assert h[b"problem_id"] == b"42"
    assert h[b"language"] == b"1"
    assert h[b"code_minio_path"] == b"submissions/sub_1.zip"
    assert h[b"attempts"] == b"0"
    assert h[b"state"] == b"pending"
    assert b"created_at" in h
    assert b"tasks_meta_json" in h

    # Pushed to pending queue
    assert rds.lrange(JOBS_PENDING, 0, -1) == [jb_id.encode()]


def test_claim_next_job_from_empty_queue_returns_none():
    assert job_mod.claim_next_job(rn_id="rn_1") is None


def test_claim_next_job_from_pending_queue():
    sub = _make_submission()
    jb_id = job_mod.enqueue_job(sub)

    payload = job_mod.claim_next_job(rn_id="rn_1")

    assert payload is not None
    assert payload["job_id"] == jb_id
    assert payload["submission_id"] == "sub_1"
    assert payload["problem_id"] == 42
    assert payload["language"] == 1
    assert payload["code_minio_path"] == "submissions/sub_1.zip"
    assert "tasks" in payload  # parsed from tasks_meta_json

    # Side effects in Redis
    rds = RedisCache().client
    assert rds.hget(job_key(jb_id), "leased_by") == b"rn_1"
    assert rds.hget(job_key(jb_id), "state") == b"leased"
    assert rds.hget(job_key(jb_id), "lease_deadline") is not None
    assert rds.sismember(JOBS_LEASED, jb_id)
    assert int(rds.hget(job_key(jb_id), "attempts")) == 1
    # Removed from pending
    assert rds.llen(JOBS_PENDING) == 0


def test_claim_next_job_is_fifo():
    """First enqueued = first claimed."""
    j1 = job_mod.enqueue_job(_make_submission(submission_id="sub_1"))
    j2 = job_mod.enqueue_job(_make_submission(submission_id="sub_2"))

    p1 = job_mod.claim_next_job(rn_id="rn_a")
    p2 = job_mod.claim_next_job(rn_id="rn_b")

    assert p1["job_id"] == j1
    assert p2["job_id"] == j2


# Append after existing tests in test_job.py

from dispatch.redis_keys import runner_alive_key
from dispatch import runner as runner_mod


def test_claim_next_job_reclaims_orphan_when_owner_dead():
    """Job leased to a runner whose alive key expired should be reclaimable."""
    # Setup: enqueue + claim by runner1, then expire runner1's alive key
    sub = _make_submission()
    jb_id = job_mod.enqueue_job(sub)
    rn_id, _ = runner_mod.register(name="r1", registration_ip="1.1.1.1")
    job_mod.claim_next_job(rn_id=rn_id)  # rn1 takes the job
    # Simulate runner1 dying:
    RedisCache().client.delete(runner_alive_key(rn_id))

    # Now another runner polls
    rn2_id, _ = runner_mod.register(name="r2", registration_ip="1.1.1.2")
    payload = job_mod.claim_next_job(rn_id=rn2_id)

    assert payload is not None
    assert payload["job_id"] == jb_id
    rds = RedisCache().client
    assert rds.hget(job_key(jb_id), "leased_by") == rn2_id.encode()
    assert int(rds.hget(job_key(jb_id), "attempts")) == 2  # incremented


def test_claim_next_job_skips_orphan_with_alive_owner():
    sub = _make_submission()
    jb_id = job_mod.enqueue_job(sub)
    rn1, _ = runner_mod.register(name="r1", registration_ip="1.1.1.1")
    job_mod.claim_next_job(rn_id=rn1)  # rn1 takes the job; rn1 still alive

    rn2, _ = runner_mod.register(name="r2", registration_ip="1.1.1.2")
    payload = job_mod.claim_next_job(rn_id=rn2)

    assert payload is None  # no work for rn2 — rn1 is still alive
    # rn1 still owns the job
    assert RedisCache().client.hget(job_key(jb_id),
                                    "leased_by") == rn1.encode()


def test_claim_next_job_reclaim_at_max_attempts_returns_signal():
    """When attempts == MAX_ATTEMPTS, reclaim should signal exhaustion."""
    sub = _make_submission()
    jb_id = job_mod.enqueue_job(sub)
    rn1, _ = runner_mod.register(name="r1", registration_ip="1.1.1.1")
    job_mod.claim_next_job(rn_id=rn1)
    # Manually bump attempts to MAX-1 then kill rn1
    RedisCache().client.hset(job_key(jb_id), "attempts", 3)
    RedisCache().client.delete(runner_alive_key(rn1))

    rn2, _ = runner_mod.register(name="r2", registration_ip="1.1.1.2")
    payload = job_mod.claim_next_job(rn_id=rn2)

    # The exhausted job is removed from JOBS_LEASED but the caller (blueprint)
    # is responsible for marking Submission JE separately. claim_next_job itself
    # returns None (Task 9 will hook in the JE marking).
    assert payload is None
    assert not RedisCache().client.sismember(JOBS_LEASED, jb_id)


def test_complete_job_with_correct_owner_succeeds():
    sub = _make_submission()
    jb_id = job_mod.enqueue_job(sub)
    rn_id, _ = runner_mod.register(name="r1", registration_ip="1.1.1.1")
    job_mod.claim_next_job(rn_id=rn_id)

    process_calls = []

    def fake_process(submission_id, tasks):
        process_calls.append((submission_id, tasks))

    result = job_mod.complete_job(
        rn_id=rn_id,
        jb_id=jb_id,
        tasks=[{
            "status": "AC"
        }],
        process_result=fake_process,
    )

    assert result == "ok"
    assert process_calls == [("sub_1", [{"status": "AC"}])]
    rds = RedisCache().client
    # Job cleaned up
    assert rds.hgetall(job_key(jb_id)) == {}
    assert not rds.sismember(JOBS_LEASED, jb_id)
    assert rds.get(submission_current_job_key("sub_1")) is None


def test_complete_job_with_wrong_owner_returns_wrong_owner():
    sub = _make_submission()
    jb_id = job_mod.enqueue_job(sub)
    rn1, _ = runner_mod.register(name="r1", registration_ip="1.1.1.1")
    job_mod.claim_next_job(rn_id=rn1)

    rn2, _ = runner_mod.register(name="r2", registration_ip="1.1.1.2")
    result = job_mod.complete_job(
        rn_id=rn2,
        jb_id=jb_id,
        tasks=[],
        process_result=lambda *a, **k: None,
    )

    assert result == "wrong_owner"
    # Job NOT cleaned up — still belongs to rn1
    assert RedisCache().client.exists(job_key(jb_id))


def test_complete_job_with_unknown_id_returns_not_found():
    result = job_mod.complete_job(
        rn_id="rn_x",
        jb_id="jb_nonexistent",
        tasks=[],
        process_result=lambda *a, **k: None,
    )
    assert result == "not_found"


def test_complete_job_rejects_stale_submission_job():
    sub = _make_submission()
    old_jb_id = job_mod.enqueue_job(sub)
    new_jb_id = job_mod.enqueue_job(sub)
    rn_id, _ = runner_mod.register(name="r1", registration_ip="1.1.1.1")
    job_mod.claim_next_job(rn_id=rn_id)

    process_calls = []
    result = job_mod.complete_job(
        rn_id=rn_id,
        jb_id=old_jb_id,
        tasks=[{
            "status": "AC"
        }],
        process_result=lambda *args: process_calls.append(args),
    )

    assert result == "stale"
    assert process_calls == []
    assert RedisCache().client.hget(job_key(new_jb_id),
                                    "submission_id") == b"sub_1"


def test_complete_job_treats_missing_current_job_as_stale():
    sub = _make_submission()
    jb_id = job_mod.enqueue_job(sub)
    rn_id, _ = runner_mod.register(name="r1", registration_ip="1.1.1.1")
    job_mod.claim_next_job(rn_id=rn_id)
    RedisCache().client.delete(submission_current_job_key("sub_1"))

    process_calls = []
    result = job_mod.complete_job(
        rn_id=rn_id,
        jb_id=jb_id,
        tasks=[{
            "status": "AC"
        }],
        process_result=lambda *args: process_calls.append(args),
    )

    assert result == "stale"
    assert process_calls == []
    assert RedisCache().client.hgetall(job_key(jb_id)) == {}


def test_complete_job_rejects_expired_lease():
    sub = _make_submission()
    jb_id = job_mod.enqueue_job(sub)
    rn_id, _ = runner_mod.register(name="r1", registration_ip="1.1.1.1")
    job_mod.claim_next_job(rn_id=rn_id)
    RedisCache().client.hset(job_key(jb_id), "lease_deadline",
                             "2000-01-01T00:00:00+00:00")

    result = job_mod.complete_job(
        rn_id=rn_id,
        jb_id=jb_id,
        tasks=[],
        process_result=lambda *a, **k: None,
    )

    assert result == "lease_expired"


def test_abort_job_requeues_alive_runner_failed_job():
    sub = _make_submission()
    jb_id = job_mod.enqueue_job(sub)
    rn_id, _ = runner_mod.register(name="r1", registration_ip="1.1.1.1")
    job_mod.claim_next_job(rn_id=rn_id)

    result = job_mod.abort_job(rn_id=rn_id,
                               jb_id=jb_id,
                               reason="prepare failed")

    assert result == "requeued"
    rds = RedisCache().client
    assert not rds.sismember(JOBS_LEASED, jb_id)
    assert rds.lrange(JOBS_PENDING, 0, -1) == [jb_id.encode()]
    assert rds.hget(job_key(jb_id), "last_error") == b"prepare failed"


def test_claim_next_job_marks_submission_je_when_exhausted(app):
    """When orphan reclaim hits max_attempts, Submission must be marked JE (status=6)."""
    from bson import ObjectId
    from datetime import datetime
    from dispatch.config import MAX_ATTEMPTS

    rds = RedisCache().client

    with app.app_context():
        from mongo import engine

        # Create a minimal Submission document in MongoDB (mongomock allows
        # fake ObjectId refs — no real problem/user needed for this test).
        sub_doc = engine.Submission(
            problem=ObjectId(),
            user=ObjectId(),
            language=0,
            status=-1,
            timestamp=datetime.now(),
        )
        sub_doc.save()
        submission_id = str(sub_doc.id)

        # Manually write the job hash (bypasses enqueue_job's problem access).
        jb_id = "jb_exhaustion_test"
        rds.hset(
            job_key(jb_id),
            mapping={
                "submission_id": submission_id,
                "attempts": MAX_ATTEMPTS,
                "leased_by": "rn_dead",
            },
        )
        rds.sadd(JOBS_LEASED, jb_id)
        # rn_dead has no alive key — it is already dead.

        rn2, _ = runner_mod.register(name="r2", registration_ip="1.1.1.2")
        result = job_mod.claim_next_job(rn_id=rn2)

        assert result is None
        # Submission status must be 6 (JE).
        # Query only the status field to avoid ref dereference on fake ObjectIds.
        refreshed = engine.Submission.objects.only("status").get(id=sub_doc.id)
        assert refreshed.status == 6
        # Job hash should also be cleaned up.
        assert rds.hgetall(job_key(jb_id)) == {}
