import pytest
from mongo.utils import RedisCache, redis, doc_required
from mongo import Course
from unittest.mock import MagicMock
import os


def setup_function(_):
    RedisCache.POOL = None


def teardown_function(_):
    RedisCache.POOL = None


def test_create_redis_cache_without_port(monkeypatch):
    os.environ['REDIS_PORT'] = '6379'
    rc = RedisCache()
    mock_redis = MagicMock(return_value='mock_redis')
    monkeypatch.setattr(redis, 'Redis', mock_redis)
    assert rc.client == "mock_redis"
    mock_redis.assert_called_once_with(connection_pool=rc.POOL)
    del os.environ['REDIS_PORT']


def test_doc_required_no_src():

    @doc_required('course_name', 'course', Course)
    def add(course):
        pass

    with pytest.raises(TypeError) as e:
        add()
    assert str(e.value) == 'course_name not found in function argument'


def test_doc_required_cls_not_a_type():

    @doc_required('course_name', 'course', 'Course')
    def add(course):
        pass

    with pytest.raises(TypeError) as e:
        add(course_name="Public")
    assert str(e.value) == 'cls must be a type'


def test_doc_required_block_src_to_be_none():

    @doc_required('course_name', 'course', Course, src_none_allowed=False)
    def add(course):
        pass

    with pytest.raises(ValueError) as e:
        add(course_name=None)
    assert str(e.value) == 'src can not be None'


def test_doc_required_replace_des(caplog, app):

    @doc_required('course_name', 'course', Course, src_none_allowed=True)
    def add(course):
        pass

    with app.app_context():
        add(course_name=None, course="Will Be Replaced")

    assert "WARNING" in caplog.text
    assert "replace a existed argument" in caplog.text
