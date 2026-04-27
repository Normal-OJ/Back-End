import pytest
from flask import Flask
from mongo.utils import RedisCache
from model.utils.runner_auth import require_runner_token
from dispatch import runner as runner_mod


@pytest.fixture(autouse=True)
def clear_redis():
    RedisCache().client.flushdb()
    yield
    RedisCache().client.flushdb()


@pytest.fixture
def app_with_protected_route():
    app = Flask(__name__)

    @app.get("/protected/<runner_id>")
    @require_runner_token
    def protected(runner_id):
        return {"runner_id": runner_id}

    return app


def test_protected_route_with_valid_token_passes(app_with_protected_route):
    rn_id, rk_token = runner_mod.register(name="r", registration_ip="1.1.1.1")
    client = app_with_protected_route.test_client()
    rv = client.get(f"/protected/{rn_id}",
                    headers={"Authorization": f"Bearer {rk_token}"})
    assert rv.status_code == 200
    assert rv.get_json() == {"runner_id": rn_id}


def test_protected_route_missing_header_returns_401(app_with_protected_route):
    rn_id, _ = runner_mod.register(name="r", registration_ip="1.1.1.1")
    client = app_with_protected_route.test_client()
    rv = client.get(f"/protected/{rn_id}")
    assert rv.status_code == 401


def test_protected_route_wrong_token_returns_401(app_with_protected_route):
    rn_id, _ = runner_mod.register(name="r", registration_ip="1.1.1.1")
    client = app_with_protected_route.test_client()
    rv = client.get(f"/protected/{rn_id}",
                    headers={"Authorization": "Bearer rk_wrong"})
    assert rv.status_code == 401


def test_protected_route_unknown_runner_returns_401(app_with_protected_route):
    client = app_with_protected_route.test_client()
    rv = client.get("/protected/rn_nonexistent",
                    headers={"Authorization": "Bearer rk_anything"})
    assert rv.status_code == 401


def test_protected_route_non_bearer_scheme_returns_401(
        app_with_protected_route):
    rn_id, rk_token = runner_mod.register(name="r", registration_ip="1.1.1.1")
    client = app_with_protected_route.test_client()
    rv = client.get(f"/protected/{rn_id}", headers={"Authorization": rk_token})
    assert rv.status_code == 401
