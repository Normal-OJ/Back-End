import pytest
import secrets
from mongo import *
from mongo import engine


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

    def test_signup(self, client):
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

    def test_update(self, client, test_token):
        # Update
        client.set_cookie('test.test', 'piann', test_token)
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
        client.set_cookie('test.test', 'piann', test_token)
        rv = client.get('/auth/session')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Goodbye'
