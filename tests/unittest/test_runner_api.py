"""End-to-end HTTP tests for the runner API blueprint.

Uses the standard `client` fixture from conftest.py (Flask test client) and
exercises the blueprint via real HTTP-style calls.
"""
import pytest
from mongo.utils import RedisCache
from dispatch import runner as runner_mod
from dispatch.redis_keys import runner_alive_key
from dispatch.config import RUNNER_REGISTRATION_TOKEN, RUNNER_ALIVE_TTL_SEC

# first_admin is the seed admin created by app.py on first boot.
_ADMIN = "first_admin"

_TEST_CASE_INFO = {
    'language':
    0,
    'fillInTemplate':
    '',
    'tasks': [{
        'caseCount': 1,
        'taskScore': 100,
        'memoryLimit': 32768,
        'timeLimit': 1000,
    }],
}

# Minimal valid tasks payload: 1 task × 1 case (matches _TEST_CASE_INFO above)
_VALID_TASKS = [[{
    "exitCode": 0,
    "status": "AC",
    "stdout": "",
    "stderr": "",
    "execTime": 0,
    "memoryUsage": 0,
}]]


@pytest.fixture(autouse=True)
def clear_redis():
    RedisCache().client.flushdb()
    yield
    RedisCache().client.flushdb()


# --- POST /runners/register ---


def test_register_with_valid_token_returns_201_with_credentials(client):
    rv = client.post("/runners/register",
                     json={
                         "registration_token": RUNNER_REGISTRATION_TOKEN,
                         "name": "test-runner",
                     })
    assert rv.status_code == 201
    body = rv.get_json()["data"]
    assert body["runner_id"].startswith("rn_")
    assert body["token"].startswith("rk_")
    assert "config" in body
    assert body["config"]["heartbeat_interval_sec"] == 15


def test_register_with_invalid_token_returns_401(client):
    rv = client.post("/runners/register",
                     json={
                         "registration_token": "wrong-token",
                         "name": "test-runner",
                     })
    assert rv.status_code == 401


# --- POST /runners/<id>/heartbeat ---


def test_heartbeat_with_valid_token_returns_204_and_renews(client):
    rn_id, rk = runner_mod.register(name="r", registration_ip="1.1.1.1")
    rds = RedisCache().client
    rds.expire(runner_alive_key(rn_id), 5)
    rv = client.post(f"/runners/{rn_id}/heartbeat",
                     headers={"Authorization": f"Bearer {rk}"})
    assert rv.status_code == 204
    assert (RUNNER_ALIVE_TTL_SEC - 5) < rds.ttl(
        runner_alive_key(rn_id)) <= RUNNER_ALIVE_TTL_SEC


def test_heartbeat_with_invalid_token_returns_401(client):
    rn_id, _ = runner_mod.register(name="r", registration_ip="1.1.1.1")
    rv = client.post(f"/runners/{rn_id}/heartbeat",
                     headers={"Authorization": "Bearer wrong"})
    assert rv.status_code == 401


# --- GET /runners/<id>/next-job ---


def test_next_job_returns_204_when_no_jobs(client):
    rn_id, rk = runner_mod.register(name="r", registration_ip="1.1.1.1")
    rv = client.get(f"/runners/{rn_id}/next-job",
                    headers={"Authorization": f"Bearer {rk}"})
    assert rv.status_code == 204


def test_next_job_returns_200_with_payload_when_pending(
    client,
    app,
    save_source,
):
    """Submit a real submission; submit() enqueues it so runner can pull via next-job."""
    from tests.utils.submission import create_submission
    from tests.utils.problem import create_problem
    rn_id, rk = runner_mod.register(name="r", registration_ip="1.1.1.1")

    with app.app_context():
        problem = create_problem(
            owner=_ADMIN,
            test_case_info=_TEST_CASE_INFO,
        )
        save_source("base", b"int main(){}", lang=0)
        sub = create_submission(user=_ADMIN, problem=problem, lang=0)
        # enqueue_job is now called inside submit(); no manual call needed

    rv = client.get(f"/runners/{rn_id}/next-job",
                    headers={"Authorization": f"Bearer {rk}"})
    assert rv.status_code == 200
    body = rv.get_json()["data"]
    assert body["job_id"].startswith("jb_")
    assert body["submission_id"] == str(sub.id)
    # code_url is presigned (contains amz signing params or testcontainers minio host)
    assert "code_url" in body and len(body["code_url"]) > 0


# --- PUT /runners/<rn>/jobs/<jb>/complete ---


def test_complete_with_valid_owner_returns_204(
    client,
    app,
    save_source,
):
    from tests.utils.submission import create_submission
    from tests.utils.problem import create_problem
    rn_id, rk = runner_mod.register(name="r", registration_ip="1.1.1.1")
    with app.app_context():
        problem = create_problem(
            owner=_ADMIN,
            test_case_info=_TEST_CASE_INFO,
        )
        save_source("base", b"int main(){}", lang=0)
        sub = create_submission(user=_ADMIN, problem=problem, lang=0)
        # enqueue_job is now called inside submit(); no manual call needed

    # Pull job
    rv = client.get(f"/runners/{rn_id}/next-job",
                    headers={"Authorization": f"Bearer {rk}"})
    jb_id = rv.get_json()["data"]["job_id"]

    # Complete
    rv = client.put(
        f"/runners/{rn_id}/jobs/{jb_id}/complete",
        headers={"Authorization": f"Bearer {rk}"},
        json={"tasks": _VALID_TASKS},
    )
    assert rv.status_code == 204


def test_complete_with_wrong_owner_returns_409(
    client,
    app,
    save_source,
):
    from tests.utils.submission import create_submission
    from tests.utils.problem import create_problem
    rn1, rk1 = runner_mod.register(name="r1", registration_ip="1.1.1.1")
    rn2, rk2 = runner_mod.register(name="r2", registration_ip="1.1.1.2")
    with app.app_context():
        problem = create_problem(
            owner=_ADMIN,
            test_case_info=_TEST_CASE_INFO,
        )
        save_source("base", b"int main(){}", lang=0)
        sub = create_submission(user=_ADMIN, problem=problem, lang=0)
        # enqueue_job is now called inside submit(); no manual call needed

    rv = client.get(f"/runners/{rn1}/next-job",
                    headers={"Authorization": f"Bearer {rk1}"})
    jb_id = rv.get_json()["data"]["job_id"]

    # rn2 tries to complete rn1's job
    rv = client.put(
        f"/runners/{rn2}/jobs/{jb_id}/complete",
        headers={"Authorization": f"Bearer {rk2}"},
        json={"tasks": _VALID_TASKS},
    )
    assert rv.status_code == 409


def test_complete_with_unknown_job_returns_404(client):
    rn_id, rk = runner_mod.register(name="r", registration_ip="1.1.1.1")
    rv = client.put(
        f"/runners/{rn_id}/jobs/jb_nonexistent/complete",
        headers={"Authorization": f"Bearer {rk}"},
        json={"tasks": _VALID_TASKS},
    )
    assert rv.status_code == 404


def test_complete_rejects_malformed_case_payload(client):
    rn_id, rk = runner_mod.register(name="r", registration_ip="1.1.1.1")
    # missing exitCode/execTime/memoryUsage
    bad_tasks = [[{"status": "AC", "stdout": "", "stderr": ""}]]
    rv = client.put(
        f"/runners/{rn_id}/jobs/jb_nonexistent/complete",
        headers={"Authorization": f"Bearer {rk}"},
        json={"tasks": bad_tasks},
    )
    assert rv.status_code == 400


def test_abort_requeues_owned_job(client, app, save_source):
    from dispatch.redis_keys import JOBS_PENDING, JOBS_LEASED, job_key
    from tests.utils.submission import create_submission
    from tests.utils.problem import create_problem

    rn_id, rk = runner_mod.register(name="r", registration_ip="1.1.1.1")
    with app.app_context():
        problem = create_problem(
            owner=_ADMIN,
            test_case_info=_TEST_CASE_INFO,
        )
        save_source("base", b"int main(){}", lang=0)
        create_submission(user=_ADMIN, problem=problem, lang=0)

    headers = {"Authorization": f"Bearer {rk}"}
    rv = client.get(f"/runners/{rn_id}/next-job", headers=headers)
    jb_id = rv.get_json()["data"]["job_id"]

    rv = client.put(
        f"/runners/{rn_id}/jobs/{jb_id}/abort",
        headers=headers,
        json={"reason": "prepare failed"},
    )

    assert rv.status_code == 202
    rds = RedisCache().client
    assert rds.lrange(JOBS_PENDING, 0, -1) == [jb_id.encode()]
    assert not rds.sismember(JOBS_LEASED, jb_id)
    assert rds.hget(job_key(jb_id), "last_error") == b"prepare failed"
