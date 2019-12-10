import pytest
from mongo.user import User
from tests.base_tester import BaseTester


class TestAdminCourse(BaseTester):
    '''Test courses panel used my admins
    '''
    def test_view(self, client_admin):
        # Get all courses
        rv = client_admin.get('/course')
        json = rv.get_json()
        assert json['message'] == 'Success.'
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['data'] == []

    def test_add_with_invalid_username(self, client_admin):
        # add a course with non-existent username
        rv = client_admin.post('/course',
                               json={
                                   'course': 'math',
                                   'teacher': 'adminn'
                               })
        json = rv.get_json()
        assert json['message'] == 'User not found.'
        assert rv.status_code == 404
        assert json['status'] == 'err'

    def test_add(self, client_admin):
        # add a course
        rv = client_admin.post('/course',
                               json={
                                   'course': 'math',
                                   'teacher': 'admin'
                               })
        json = rv.get_json()
        assert json['message'] == 'Success.'
        assert rv.status_code == 200
        assert json['status'] == 'ok'

        rv = client_admin.get('/course')
        json = rv.get_json()
        assert json['data'] == [{'course': 'math', 'teacher': 'admin'}]

    def test_add_with_existent_course_name(self, client_admin):
        # add a course with existent name
        rv = client_admin.post('/course',
                               json={
                                   'course': 'math',
                                   'teacher': 'admin'
                               })
        json = rv.get_json()
        assert json['message'] == 'Course exists.'
        assert rv.status_code == 400
        assert json['status'] == 'err'

    def test_edit_with_invalid_course_name(self, client_admin):
        # edit a course with non-existent course
        rv = client_admin.put('/course',
                              json={
                                  'course': 'history',
                                  'newCourse': 'PE',
                                  'teacher': 'admin'
                              })
        json = rv.get_json()
        assert json['message'] == 'Course not found.'
        assert rv.status_code == 404
        assert json['status'] == 'err'

    def test_edit_with_invalid_username(self, client_admin):
        # edit a course with non-existent username
        rv = client_admin.put('/course',
                              json={
                                  'course': 'math',
                                  'newCourse': 'PE',
                                  'teacher': 'adminn'
                              })
        json = rv.get_json()
        assert json['message'] == 'User not found.'
        assert rv.status_code == 404
        assert json['status'] == 'err'

    def test_edit(self, client_admin):
        # edit a course
        rv = client_admin.put('/course',
                              json={
                                  'course': 'math',
                                  'newCourse': 'PE',
                                  'teacher': 'admin'
                              })
        json = rv.get_json()
        assert json['message'] == 'Success.'
        assert rv.status_code == 200
        assert json['status'] == 'ok'

        rv = client_admin.get('/course')
        json = rv.get_json()
        assert json['data'] == [{'course': 'PE', 'teacher': 'admin'}]

    def test_delete_with_invalid_course_name(self, client_admin):
        # delete a course with non-existent course name
        rv = client_admin.delete('/course', json={'course': 'math'})
        json = rv.get_json()
        assert json['message'] == 'Course not found.'
        assert rv.status_code == 404
        assert json['status'] == 'err'

    def test_delete(self, client_admin):
        # delete a course
        rv = client_admin.delete('/course', json={
            'course': 'PE',
        })
        json = rv.get_json()
        assert json['message'] == 'Success.'
        assert rv.status_code == 200
        assert json['status'] == 'ok'

        rv = client_admin.get('/course')
        json = rv.get_json()
        assert json['data'] == []
