import itertools
import pathlib
import subprocess
import time as _time
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from minio import Minio
from mongo import *
from mongo import engine
import mongo.config
from .base_tester import BaseTester
from .utils import *
from tests import utils


@pytest.fixture(autouse=True, scope='session')
def setup_minio():
    """Override session-scoped minio fixture to start minio via Docker."""
    container_name = 'test-minio-runner'
    subprocess.run(
        ['docker', 'rm', '-f', container_name],
        capture_output=True,
    )
    proc = subprocess.run(
        [
            'docker',
            'run',
            '-d',
            '--name',
            container_name,
            '-p',
            '19000:9000',
            '-e',
            'MINIO_ROOT_USER=minioadmin',
            '-e',
            'MINIO_ROOT_PASSWORD=minioadmin',
            'minio/minio:latest',
            'server',
            '/data',
            '--address',
            ':9000',
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f'Failed to start minio: {proc.stderr}'

    # Wait for minio to be ready
    for _ in range(30):
        try:
            import urllib.request
            urllib.request.urlopen('http://localhost:19000/minio/health/live',
                                   timeout=2)
            break
        except Exception:
            _time.sleep(1)
    else:
        raise TimeoutError('Minio did not start in time')

    mongo.config.MINIO_ACCESS_KEY = 'minioadmin'
    mongo.config.MINIO_SECRET_KEY = 'minioadmin'
    mongo.config.MINIO_HOST = 'localhost:19000'
    mongo.config.FLASK_DEBUG = True

    client = Minio(
        'localhost:19000',
        access_key='minioadmin',
        secret_key='minioadmin',
        secure=False,
    )
    bucket = mongo.config.MINIO_BUCKET
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    yield

    subprocess.run(['docker', 'rm', '-f', container_name], capture_output=True)


import fakeredis

A_NAMES = ['teacher', 'admin']
S_NAMES = {
    'student': 'Chika.Fujiwara',
    'student-2': 'Nico.Kurosawa',
}

# The default sandbox token from engine.SubmissionConfig
RUNNER_TOKEN = 'KoNoSandboxDa'
RUNNER_HEADERS = {
    'X-Runner-Token': RUNNER_TOKEN,
    'X-Runner-Name': 'test-runner',
}


@pytest.fixture(autouse=True)
def shared_fakeredis(monkeypatch):
    """Ensure all RedisCache instances share the same fakeredis server."""
    server = fakeredis.FakeServer()
    shared_client = fakeredis.FakeStrictRedis(server=server)
    from mongo.utils import RedisCache
    monkeypatch.setattr(
        RedisCache,
        'client',
        property(lambda self: shared_client),
    )


@pytest.fixture(autouse=True)
def runner_testcase_setup(
    save_source,
    make_course,
):
    BaseTester.setup_class()
    src_dir = pathlib.Path('tests/src')
    exts = ['.c', '.cpp', '.py', '.pdf']
    for src in src_dir.iterdir():
        if any([not src.suffix in exts, not src.is_file()]):
            continue
        save_source(
            src.stem,
            src.read_bytes(),
            exts.index(src.suffix),
        )
    for name in A_NAMES:
        make_course(username=name, students=S_NAMES)
    yield
    BaseTester.teardown_class()


@pytest.fixture
def submission_id(app, problem_ids, get_source):
    """Create a single pending submission (status=-1) for testing."""
    with app.app_context():
        pids = problem_ids('teacher', 1, True)
        pid = pids[0]
        sub = Submission.add(
            problem_id=pid,
            username='student',
            lang=2,
            timestamp=datetime.now(),
        )
        sub.submit(get_source('base.py'))
        return str(sub.obj.id)


class TestRunnerAuth:
    """Test runner authentication via X-Runner-Token."""

    def test_missing_token_returns_403(self, client):
        rv = client.get('/runner/jobs')
        assert rv.status_code == 403

    def test_invalid_token_returns_403(self, client):
        rv = client.get('/runner/jobs',
                        headers={
                            'X-Runner-Token': 'wrong-token',
                        })
        assert rv.status_code == 403

    def test_valid_token_returns_200(self, client):
        rv = client.get('/runner/jobs', headers=RUNNER_HEADERS)
        assert rv.status_code == 200


class TestGetPendingJobs:
    """Test GET /runner/jobs endpoint."""

    def test_no_pending_jobs(self, client):
        rv = client.get('/runner/jobs', headers=RUNNER_HEADERS)
        assert rv.status_code == 200
        data = rv.get_json()['data']
        assert data['jobs'] == []

    def test_returns_pending_submission(self, client, submission_id):
        rv = client.get('/runner/jobs', headers=RUNNER_HEADERS)
        assert rv.status_code == 200
        data = rv.get_json()['data']
        jobs = data['jobs']
        assert len(jobs) >= 1
        job_ids = [j['submissionId'] for j in jobs]
        assert submission_id in job_ids

    def test_excludes_claimed_jobs(self, client, submission_id):
        # Claim the job first
        engine.Submission.objects.get(id=submission_id).update(
            claimed_by='other-runner',
            claimed_at=datetime.now(),
        )
        rv = client.get('/runner/jobs', headers=RUNNER_HEADERS)
        assert rv.status_code == 200
        jobs = rv.get_json()['data']['jobs']
        job_ids = [j['submissionId'] for j in jobs]
        assert submission_id not in job_ids

    def test_includes_expired_claims(self, client, submission_id):
        # Claim with expired time
        engine.Submission.objects.get(id=submission_id).update(
            claimed_by='dead-runner',
            claimed_at=datetime.now() - timedelta(seconds=700),
        )
        rv = client.get('/runner/jobs', headers=RUNNER_HEADERS)
        assert rv.status_code == 200
        jobs = rv.get_json()['data']['jobs']
        job_ids = [j['submissionId'] for j in jobs]
        assert submission_id in job_ids


class TestClaimJob:
    """Test POST /runner/jobs/<id>/claim endpoint."""

    def test_claim_success(self, client, submission_id):
        rv = client.post(
            f'/runner/jobs/{submission_id}/claim',
            headers=RUNNER_HEADERS,
        )
        assert rv.status_code == 200
        data = rv.get_json()['data']
        assert data['submissionId'] == submission_id
        assert 'token' in data
        assert 'meta' in data
        assert 'language' in data['meta']
        assert 'tasks' in data['meta']

    def test_claim_nonexistent_returns_404(self, client):
        rv = client.post(
            '/runner/jobs/000000000000000000000000/claim',
            headers=RUNNER_HEADERS,
        )
        assert rv.status_code == 404

    def test_claim_already_claimed_returns_409(self, client, submission_id):
        # First claim
        rv = client.post(
            f'/runner/jobs/{submission_id}/claim',
            headers=RUNNER_HEADERS,
        )
        assert rv.status_code == 200

        # Second claim by another runner
        rv = client.post(
            f'/runner/jobs/{submission_id}/claim',
            headers={
                'X-Runner-Token': RUNNER_TOKEN,
                'X-Runner-Name': 'another-runner',
            },
        )
        assert rv.status_code == 409

    def test_claim_sets_claimed_by_field(self, client, submission_id):
        client.post(
            f'/runner/jobs/{submission_id}/claim',
            headers=RUNNER_HEADERS,
        )
        sub = engine.Submission.objects.get(id=submission_id)
        assert sub.claimed_by == 'test-runner'
        assert sub.claimed_at is not None


class TestGetJobCode:
    """Test GET /runner/jobs/<id>/code endpoint."""

    def test_code_download_by_claimer(self, client, submission_id):
        # Claim first
        client.post(
            f'/runner/jobs/{submission_id}/claim',
            headers=RUNNER_HEADERS,
        )
        rv = client.get(
            f'/runner/jobs/{submission_id}/code',
            headers=RUNNER_HEADERS,
        )
        assert rv.status_code == 200
        assert rv.content_type == 'application/zip'

    def test_code_download_by_non_claimer_returns_403(self, client,
                                                      submission_id):
        # Claim by one runner
        client.post(
            f'/runner/jobs/{submission_id}/claim',
            headers=RUNNER_HEADERS,
        )
        # Try download by another
        rv = client.get(
            f'/runner/jobs/{submission_id}/code',
            headers={
                'X-Runner-Token': RUNNER_TOKEN,
                'X-Runner-Name': 'another-runner',
            },
        )
        assert rv.status_code == 403

    def test_code_download_nonexistent_returns_404(self, client):
        rv = client.get(
            '/runner/jobs/000000000000000000000000/code',
            headers=RUNNER_HEADERS,
        )
        assert rv.status_code == 404


class TestHeartbeat:
    """Test POST /runner/heartbeat endpoint."""

    def test_heartbeat_extends_claim(self, client, submission_id):
        # Claim first
        client.post(
            f'/runner/jobs/{submission_id}/claim',
            headers=RUNNER_HEADERS,
        )
        old_sub = engine.Submission.objects.get(id=submission_id)
        old_claimed_at = old_sub.claimed_at

        # Send heartbeat
        rv = client.post(
            '/runner/heartbeat',
            headers=RUNNER_HEADERS,
            json={'submissionId': submission_id},
        )
        assert rv.status_code == 200

        new_sub = engine.Submission.objects.get(id=submission_id)
        assert new_sub.claimed_at >= old_claimed_at

    def test_heartbeat_without_submission_id(self, client):
        rv = client.post(
            '/runner/heartbeat',
            headers=RUNNER_HEADERS,
            json={},
        )
        assert rv.status_code == 200

    def test_heartbeat_by_non_claimer_returns_403(self, client, submission_id):
        # Claim by one runner
        client.post(
            f'/runner/jobs/{submission_id}/claim',
            headers=RUNNER_HEADERS,
        )
        # Heartbeat from different runner
        rv = client.post(
            '/runner/heartbeat',
            headers={
                'X-Runner-Token': RUNNER_TOKEN,
                'X-Runner-Name': 'another-runner',
            },
            json={'submissionId': submission_id},
        )
        assert rv.status_code == 403


class TestJobComplete:
    """Test PUT /runner/jobs/<id>/complete endpoint."""

    def test_complete_missing_body_returns_400(self, client, submission_id):
        rv = client.put(
            f'/runner/jobs/{submission_id}/complete',
            headers=RUNNER_HEADERS,
            content_type='application/json',
        )
        assert rv.status_code == 400

    def test_complete_missing_fields_returns_400(self, client, submission_id):
        rv = client.put(
            f'/runner/jobs/{submission_id}/complete',
            headers=RUNNER_HEADERS,
            json={'tasks': []},
        )
        assert rv.status_code == 400

    def test_complete_invalid_token_returns_403(self, client, submission_id):
        rv = client.put(
            f'/runner/jobs/{submission_id}/complete',
            headers=RUNNER_HEADERS,
            json={
                'tasks': [],
                'token': 'invalid-token',
            },
        )
        assert rv.status_code == 403

    def test_complete_with_valid_token(self, client, submission_id):
        # Claim to get token
        rv = client.post(
            f'/runner/jobs/{submission_id}/claim',
            headers=RUNNER_HEADERS,
        )
        token = rv.get_json()['data']['token']
        tasks = rv.get_json()['data']['meta']['tasks']

        # Build result matching the task structure
        result_tasks = []
        for task in tasks:
            cases = []
            for _ in range(task['caseCount']):
                cases.append({
                    'exitCode': 0,
                    'status': 'AC',
                    'stdout': 'output',
                    'stderr': '',
                    'execTime': 100,
                    'memoryUsage': 1024,
                })
            result_tasks.append(cases)

        rv = client.put(
            f'/runner/jobs/{submission_id}/complete',
            headers=RUNNER_HEADERS,
            json={
                'tasks': result_tasks,
                'token': token,
            },
        )
        assert rv.status_code == 200

        # Verify submission status updated
        sub = engine.Submission.objects.get(id=submission_id)
        assert sub.status != -1  # no longer pending
        assert sub.claimed_by is None  # claim cleared
