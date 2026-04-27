import json
from unittest.mock import MagicMock

import pytest
from mongo.utils import RedisCache
from dispatch import job as job_mod
from dispatch.redis_keys import job_key, JOBS_PENDING, JOBS_LEASED


@pytest.fixture(autouse=True)
def clear_redis():
    RedisCache().client.flushdb()
    yield
    RedisCache().client.flushdb()


def _make_submission(submission_id="sub_1", problem_id=42, language=1,
                     code_minio_path="submissions/sub_1.zip"):
    """Build a minimal submission-like object for enqueue_job tests."""
    sub = MagicMock()
    sub.id = submission_id
    sub.problem_id = problem_id
    sub.language = language
    sub.code_minio_path = code_minio_path
    sub.problem.test_case_info = {
        "tasks": [{"caseCount": 3, "memoryLimit": 65536, "timeLimit": 1000}]
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
