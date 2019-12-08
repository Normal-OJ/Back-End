import pytest


class TestAdminCourse:
    '''Test courses panel used my admins
    '''
    def test_without_username_and_password(self, client):
        # Signup without username and password
        rv = client.post('/auth/signup', json={'password': 'test'})
        json = rv.get_json()
        assert rv.status_code == 400
        assert json['status'] == 'err'
        assert json['message'] == 'Signup Failed'
        assert json['data']['email'] == 'Field is required'
        assert json['data']['username'] == 'Field is required'
