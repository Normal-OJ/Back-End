from app import app as flask_app
from mongo.user import User

import os
import pytest


@pytest.fixture
def app():
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def client_admin(client):
    client.set_cookie('test.test', 'piann', User('admin').secret)
    return client


@pytest.fixture
def client_teacher(client):
    client.set_cookie('test.test', 'piann', User('teacher').secret)
    return client


@pytest.fixture
def client_student(client):
    client.set_cookie('test.test', 'piann', User('student').secret)
    return client


@pytest.fixture
def test_token():
    # Token for user: test
    return 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJ0ZXN0LnRlc3QiLCJleHAiOjE1NzkyNzEzMDksInNlY3JldCI6dHJ1ZSwiZGF0YSI6eyJ1c2VybmFtZSI6InRlc3QiLCJ1c2VySWQiOiI2NGMzN2YxNWNhNzNmMDRkNGFiMzRmNmYifX0.QUYwwR_RPVLAHZ9GxbUNyqI4w6w429kE6GCgmp5my9o'


@pytest.fixture
def test2_token():
    # Token for user: test2
    return 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJ0ZXN0LnRlc3QiLCJleHAiOjE1NzkyNzE0NjgsInNlY3JldCI6dHJ1ZSwiZGF0YSI6eyJ1c2VybmFtZSI6InRlc3QyIiwidXNlcklkIjoiOTdlYzJhNmY3ZTA2YWY3YTUwMmUzMWVkIn19.WVuSHj55b23kS_qb07ER15lRSdr20zBL-FdCRTk7pqM'
