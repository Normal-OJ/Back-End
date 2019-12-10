import pytest
from mongo.user import User


class TestAdminCourse:
    '''Test courses panel used my admins
    '''
    def test_view(self, client_test):
        # Get all courses
        User('test').obj.update(role=0)  # Set to admin

        rv = client_test.get('/course')
        json = rv.get_json()
        assert json['message'] == 'Success.'
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['data'] == []

    def test_add_with_invalid_username(self, client_test):
        # add a course with non-existent username
        rv = client_test.post('/course',
                              json={
                                  'course': 'math',
                                  'teacher': 'testt'
                              })
        json = rv.get_json()
        assert json['message'] == '"User not found."'
        assert rv.status_code == 404
        assert json['status'] == 'err'

    def test_add(self, client_test):
        # add a course
        rv = client_test.post('/course',
                              json={
                                  'course': 'math',
                                  'teacher': 'test'
                              })
        json = rv.get_json()
        assert json['message'] == 'Success.'
        assert rv.status_code == 200
        assert json['status'] == 'ok'

        rv = client_test.get('/course')
        json = rv.get_json()
        assert json['data'] == [{'course': 'math', 'teacher': 'test'}]
