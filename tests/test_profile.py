import pytest
from tests.base_tester import BaseTester


class TestViewProfile(BaseTester):
    def test_edit_profile(self, client_student):
        rv = client_student.post(
            '/profile',
            json={
                'displayedName': 'aisu_0911',
                'bio': 'Hello World!'
            })
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Uploaded.'

    def test_view_own_profile(self, client_student):
        rv = client_student.get('/profile')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Profile exist.'
        assert json['data']['displayedName'] == 'aisu_0911'
        assert json['data']['bio'] == 'Hello World!'
        '''
        assert json['data'] == [{
            'displayedName': 'aisu_0911',
            'bio': 'Hello World!'
        }]
        '''
