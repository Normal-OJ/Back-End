from app import app as flask_app

import os
import pytest


@pytest.fixture
def app():
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def test_token():
    # Token for user: test
    return 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJ0ZXN0LnRlc3QiLCJleHAiOjI0MzkzNjk2MzEsImRhdGEiOnsidXNlcm5hbWUiOiJ0ZXN0In19.jXZuwP6JJpIHCsAFjZAHove3FYwr2tRgFZYRIbAJhJo'


@pytest.fixture
def test2_token():
    # Token for user: test2
    return 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJ0ZXN0LnRlc3QiLCJleHAiOjI0MzkzNzI2OTIsImRhdGEiOnsidXNlcm5hbWUiOiJ0ZXN0MiJ9fQ.lXtoQJNgLjwjum6ChbdTVpcPIBtwrKgNQcT6ZjApfYc'