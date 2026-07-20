import pytest
import httpx
from mongo import Submission
from mongo import engine
from tests import utils
from config import settings


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    utils.drop_db()
    Submission._config = None
    monkeypatch.setattr(settings, 'TESTING', True)
    yield
    utils.drop_db()
    Submission._config = None


def _make_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture
def two_sandboxes():
    Submission.config().update(sandbox_instances=[
        engine.Sandbox(name='sb1', url='http://sb1:6666', token='tok1'),
        engine.Sandbox(name='sb2', url='http://sb2:6666', token='tok2'),
    ])


def _make_submission():
    admin = utils.user.create_user(role=0)
    problem_id = utils.problem.create_problem(
        owner=admin,
        course='Public',
    ).problem_id
    return utils.submission.create_submission(
        user=admin,
        problem=problem_id,
    )


def test_target_sandbox_skips_unhealthy(two_sandboxes):
    submission = _make_submission()

    def handler(request):
        if 'sb1' in str(request.url):
            return httpx.Response(503, text='unavailable')
        return httpx.Response(200, json={'load': 5})

    with _make_client(handler) as client:
        target = submission.target_sandbox(client=client)
    assert target is not None
    assert target.name == 'sb2'


def test_target_sandbox_picks_lowest_load(two_sandboxes):
    submission = _make_submission()

    def handler(request):
        if 'sb1' in str(request.url):
            return httpx.Response(200, json={'load': 10})
        return httpx.Response(200, json={'load': 2})

    with _make_client(handler) as client:
        target = submission.target_sandbox(client=client)
    assert target is not None
    assert target.name == 'sb2'


def test_target_sandbox_returns_none_when_all_unhealthy():
    submission = _make_submission()
    Submission.config().update(sandbox_instances=[
        engine.Sandbox(name='sb1', url='http://sb1:6666', token='tok1'),
    ])

    def handler(request):
        return httpx.Response(503, text='down')

    with _make_client(handler) as client:
        target = submission.target_sandbox(client=client)
    assert target is None
