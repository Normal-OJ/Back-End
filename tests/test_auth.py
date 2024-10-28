import dataclasses
from dataclasses import dataclass
import random
from typing import List, Optional, Union
import pytest
import secrets
from mongo import *
from mongo import engine
from model import get_verify_link
from tests import utils
from tests.conftest import ForgeClient


class TestSignup:
    '''Test Signup
    '''

    def test_without_username_and_email(self, client):
        # Signup without username and password
        rv = client.post('/auth/signup', json={'password': 'test'})
        json = rv.get_json()
        assert rv.status_code == 400
        assert json['status'] == 'err'
        assert json['message'] == 'Requested Value With Wrong Type'

    def test_empty_password(self, client):
        # Signup with empty password
        rv = client.post('/auth/signup',
                         json={
                             'username': 'test',
                             'email': 'test@test.test'
                         })
        json = rv.get_json()
        assert rv.status_code == 400
        assert json['status'] == 'err'
        assert json['message'] == 'Requested Value With Wrong Type'

    def test_too_long_username(self, client):
        name = secrets.token_hex()[:12]
        password = secrets.token_hex()
        rv = client.post('/auth/signup',
                         json={
                             'username': f'tooooooooloooooooooong{name}',
                             'password': password,
                             'email': f'{name}@noj.tw',
                         })
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'Signup Failed'

    def test_invalid_username(self, client):
        name = secrets.token_hex()[:12]
        password = secrets.token_hex()
        rv = client.post('/auth/signup',
                         json={
                             'username': f'invalid/{name}',
                             'password': password,
                             'email': f'{name}@noj.tw',
                         })
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'Not Allowed Name'

    def test_signup(self, client, forge_client):
        # Signup
        rv = client.post('/auth/signup',
                         json={
                             'username': 'test',
                             'password': 'test',
                             'email': 'test@test.test'
                         })
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Signup Success'
        # Signup a second user
        client.post('/auth/signup',
                    json={
                        'username': 'test2',
                        'password': 'test2',
                        'email': 'test2@test.test'
                    })
        client = forge_client('test2')
        rv = client.get('/auth/me')
        assert rv.status_code == 403, rv.get_json()
        assert rv.get_json()['message'] == 'Inactive User'

    def test_used_username(self, client):
        # Signup with used username
        rv = client.post('/auth/signup',
                         json={
                             'username': 'test',
                             'password': 'test',
                             'email': 'test@test.test'
                         })
        json = rv.get_json()
        assert rv.status_code == 400
        assert json['status'] == 'err'
        assert json['message'] == 'User Exists'

    def test_used_email(self, client):
        # Signup with used email
        rv = client.post('/auth/signup',
                         json={
                             'username': 'test3',
                             'password': 'test',
                             'email': 'test@test.test'
                         })
        json = rv.get_json()
        assert rv.status_code == 400
        assert json['status'] == 'err'
        assert json['message'] == 'User Exists'

    def test_directly_add_user_by_admin(self, client):
        client.set_cookie(
            'piann',
            User('first_admin').secret,
            domain='test.test',
        )
        name = secrets.token_hex()[:12]
        assert not User(name), name
        password = secrets.token_hex()
        rv = client.post(
            '/auth/user',
            json={
                'username': name,
                'password': password,
                'email': f'{name}@noj.tw',
            },
        )
        assert rv.status_code == 200, rv.get_json()
        client.delete_cookie('piann', domain='test.test')
        rv = client.post(
            '/auth/session',
            json={
                'username': name,
                'password': password,
            },
        )
        assert rv.status_code == 200, rv.get_json()

    def test_add_user_with_invalid_username(self, forge_client):
        client = forge_client('first_admin')
        name = secrets.token_hex()[:12]
        password = secrets.token_hex()
        rv = client.post('/auth/user',
                         json={
                             'username': f'invalid/{name}',
                             'password': password,
                             'email': f'{name}@noj.tw',
                         })
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'Not Allowed Name'

    def test_add_user_with_too_long_username(self, forge_client):
        client = forge_client('first_admin')
        name = secrets.token_hex()[:12]
        password = secrets.token_hex()
        rv = client.post('/auth/user',
                         json={
                             'username': f'tooooooooloooooooooong{name}',
                             'password': password,
                             'email': f'{name}@noj.tw',
                         })
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'Signup Failed'
        assert rv.get_json()['data']['username'] == 'String value is too long'

    def test_add_user_with_existent_user(self, forge_client):
        client = forge_client('first_admin')
        name = secrets.token_hex()[:12]
        password = secrets.token_hex()
        rv = client.post('/auth/user',
                         json={
                             'username': name,
                             'password': password,
                             'email': f'{name}@noj.tw',
                         })
        assert rv.status_code == 200, rv.get_json()
        rv = client.post('/auth/user',
                         json={
                             'username': name,
                             'password': password,
                             'email': f'{name}@noj.tw',
                         })
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'User Exists'

    @pytest.mark.parametrize('username', ('teacher', 'student'))
    def test_non_admin_cannot_add_user(self, forge_client, username: str):
        client = forge_client(username)
        rv = client.post(
            '/auth/user',
            json={
                'username': secrets.token_hex()[:12],
                'password': secrets.token_hex(),
                'email': secrets.token_hex()[:12] + '@noj.tw',
            },
        )
        assert rv.status_code == 403, rv.get_json()


class TestActive:
    '''Test Active
    '''

    def test_redirect_with_invalid_toke(self, client):
        # Access active-page with invalid token
        rv = client.get('/auth/active/invalid_token')
        json = rv.get_json()
        assert rv.status_code == 403
        assert json['status'] == 'err'
        assert json['message'] == 'Invalid Token'

    def test_redirect(self, client, test_token):
        # Redirect to active-page
        rv = client.get(f'/auth/active/{test_token}')
        json = rv.get_json()
        assert rv.status_code == 302

    def test_update_with_invalid_data(self, client):
        # Update with invalid data
        rv = client.post(
            f'/auth/active',
            json={
                'profile': 123  # profile should be a dictionary
            })
        json = rv.get_json()
        assert rv.status_code == 400
        assert json['status'] == 'err'
        assert json['message'] == 'Requested Value With Wrong Type'

    def test_update_without_agreement(self, client):
        # Update without agreement
        rv = client.post(f'/auth/active',
                         json={
                             'profile': {},
                             'agreement': 123
                         })
        json = rv.get_json()
        assert rv.status_code == 400
        assert json['status'] == 'err'
        assert json['message'] == 'Requested Value With Wrong Type'

    def test_update_without_true_agreement(self, client):
        rv = client.post(f'/auth/active',
                         json={
                             'profile': {},
                             'agreement': False
                         })
        assert rv.status_code == 403, rv.get_json()
        assert rv.get_json()['message'] == 'Not Confirm the Agreement'

    def test_update_with_invalid_token(self, client):
        rv = client.post(f'/auth/active',
                         json={
                             'profile': {},
                             'agreement': True
                         })
        assert rv.status_code == 403, rv.get_json()
        assert rv.get_json()['message'] == 'Invalid Token.'

    def test_update_with_user_not_exists(self, client, monkeypatch):
        from model import auth

        def mock_jwt_decode(_):
            return {
                'secret': 'mock_secret',
                'data': {
                    'username': secrets.token_hex()[:12],
                }
            }

        monkeypatch.setattr(auth, 'jwt_decode', mock_jwt_decode)
        rv = client.post(f'/auth/active',
                         json={
                             'profile': {},
                             'agreement': True
                         })
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'User Not Exists'

    def test_update_public_course_not_exists(self, client, test_token,
                                             monkeypatch):

        def raise_public_course_not_exists(*args, **kwargs):
            raise engine.DoesNotExist('Public Course Not Exists')

        monkeypatch.setattr(User, 'activate', raise_public_course_not_exists)
        client.set_cookie('piann', test_token, domain='test.test')
        rv = client.post(f'/auth/active',
                         json={
                             'profile': {},
                             'agreement': True
                         })
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'Public Course Not Exists'

    def test_update(self, client, test_token):
        # Update
        client.set_cookie('piann', test_token, domain='test.test')
        rv = client.post(
            f'/auth/active',
            json={
                'profile': {
                    'displayedName': 'Test',
                    'bio': 'Hi',
                },
                'agreement': True
            },
        )
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'User Is Now Active'

    def test_update_with_activated_user(self, client, test_token):
        client.set_cookie('piann', test_token, domain='test.test')
        rv = client.post(f'/auth/active',
                         json={
                             'profile': {},
                             'agreement': True
                         })
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'User Has Been Actived'

    @pytest.mark.parametrize(
        'role',
        [
            engine.User.Role.TEACHER,
            engine.User.Role.ADMIN,
            engine.User.Role.STUDENT,
            pytest.param(
                10086,
                marks=pytest.mark.xfail,
            ),
        ],
    )
    def test_update_user_role(self, role):
        u = User.signup(
            username=secrets.token_hex(8),
            password=secrets.token_hex(16),
            email=f'{secrets.token_hex(16)}@noj.tw',
        ).activate()
        u.update(role=role)
        u.reload()
        assert u.role == role


class TestPasswordRecovery:

    def test_recovery_with_user_not_exists(self, client):
        name = secrets.token_hex()[:12]
        rv = client.post('/auth/password-recovery',
                         json={
                             'email': f'{name}_not_exists@test.test',
                         })
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'User Not Exists'

    def test_recovery(self, client):
        rv = client.post('/auth/password-recovery',
                         json={
                             'email': 'test@test.test',
                         })
        assert rv.status_code == 200, rv.get_json()
        assert rv.get_json()['message'] == 'Recovery Email Has Been Sent'
        test_user = User('test')
        assert test_user.user_id != test_user.user_id2


class TestCheckUser:

    def test_name_exists(self, client):
        rv = client.post('/auth/check/username', json={'username': 'test'})
        assert rv.status_code == 200, rv.get_json()
        assert rv.get_json()['message'] == 'User Exists'
        assert rv.get_json()['data']['valid'] == 0

    def test_name_not_exist(self, client):
        name = secrets.token_hex()[:12]
        rv = client.post('/auth/check/username', json={'username': name})
        assert rv.status_code == 200, rv.get_json()
        assert rv.get_json()['message'] == 'Username Can Be Used'
        assert rv.get_json()['data']['valid'] == 1

    def test_email_exists(self, client):
        rv = client.post('/auth/check/email', json={'email': 'test@test.test'})
        assert rv.status_code == 200, rv.get_json()
        assert rv.get_json()['message'] == 'Email Has Been Used'
        assert rv.get_json()['data']['valid'] == 0

    def test_email_not_exist(self, client):
        name = secrets.token_hex()[:12]
        rv = client.post('/auth/check/email',
                         json={'email': f'{name}@test.test'})
        assert rv.status_code == 200, rv.get_json()
        assert rv.get_json()['message'] == 'Email Can Be Used'
        assert rv.get_json()['data']['valid'] == 1

    def test_invalid_type(self, client):
        rv = client.post('/auth/check/invalid')
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'Ivalid Checking Type'


class TestResendEmail:

    def test_user_not_exists(self, client):
        name = secrets.token_hex()[:12]
        rv = client.post('/auth/resend-email',
                         json={'email': f'{name}@test.test'})
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'User Not Exists'

    def test_user_has_been_actived(self, forge_client):
        client = forge_client('first_admin')
        name = secrets.token_hex()[:12]
        password = secrets.token_hex()
        rv = client.post('/auth/user',
                         json={
                             'username': name,
                             'password': password,
                             'email': f'{name}@test.test',
                         })
        assert rv.status_code == 200
        client.delete_cookie('pinna', domain='test.test')
        rv = client.post('/auth/resend-email',
                         json={'email': f'{name}@test.test'})
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'User Has Been Actived'

    def test_normal_resend(self, client):
        rv = client.post('/auth/resend-email',
                         json={'email': 'test2@test.test'})
        assert rv.status_code == 200, rv.get_json()
        assert rv.get_json()['message'] == 'Email Has Been Resent'


class TestLogin:
    '''Test Login
    '''

    def test_incomplete_data(self, client):
        # Login with incomplete data
        rv = client.post('/auth/session', json={})
        json = rv.get_json()
        assert rv.status_code == 400
        assert json['status'] == 'err'
        assert json['message'] == 'Requested Value With Wrong Type'

    def test_wrong_password(self, client):
        # Login with wrong password
        rv = client.post('/auth/session',
                         json={
                             'username': 'test',
                             'password': 'tset'
                         })
        json = rv.get_json()
        assert rv.status_code == 403
        assert json['status'] == 'err'
        assert json['message'] == 'Login Failed'

    def test_not_active(self, client):
        # Login an inactive user
        rv = client.post('/auth/session',
                         json={
                             'username': 'test2',
                             'password': 'test2'
                         })
        json = rv.get_json()
        assert rv.status_code == 403
        assert json['status'] == 'err'
        assert json['message'] == 'Invalid User'

    def test_with_username(self, client):
        # Login with username
        rv = client.post('/auth/session',
                         json={
                             'username': 'test',
                             'password': 'test'
                         })
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Login Success'

    def test_with_email(self, client):
        # Login with email
        rv = client.post('/auth/session',
                         json={
                             'username': 'test@test.test',
                             'password': 'test'
                         })
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Login Success'


class TestLogout:
    '''Test Logout
    '''

    def test_logout(self, client, test_token):
        # Logout
        client.set_cookie('piann', test_token, domain='test.test')
        rv = client.get('/auth/session')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Goodbye'


def test_get_self_data(client):
    rv = client.get('/auth/me')
    assert rv.status_code == 403
    test_user = User('test')
    client.set_cookie('piann', test_user.secret, domain='test.test')
    rv = client.get(
        '/auth/me',
        query_string='fields=username,displayedName',
    )
    assert rv.status_code == 200, rv.get_json()
    rv_data = rv.get_json()['data']
    assert rv_data['username'] == test_user.username
    assert rv_data['displayedName'] == test_user.profile.displayed_name
    rv = client.get('/auth/me')
    assert rv.status_code == 200, rv.get_json()
    rv_data = rv.get_json()['data']
    assert rv_data['username'] == test_user.username
    assert rv_data['displayedName'] == test_user.profile.displayed_name


def test_identity_verify(forge_client):
    client = forge_client('first_admin')
    name = secrets.token_hex()[:12]
    password = secrets.token_hex()
    rv = client.post('/auth/user',
                     json={
                         'username': name,
                         'password': password,
                         'email': f'{name}@noj.tw',
                     })
    assert rv.status_code == 200
    client = forge_client(name)
    rv = client.post(
        '/auth/user',
        json={
            'username': name,
            'password': password,
            'email': f'{name}@noj.tw',
        },
    )
    assert rv.status_code == 403, rv.get_json()
    assert rv.get_json()['message'] == 'Insufficient Permissions'


class TestChangePassword:

    def test_change_password(self, forge_client):
        client = forge_client('first_admin')
        name = secrets.token_hex()[:12]
        password = secrets.token_hex()
        rv = client.post('/auth/user',
                         json={
                             'username': name,
                             'password': password,
                             'email': f'{name}@noj.tw',
                         })
        assert rv.status_code == 200
        client = forge_client(name)
        old_secret = User(name).secret
        new_password = secrets.token_hex()
        rv = client.post('/auth/change-password',
                         json={
                             'oldPassword': password,
                             'newPassword': new_password
                         })
        assert rv.status_code == 200, rv.get_json()
        assert rv.get_json()['message'] == 'Password Has Been Changed'
        client.set_cookie('piann', old_secret, domain='test.test')
        rv = client.get('/auth/me')
        assert rv.status_code == 403, rv.get_json()
        assert rv.get_json()['message'] == 'Authorization Expired'

    def test_change_password_with_wrong_password(self, forge_client):
        client = forge_client('first_admin')
        name = secrets.token_hex()[:12]
        password = secrets.token_hex()
        rv = client.post('/auth/user',
                         json={
                             'username': name,
                             'password': password,
                             'email': f'{name}@noj.tw',
                         })
        assert rv.status_code == 200
        client = forge_client(name)
        bad_password = secrets.token_hex()
        new_password = secrets.token_hex()
        rv = client.post('/auth/change-password',
                         json={
                             'oldPassword': bad_password,
                             'newPassword': new_password
                         })
        assert rv.status_code == 403, rv.get_json()
        assert rv.get_json()['message'] == 'Wrong Password'


class TestBatchSignup:

    @dataclass
    class SignupInput:
        username: str
        password: str
        email: str
        displayed_name: Optional[str]
        role: Optional[int]

        def row(self):
            values = [*dataclasses.astuple(self)]
            while values[-1] is None:
                values.pop()
            values = [('' if v is None else v) for v in values]
            return ','.join(map(str, values))

    @staticmethod
    def cmp_payload_and_user(
        user: User,
        payload: SignupInput,
    ):
        assert user.username == payload.username
        assert user.email == payload.email
        if payload.displayed_name is not None:
            assert user.profile.displayed_name == payload.displayed_name
        if payload.role is not None:
            assert user.role == payload.role
        login = User.login(payload.username, payload.password, "127.0.0.1")
        assert login.username == payload.username

    @classmethod
    def signup_input(
        cls,
        *,
        displayed_name: Optional[Union[str, bool]] = None,
        role: Optional[int] = None,
    ) -> SignupInput:
        '''
        Generate random signup input data
        '''
        username = secrets.token_hex(8)
        password = secrets.token_hex(16)
        email = f'{username}@gmail.com'
        if displayed_name == True:
            displayed_name = secrets.token_urlsafe(8)
        return cls.SignupInput(
            username=username,
            password=password,
            email=email,
            displayed_name=displayed_name,
            role=role,
        )

    @classmethod
    def convert_to_csv(cls, inputs: List[SignupInput]):
        new_users = 'username,password,email,displayedName,role\n'
        new_users += '\n'.join(i.row() for i in inputs)
        return new_users

    def test_normally_register(self, forge_client):
        excepted_users = [self.signup_input() for _ in range(5)]
        client = forge_client('first_admin')
        rv = client.post(
            '/auth/batch-signup',
            json={
                'newUsers': self.convert_to_csv(excepted_users),
            },
        )
        assert rv.status_code == 200, rv.get_json()
        # Ensure the users has been registered
        for u in excepted_users:
            login = User.login(u.username, u.password, "127.0.0.1")
            assert login == User.get_by_username(u.username)

    def test_sign_up_with_invalid_csv(self, monkeypatch, forge_client):
        import csv

        def csv_raise_error(*args, **kwargs):
            raise csv.Error

        monkeypatch.setattr(csv.DictReader, '__next__', csv_raise_error)
        client = forge_client('first_admin')
        rv = client.post(
            '/auth/batch-signup',
            json={
                'newUsers':
                'I am invalid input <3\n'
                'This should raise csv.Error\n',
            },
        )
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'Invalid file content'

    def test_signup_with_course(self, forge_client):
        course_name = secrets.token_urlsafe(10)
        Course.add_course(course_name, 'first_admin')
        excepted_users = [self.signup_input() for _ in range(5)]
        client = forge_client('first_admin')
        rv = client.post(
            '/auth/batch-signup',
            json={
                'newUsers': self.convert_to_csv(excepted_users),
                'course': course_name,
            },
        )
        assert rv.status_code == 200, rv.get_json()
        course = Course(course_name)
        for u in excepted_users:
            assert u.username in course.student_nicknames

    def test_signup_with_existent_user(self, forge_client):
        existent_users = [self.signup_input() for _ in range(5)]
        for u in existent_users:
            u = dataclasses.asdict(u)
            del u['displayed_name']
            del u['role']
            User.signup(**u)
        excepted_users = [self.signup_input() for _ in range(5)]
        excepted_users += existent_users
        course_name = secrets.token_urlsafe(12)
        Course.add_course(course_name, 'first_admin')
        client = forge_client('first_admin')
        rv = client.post(
            '/auth/batch-signup',
            json={
                'newUsers': self.convert_to_csv(excepted_users),
                'course': course_name,
            },
        )
        assert rv.status_code == 200, rv.get_json()
        course = Course(course_name)
        for u in excepted_users:
            login = User.login(u.username, u.password, "127.0.0.1")
            assert login == User.get_by_username(u.username)
            assert u.username in course.student_nicknames

    def test_signup_with_displayed_name(self, forge_client):
        excepted_users = [
            self.signup_input(displayed_name=True) for _ in range(10)
        ]
        client = forge_client('first_admin')
        rv = client.post(
            '/auth/batch-signup',
            json={
                'newUsers': self.convert_to_csv(excepted_users),
            },
        )
        assert rv.status_code == 200, rv.get_json()
        for u in excepted_users:
            login = User.login(u.username, u.password, "127.0.0.1")
            assert login == User.get_by_username(u.username)
            assert login.profile.displayed_name == u.displayed_name

    def test_signup_with_role(self, forge_client):
        excepted_users = [
            self.signup_input(role=random.randint(1, 2)) for _ in range(20)
        ]
        client = forge_client('first_admin')
        rv = client.post(
            '/auth/batch-signup',
            json={
                'newUsers': self.convert_to_csv(excepted_users),
            },
        )
        assert rv.status_code == 200, rv.get_json()
        for u in excepted_users:
            login = User.login(u.username, u.password, "127.0.0.1")
            assert login == User.get_by_username(u.username)
            assert login.role == u.role

    def test_signup_without_optional_field(self, forge_client):
        except_user = self.signup_input()
        client = forge_client('first_admin')
        rv = client.post(
            '/auth/batch-signup',
            json={
                'newUsers': 'username,password,email\n' + except_user.row(),
            },
        )
        assert rv.status_code == 200, rv.get_json()
        login = User.login(except_user.username, except_user.password,
                           "127.0.0.1")
        assert login == User.get_by_username(except_user.username)

    def test_signup_with_invalid_input_format(self, forge_client):
        client = forge_client('first_admin')
        rv = client.post(
            '/auth/batch-signup',
            json={
                'newUsers':
                'I am invalid input <3\n'
                'This should not register any user\n',
            },
        )
        assert rv.status_code == 400, rv.get_json()
        assert 'input' in rv.get_json()['message']

    def test_signup_with_invalid_role(self, forge_client):
        client = forge_client('first_admin')
        rv = client.post(
            '/auth/batch-signup',
            json={
                'newUsers':
                'username,password,email,role\n'
                'fakeuser,1234,fake@n0j.tw,a\n'
            },
        )
        assert rv.status_code == 400, rv.get_json()
        assert 'username' in rv.get_json()['message']
        assert 'role' in rv.get_json()['message']

    def test_signup_with_used_email(self, forge_client):
        client = forge_client('first_admin')
        rv = client.post(
            '/auth/batch-signup',
            json={
                'newUsers':
                'username,password,email\n'
                'fakeuser,1234,i.am.first.admin@noj.tw\n'
            },
        )
        assert rv.status_code == 200, rv.get_json()

    def test_force_signup_should_override_existent_users(
        self,
        forge_client: ForgeClient,
    ):
        existent_users = [
            self.signup_input(
                displayed_name=True,
                role=int(engine.User.Role.TEACHER),
            ) for _ in range(5)
        ]
        for eu in existent_users:
            u = dataclasses.asdict(eu)
            del u['displayed_name']
            del u['role']
            User.signup(**u)
            eu.password += secrets.token_hex(8)

        # ensure they can't login with updated payload
        for u in existent_users:
            with pytest.raises(engine.DoesNotExist):
                User.login(u.username, u.password, "127.0.0.1")
            with pytest.raises(engine.DoesNotExist):
                User.login(u.email, u.password, "127.0.0.1")

        excepted_users = [
            *(self.signup_input() for _ in range(5)),
            *existent_users,
        ]

        course = utils.course.create_course(teacher='first_admin')
        client = forge_client('first_admin')
        rv = client.post(
            '/auth/batch-signup',
            json={
                'newUsers': self.convert_to_csv(excepted_users),
                'course': course.course_name,
                'force': True,
            },
        )
        assert rv.status_code == 200, rv.get_json()

        course.reload()
        for u in excepted_users:
            login = User.login(u.username, u.password, "127.0.0.1")
            self.cmp_payload_and_user(login, u)
            assert u.username in course.student_nicknames

    def test_get_me_with_invalid_field(self, forge_client):
        client = forge_client('first_admin')
        rv = client.get('/auth/me?fields=invalid')
        assert rv.status_code == 400, rv.get_json()


def test_verify_link_without_subdirectory(app):
    server_name = '4pi.n0j.tw'
    app.config['SERVER_NAME'] = server_name

    u = utils.user.create_user()
    expected_url = f'https://{server_name}/auth/active/{u.cookie}'
    with app.app_context():
        assert expected_url == get_verify_link(u)


def test_verify_link_with_subdirectory(app):
    server_name = 'n0j.tw'
    subdirectory = '/4pi'
    app.config['SERVER_NAME'] = server_name
    app.config['APPLICATION_ROOT'] = subdirectory

    u = utils.user.create_user()
    expected_url = f'https://{server_name}{subdirectory}/auth/active/{u.cookie}'
    with app.app_context():
        assert expected_url == get_verify_link(u)
