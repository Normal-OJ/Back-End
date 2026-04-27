"""End-to-end mock-runner integration tests.

These tests use the Flask test client to simulate a complete runner lifecycle:
register → poll → claim → complete. Verifies the entire Backend pipeline works
without needing a real Sandbox container.
"""
import io
import tempfile
import zipfile

import pytest
from mongo.utils import RedisCache
from dispatch.config import RUNNER_REGISTRATION_TOKEN, MAX_ATTEMPTS

# Realistic 1-task / 1-case AC result that process_result accepts.
# Outer list = tasks, inner list = cases per task.
_AC_TASKS = [
    [
        {
            "exitCode": 0,
            "status": "AC",
            "execTime": 10,
            "memoryUsage": 1024,
            "stdout": "",
            "stderr": "",
        },
    ],
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_zip_source(code: bytes = b"int main(){}") -> io.BytesIO:
    """Return a BytesIO holding a zip with main.c containing *code*."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("main.c", code)
    buf.seek(0)
    return buf


def _create_pending_submission(app, owner="first_admin", lang=0):
    """Create a problem + submission ready for judging (status=-1, job enqueued).

    Returns a *detached* Submission object (must call .reload() inside app
    context to refresh).
    """
    from tests.utils.problem import create_problem
    from mongo import Problem, Submission
    from tests.test_problem import get_file

    with app.app_context():
        prob = create_problem(
            owner=owner,
            status=0,
            test_case_info={
                "language":
                0,
                "fill_in_template":
                "",
                "tasks": [
                    {
                        "caseCount": 1,
                        "taskScore": 100,
                        "memoryLimit": 32768,
                        "timeLimit": 1000,
                    },
                ],
            },
        )
        # Attach test case data so process_result can look up tasks
        test_case = get_file("default/test_case.zip")["case"][0]
        prob.update_test_case(test_case)

        sub = Submission.add(
            problem_id=prob.id,
            username=owner,
            lang=lang,
            ip_addr="127.0.0.1",
        )
        # submit() uploads source to MinIO and enqueues job → status=-1
        sub.submit(_make_zip_source())
        sub.reload()
        return sub


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_runner(client):
    """Register a runner and return a helper object for runner-side actions."""
    rv = client.post(
        "/runners/register",
        json={
            "registration_token": RUNNER_REGISTRATION_TOKEN,
            "name": "mock-runner-1",
        },
    )
    assert rv.status_code == 201
    body = rv.get_json()["data"]
    rn_id = body["runner_id"]
    rk = body["token"]

    headers = {"Authorization": f"Bearer {rk}"}

    class Runner:
        runner_id = rn_id
        token = rk

        def heartbeat(self):
            return client.post(f"/runners/{rn_id}/heartbeat", headers=headers)

        def next_job(self):
            return client.get(f"/runners/{rn_id}/next-job", headers=headers)

        def complete(self, jb_id, tasks):
            return client.put(
                f"/runners/{rn_id}/jobs/{jb_id}/complete",
                headers=headers,
                json={"tasks": tasks},
            )

    return Runner()


# ---------------------------------------------------------------------------
# Task 19: Happy path
# ---------------------------------------------------------------------------


def test_full_flow_submit_pull_complete(app, mock_runner):
    """Submit code → runner pulls → runner submits result → submission shows AC."""
    sub = _create_pending_submission(app)
    assert sub.status == -1  # Pending after submit

    # Runner pulls
    rv = mock_runner.next_job()
    assert rv.status_code == 200, rv.get_data()
    payload = rv.get_json()["data"]
    assert payload["submission_id"] == str(sub.id)
    jb_id = payload["job_id"]

    # Runner sends back AC result
    rv = mock_runner.complete(jb_id, _AC_TASKS)
    assert rv.status_code == 204, rv.get_data()

    with app.app_context():
        sub.reload()
        assert sub.status == 0  # AC


def test_no_pending_returns_204(mock_runner):
    rv = mock_runner.next_job()
    assert rv.status_code == 204


def test_heartbeat_keeps_runner_alive(mock_runner):
    for _ in range(3):
        rv = mock_runner.heartbeat()
        assert rv.status_code == 204


# ---------------------------------------------------------------------------
# Task 20: Orphan reclaim
# ---------------------------------------------------------------------------


def test_orphan_reclaim_when_runner_dies(app, client):
    """Runner1 takes a job and dies; runner2 should reclaim and complete it."""
    from dispatch.redis_keys import runner_alive_key

    rv = client.post(
        "/runners/register",
        json={
            "registration_token": RUNNER_REGISTRATION_TOKEN,
            "name": "rn1",
        },
    )
    assert rv.status_code == 201
    rn1 = rv.get_json()["data"]
    rv = client.post(
        "/runners/register",
        json={
            "registration_token": RUNNER_REGISTRATION_TOKEN,
            "name": "rn2",
        },
    )
    assert rv.status_code == 201
    rn2 = rv.get_json()["data"]

    h1 = {"Authorization": f"Bearer {rn1['token']}"}
    h2 = {"Authorization": f"Bearer {rn2['token']}"}

    sub = _create_pending_submission(app)

    # rn1 takes the job
    rv = client.get(f"/runners/{rn1['runner_id']}/next-job", headers=h1)
    assert rv.status_code == 200
    jb_id = rv.get_json()["data"]["job_id"]

    # Simulate rn1 death
    RedisCache().client.delete(runner_alive_key(rn1["runner_id"]))

    # rn2 polls — should reclaim
    rv = client.get(f"/runners/{rn2['runner_id']}/next-job", headers=h2)
    assert rv.status_code == 200, rv.get_data()
    reclaimed = rv.get_json()["data"]
    assert reclaimed["job_id"] == jb_id  # same job!

    # rn2 completes it
    rv = client.put(
        f"/runners/{rn2['runner_id']}/jobs/{jb_id}/complete",
        headers=h2,
        json={"tasks": _AC_TASKS},
    )
    assert rv.status_code == 204, rv.get_data()

    # If rn1 zombie comes back and tries to complete, should be rejected
    # (404 because the job was deleted after rn2 completed it)
    rv = client.put(
        f"/runners/{rn1['runner_id']}/jobs/{jb_id}/complete",
        headers=h1,
        json={"tasks": _AC_TASKS},
    )
    assert rv.status_code == 404


# ---------------------------------------------------------------------------
# Task 21: Max attempts → JE
# ---------------------------------------------------------------------------


def test_max_attempts_marks_submission_je(app, client):
    """When a job is reclaimed too many times, Submission must be marked JE (status=6).

    Exhaustion logic in the Lua script:
        attempts >= max_attempts → remove from leased set, return -1

    Sequence for MAX_ATTEMPTS=3:
        - Runner 0 claims from pending  → attempts=1, then dies
        - Runner 1 reclaims             → attempts=2, then dies
        - Runner 2 reclaims             → attempts=3, then dies
        - Runner 3 polls                → Lua sees attempts=3 >= 3 → exhausted, JE marked
    Total runners needed: MAX_ATTEMPTS + 1.
    """
    from dispatch.redis_keys import runner_alive_key

    sub = _create_pending_submission(app)
    assert sub.status == -1

    # Register MAX_ATTEMPTS + 1 runners (one extra to trigger exhaustion)
    total_runners = MAX_ATTEMPTS + 1
    runners = []
    for i in range(total_runners):
        rv = client.post(
            "/runners/register",
            json={
                "registration_token": RUNNER_REGISTRATION_TOKEN,
                "name": f"rn{i}",
            },
        )
        assert rv.status_code == 201
        runners.append(rv.get_json()["data"])

    # Round 0: runner 0 claims from pending (attempts → 1)
    rn = runners[0]
    h = {"Authorization": f"Bearer {rn['token']}"}
    rv = client.get(f"/runners/{rn['runner_id']}/next-job", headers=h)
    assert rv.status_code == 200
    jb_id = rv.get_json()["data"]["job_id"]
    # Kill runner 0
    RedisCache().client.delete(runner_alive_key(rn["runner_id"]))

    # Rounds 1..MAX_ATTEMPTS-1: each runner reclaims then dies (attempts fills up to MAX_ATTEMPTS)
    for i in range(1, MAX_ATTEMPTS):
        rn = runners[i]
        h = {"Authorization": f"Bearer {rn['token']}"}
        rv = client.get(f"/runners/{rn['runner_id']}/next-job", headers=h)
        assert rv.status_code == 200, f"reclaim round {i} failed: {rv.get_data()}"
        RedisCache().client.delete(runner_alive_key(rn["runner_id"]))

    # The (MAX_ATTEMPTS+1)-th poll observes exhaustion and returns 204
    last_rn = runners[MAX_ATTEMPTS]
    h = {"Authorization": f"Bearer {last_rn['token']}"}
    rv = client.get(f"/runners/{last_rn['runner_id']}/next-job", headers=h)
    assert rv.status_code == 204  # exhausted; no job available

    # And the Submission is marked JE
    with app.app_context():
        sub.reload()
        assert sub.status == 6  # JE
