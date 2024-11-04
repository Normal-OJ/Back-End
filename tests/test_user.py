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


@dataclass
class CreateUserInput:
    username: str
    password: str
    email: str


def random_create_user_input():
    return CreateUserInput(
        username=secrets.token_hex(6),
        password=secrets.token_hex(6),
        email=f'{secrets.token_hex(6)}@noj.tw',
    )


def test_admin_can_create_user(forge_client):
    client = forge_client('first_admin')
    payload = random_create_user_input()
    rv, rv_json, _ = BaseTester.request(
        client,
        'post',
        '/user',
        json=asdict(payload),
    )
    assert rv.status_code == 200, rv_json

    u = User.login(payload.username, payload.password, "127.0.0.1")
    assert u.email == payload.email


@pytest.mark.parametrize(
    ('payload_override', 'expected_err_msg'),
    (
        ({
            'email': 'inva@lid.'
        }, 'Signup Failed'),
        ({
            'username': 'first_admin'
        }, 'User Exists'),
        ({
            'username': ''
        }, 'Not Allowed Name'),
    ),
)
def test_admin_fails_to_create_user(forge_client, payload_override,
                                    expected_err_msg):
    client = forge_client('first_admin')
    payload = random_create_user_input()
    rv, rv_json, _ = BaseTester.request(
        client,
        'post',
        '/user',
        json={
            **asdict(payload),
            **payload_override
        },
    )
    assert rv.status_code == 400, rv_json
    assert rv_json['message'] == expected_err_msg


@pytest.mark.parametrize(
    'role',
    (
        engine.User.Role.STUDENT,
        engine.User.Role.TEACHER,
    ),
)
def test_non_admin_cannot_create_user(forge_client, role: engine.User.Role):
    actor = utils.user.create_user(role=role)
    client = forge_client(actor.username)
    payload = random_create_user_input()
    rv, rv_json, _ = BaseTester.request(
        client,
        'post',
        '/user',
        json=asdict(payload),
    )
    assert rv.status_code == 403, rv_json
    with pytest.raises(engine.DoesNotExist):
        User.login(payload.username, payload.password, "127.0.0.1")


def test_admin_can_read_user_list(forge_client):
    client = forge_client('first_admin')
    rv, rv_json, rv_data = BaseTester.request(client, 'get', '/user')
    assert rv.status_code == 200, rv_json
    assert rv_data == [User('first_admin').info]


@pytest.mark.parametrize(
    'role',
    (
        engine.User.Role.STUDENT,
        engine.User.Role.TEACHER,
    ),
)
def test_non_admin_cannot_read_user_list(
    forge_client,
    role: engine.User.Role,
):
    actor = utils.user.create_user(role=role)
    client = forge_client(actor.username)
    rv, rv_json, rv_data = BaseTester.request(client, 'get', '/user')
    assert rv.status_code == 403, rv_json
    assert rv_data is None


def test_read_user_list_with_role(forge_client):
    client = forge_client('first_admin')

    expected = [(0, 1), (1, 0), (2, 0)]
    for role, count in expected:
        rv, rv_json, rv_data = BaseTester.request(client, 'get',
                                                  f'/user?role={role}')
        assert rv.status_code == 200, rv_json
        assert len(rv_data) == count, rv_data

    utils.user.create_user_many(3, role=1)
    utils.user.create_user_many(5, role=2)

    expected = [(0, 1), (1, 3), (2, 5)]
    for role, count in expected:
        rv, rv_json, rv_data = BaseTester.request(client, 'get',
                                                  f'/user?role={role}')
        assert rv.status_code == 200, rv_json
        assert len(rv_data) == count

    rv, rv_json, rv_data = BaseTester.request(client, 'get', '/user?role=0.5')
    assert rv.status_code == 400, rv_json


def test_read_user_list_with_offset(forge_client):
    client = forge_client('first_admin')

    expected = [(0, 1), (1, 0)]
    for offset, count in expected:
        rv, rv_json, rv_data = BaseTester.request(client, 'get',
                                                  f'/user?offset={offset}')
        assert rv.status_code == 200, rv_json
        assert len(rv_data) == count, rv_data

    utils.user.create_user_many(3, role=1)

    expected = [(0, 4), (2, 2)]
    for offset, count in expected:
        rv, rv_json, rv_data = BaseTester.request(client, 'get',
                                                  f'/user?offset={offset}')
        assert rv.status_code == 200, rv_json
        assert len(rv_data) == count, rv_data

    rv, rv_json, rv_data = BaseTester.request(client, 'get',
                                              '/user?offset=0.5')
    assert rv.status_code == 400, rv_json


def test_read_user_list_with_count(forge_client):
    client = forge_client('first_admin')

    expected = [(0, 0), (1, 1)]
    for count, length in expected:
        rv, rv_json, rv_data = BaseTester.request(client, 'get',
                                                  f'/user?count={count}')
        assert rv.status_code == 200, rv_json
        assert len(rv_data) == length, rv_data

    rv, rv_json, rv_data = BaseTester.request(client, 'get', '/user?count=0.5')
    assert rv.status_code == 400, rv_json


def test_admin_can_read_user_under_specific_course(forge_client):
    course_name = secrets.token_hex(8)
    user = utils.user.create_user(course=course_name)
    course = user.courses[-1]

    client = forge_client('first_admin')
    rv, rv_json, rv_data = BaseTester.request(
        client,
        'get',
        f'/user?course={course.id}',
    )
    assert rv.status_code == 200, rv_json

    key_fn = lambda d: d['username']
    expected = sorted((user.info, course.teacher.info), key=key_fn)
    assert sorted(rv_data, key=key_fn) == expected


def test_admin_can_update_user_password(forge_client):
    password = secrets.token_hex()
    user = utils.user.create_user(password=password)
    assert User.login(user.username, password,
                      "127.0.0.1").username == user.username

    client = forge_client('first_admin')
    new_password = password + secrets.token_hex(4)
    payload = {'password': new_password}
    rv, rv_json, _ = BaseTester.request(
        client,
        'patch',
        f'/user/{user.username}',
        json=payload,
    )
    assert rv.status_code == 200, rv_json

    # can't login with old password
    with pytest.raises(engine.DoesNotExist):
        User.login(user.username, password, "127.0.0.1")
    # should use new one
    assert User.login(user.username, new_password,
                      "127.0.0.1").username == user.username


def test_admin_can_update_user_display_name(forge_client):
    user = utils.user.create_user()
    original_name = user.profile.displayed_name
    client = forge_client('first_admin')
    new_name = original_name + secrets.token_hex(4)
    payload = {'displayedName': new_name}
    rv, rv_json, _ = BaseTester.request(
        client,
        'patch',
        f'/user/{user.username}',
        json=payload,
    )
    assert rv.status_code == 200, rv_json
    user.reload('profile')
    assert user.profile.displayed_name == new_name


def test_admin_can_upgrade_user_role(forge_client):
    user = utils.user.create_user()
    assert user.role == engine.User.Role.STUDENT
    client = forge_client('first_admin')
    payload = {'role': engine.User.Role.TEACHER}
    rv, rv_json, _ = BaseTester.request(
        client,
        'patch',
        f'/user/{user.username}',
        json=payload,
    )
    assert rv.status_code == 200, rv_json
    assert user.reload('role').role == engine.User.Role.TEACHER


def test_admin_can_downgrade_user_role(forge_client):
    user = utils.user.create_user(role=engine.User.Role.TEACHER)
    assert user.role == engine.User.Role.TEACHER
    client = forge_client('first_admin')
    payload = {'role': engine.User.Role.STUDENT}
    rv, rv_json, _ = BaseTester.request(
        client,
        'patch',
        f'/user/{user.username}',
        json=payload,
    )
    assert rv.status_code == 200, rv_json
    assert user.reload('role').role == engine.User.Role.STUDENT


@pytest.mark.parametrize(
    'payload',
    (
        {
            'role': engine.User.Role.ADMIN
        },
        {
            'displayedName': secrets.token_hex(6)
        },
        {
            'password': '123456'
        },
    ),
)
@pytest.mark.parametrize(
    'role',
    (
        engine.User.Role.STUDENT,
        engine.User.Role.TEACHER,
    ),
)
def test_non_admin_cannot_update_user_data(
    forge_client,
    role: engine.User.Role,
    payload: Dict[str, Any],
):
    user = utils.user.create_user()
    original_user = user.to_json()
    actor = utils.user.create_user(role=role)
    client = forge_client(actor.username)

    rv, rv_json, _ = BaseTester.request(
        client,
        'patch',
        f'/user/{user.username}',
        json=payload,
    )
    assert rv.status_code == 403, rv_json
    # ensure user is not updated
    assert user.reload().to_json() == original_user


def test_client_can_make_cors_preflight_request(client):
    # CORS-preflight requests must never include credentials, so
    # using a unauthorized client here
    # see more: https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS#preflight_requests_and_credentials
    rv = client.options('/user')
    assert rv.status_code == 200
