import secrets
import pytest
from dataclasses import dataclass, asdict
from typing import Dict, Any
from mongo import *
from mongo import engine
from tests import utils
from tests.base_tester import BaseTester


def setup_function(_):
    utils.drop_db()


def teardown_function(_):
    utils.drop_db()


def test_test(forge_client):
    client = forge_client('first_admin')
    rv, rv_json, _ = BaseTester.request(
        client,
        'get',
        '/test',
    )
    assert rv.status_code == 200, rv_json
    assert rv_json.get('message') == 'first_admin', rv_json


@pytest.mark.parametrize(
    'role',
    [0, 1],
)
def test_role(forge_client, role):
    u = utils.user.create_user(role=role)
    client = forge_client(u.username)
    rv, rv_json, _ = BaseTester.request(
        client,
        'get',
        '/test/role',
    )
    assert rv.status_code == 200, rv_json
    assert rv_json.get('message') == str(role), rv_json


LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']


@pytest.mark.parametrize(
    'log_level',
    LOG_LEVELS,
)
def test_log(forge_client, caplog, app, log_level):
    app.logger.setLevel(log_level)
    client = forge_client('first_admin')
    rv, rv_json, _ = BaseTester.request(
        client,
        'get',
        '/test/log',
    )
    assert rv.status_code == 200, rv_json
    assert rv_json.get('message') == 'check the log'

    idx = LOG_LEVELS.index(log_level)
    expected_log = [
        'DEBUG    app:test.py:25 this is a DEBUG log',
        'INFO     app:test.py:26 this is a INFO log',
        'WARNING  app:test.py:27 this is a WARNING log',
        'ERROR    app:test.py:28 this is a ERROR log',
        'CRITICAL app:test.py:29 this is a CRITICAL log',
    ][idx:]

    assert caplog.text == '\n'.join(expected_log) + '\n', caplog.text


def test_check_header(forge_client):
    client = forge_client('first_admin')
    rv, rv_json, _ = BaseTester.request(
        client,
        'get',
        '/test/header',
    )
    assert rv.status_code == 200, rv_json
    assert rv_json.get('message') == 'ok'
