import pytest
from tests.base_tester import BaseTester


class TestProfile(BaseTester):
    def test_edit(self, client_student):
        rv = client_student.post('/profile',
                                 json={
                                     'displayedName': 'aisu_0911',
                                     'bio': 'Hello World!'
                                 })
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Uploaded.'

    def test_view_without_username(self, client_student):
        rv = client_student.get('/profile')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Profile exist.'
        assert json['data']['displayedName'] == 'aisu_0911'
        assert json['data']['bio'] == 'Hello World!'

    def test_view_with_username(self, client_student):
        rv = client_student.get('/profile/student')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Profile exist.'
        assert json['data']['displayedName'] == 'aisu_0911'
        assert json['data']['bio'] == 'Hello World!'

    def test_view_with_nonexist_username(self, client_student):
        rv = client_student.get('/profile/a_username_not_exist')
        json = rv.get_json()
        assert rv.status_code == 404
        assert json['status'] == 'err'
        assert json['message'] == 'Profile not exist.'

    def test_set_invalid_config(self, client_student):
        rv = client_student.put('/profile/config',
                                json={
                                    'fontSize': 87,
                                    'theme': 'default',
                                    'indentType': 1,
                                    'tabSize': 4,
                                    'language': 0
                                })
        json = rv.get_json()
        assert rv.status_code == 400
        assert json['status'] == 'err'
        assert json['message'] == 'Update fail.'