import pytest
from mongo import *
from tests import utils
from model.utils.smtp import send
from model.utils import smtp
from unittest.mock import MagicMock
import os


def setup_function(_):
    utils.drop_db()


def teardown_function(_):
    utils.drop_db()


from_addr = "from@test.n0j.tw"
password = "mock"
to_addrs = ['to0@test.n0j.tw', 'to1@test.n0j.tw']
subject = "test"
text = "test"
html = "test"


def test_smtp_send(monkeypatch):

    os.environ['SMTP_SERVER'] = "http://mock.server"

    from contextlib import contextmanager
    mock_smtp = MagicMock()

    @contextmanager
    def mock_smtp_context(*args, **kwargs):
        yield mock_smtp

    monkeypatch.setattr(smtp, 'SMTP', mock_smtp_context)

    send(from_addr, password, to_addrs, subject, text, html)

    mock_smtp.login.assert_called_once_with(from_addr, password)
    mock_smtp.send_message.assert_called_once()


def test_smtp_send_without_server_env(monkeypatch):

    del os.environ['SMTP_SERVER']

    from contextlib import contextmanager
    mock_smtp = MagicMock()

    @contextmanager
    def mock_smtp_context(*args, **kwargs):
        yield mock_smtp

    monkeypatch.setattr(smtp, 'SMTP', mock_smtp_context)

    send(from_addr, password, to_addrs, subject, text, html)

    mock_smtp.login.assert_not_called()
