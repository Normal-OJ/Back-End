import os
import pytest

from config import Settings

# Env vars that may leak from the real environment and pollute a "clean env"
# Settings() construction. Derived from the model so new fields can't silently
# leak; FLASK_DEBUG is the one legacy name no longer backing a field.
_LEAK_VARS = (*Settings.model_fields, 'FLASK_DEBUG')


@pytest.fixture
def clean_env(monkeypatch):
    for var in _LEAK_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_defaults(clean_env):
    s = Settings()
    assert s.DEBUG is False
    assert s.TESTING is False
    assert s.MONGO_HOST == 'mongomock://localhost'
    assert s.MINIO_HOST is None
    assert s.MINIO_ACCESS_KEY is None
    assert s.MINIO_SECRET_KEY is None
    assert s.MINIO_BUCKET == 'normal-oj-testing'
    assert s.MINIO_REGION is None
    assert s.REDIS_HOST is None
    assert s.REDIS_PORT is None
    assert s.JWT_EXP == 30
    assert s.JWT_ISS == 'test.test'
    assert s.JWT_SECRET == 'SuperSecretString'
    assert s.SMTP_SERVER is None
    assert s.SMTP_NOREPLY is None
    assert s.SMTP_NOREPLY_PASSWORD is None


def test_debug_default_false(clean_env):
    assert Settings().DEBUG is False


def test_debug_from_env(clean_env):
    clean_env.setenv('DEBUG', 'True')
    assert Settings().DEBUG is True


def test_smtp_validator_server_without_noreply_raises(clean_env):
    clean_env.setenv('SMTP_SERVER', 'smtp.example.com')
    with pytest.raises(ValueError,
                       match="missing required configuration 'SMTP_NOREPLY'"):
        Settings()


def test_smtp_validator_both_set_ok(clean_env):
    clean_env.setenv('SMTP_SERVER', 'smtp.example.com')
    clean_env.setenv('SMTP_NOREPLY', 'noreply@example.com')
    s = Settings()
    assert s.SMTP_SERVER == 'smtp.example.com'
    assert s.SMTP_NOREPLY == 'noreply@example.com'


def test_smtp_validator_neither_set_ok(clean_env):
    s = Settings()
    assert s.SMTP_SERVER is None
    assert s.SMTP_NOREPLY is None


@pytest.mark.parametrize('value', ['1', 'true', 'TRUE', 'YES', 'yes', 'Yes'])
def test_testing_lenient_true(clean_env, value):
    clean_env.setenv('TESTING', value)
    assert Settings().TESTING is True


@pytest.mark.parametrize('value', ['false', 'FALSE', '0', 'garbage', ''])
def test_testing_lenient_false(clean_env, value):
    clean_env.setenv('TESTING', value)
    assert Settings().TESTING is False


def test_submission_tmp_dir_default_is_existing_dir(clean_env):
    s = Settings()
    assert os.path.isdir(s.SUBMISSION_TMP_DIR)
    assert 'noj-submissions' in s.SUBMISSION_TMP_DIR


def test_submission_tmp_dir_env_override(clean_env, tmp_path):
    override = str(tmp_path / 'custom-tmp')
    clean_env.setenv('SUBMISSION_TMP_DIR', override)
    assert Settings().SUBMISSION_TMP_DIR == override


def test_jwt_exp_is_int_not_timedelta(clean_env):
    clean_env.setenv('JWT_EXP', '7')
    assert Settings().JWT_EXP == 7


def test_redis_port_is_int(clean_env):
    clean_env.setenv('REDIS_PORT', '6379')
    assert Settings().REDIS_PORT == 6379
