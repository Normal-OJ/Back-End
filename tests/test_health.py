import pytest
from tests import utils
from tests.base_tester import BaseTester
from pymongo import MongoClient
from mongo.utils import RedisCache


def setup_function():
    utils.drop_db()


def teardown_function(_):
    utils.drop_db()


def mock_mongo_success(self):
    return {'ok': 1.0}


def mock_mongo_fails(self):
    return {'ok': 0}


def test_health(client, monkeypatch):
    monkeypatch.setattr(MongoClient, '__init__', lambda *_: None)
    monkeypatch.setattr(MongoClient, 'server_info', mock_mongo_success)
    rv = client.get('/health')
    rv_json = rv.get_json()
    assert rv.status_code == 200, rv_json


def test_health_when_mongo_fails(client, monkeypatch):
    monkeypatch.setattr(MongoClient, '__init__', lambda *_: None)
    monkeypatch.setattr(MongoClient, 'server_info', mock_mongo_fails)
    rv, rv_json, rv_data = BaseTester.request(
        client,
        'get',
        '/health',
    )
    assert rv.status_code == 500, rv_json
    assert rv_data == {'mongo': False, 'redis': True}, rv_json


def test_health_when_redis_fails(client, monkeypatch):
    monkeypatch.setattr(MongoClient, '__init__', lambda *_: None)
    monkeypatch.setattr(MongoClient, 'server_info', mock_mongo_success)

    def mock_redis(cls):

        class MockRedisClient:

            def ping(self):
                return False

        class MockRedisCache:
            client = MockRedisClient()

        return MockRedisCache()

    monkeypatch.setattr(RedisCache, '__new__', mock_redis)
    rv, rv_json, rv_data = BaseTester.request(
        client,
        'get',
        '/health',
    )
    assert rv.status_code == 500, rv_json
    assert rv_data == {'mongo': True, 'redis': False}, rv_json


def test_health_when_mongo_and_redis_fails(client, monkeypatch):
    monkeypatch.setattr(MongoClient, '__init__', lambda *_: None)
    monkeypatch.setattr(MongoClient, 'server_info', mock_mongo_fails)

    def mock_redis(cls):

        class MockRedisClient:

            def ping(self):
                return False

        class MockRedisCache:
            client = MockRedisClient()

        return MockRedisCache()

    monkeypatch.setattr(RedisCache, '__new__', mock_redis)
    rv, rv_json, rv_data = BaseTester.request(
        client,
        'get',
        '/health',
    )
    assert rv.status_code == 500, rv_json
    assert rv_data == {'mongo': False, 'redis': False}, rv_json
