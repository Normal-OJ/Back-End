import pytest
from tests.base_tester import BaseTester


class TestInbox(BaseTester):
    '''Test inbox
    '''

    def test_send_with_invalid_username(self, client_student):
        # send inbox with all invalide user
        rv = client_student.post('/inbox',
                                 json={
                                     'receivers': ['nobody'], 'title': 'hi', 'message': 'AAA'
                                 })
        json = rv.get_json()
        assert json['message'] == 'At least one receiver is required'
        assert rv.status_code == 400
        assert json['status'] == 'err'

    def test_send_with_invalid_info(self, client_student):
        # send inbox with wierd info
        rv = client_student.post('/inbox',
                                 json={
                                     'receivers': ['teacher'], 'title': {}, 'message': 'AAA'
                                 })
        json = rv.get_json()
        assert json['message'] == 'Failed to Send a Message'
        assert rv.status_code == 400
        assert json['status'] == 'err'

    def test_send(self, client_student):
        # send inbox
        rv = client_student.post('/inbox',
                                 json={
                                     'receivers': ['teacher'], 'title': 'hi', 'message': 'AAA'
                                 })
        json = rv.get_json()
        assert json['message'] == 'Successfully Send'
        assert rv.status_code == 200
        assert json['status'] == 'ok'

    def test_view(self, client_admin):
        # Get all courses
        rv = client_admin.get('/inbox')
        json = rv.get_json()
        assert json['message'] == 'Received List'
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['data'] == [{'course': 'math', 'teacher': 'admin'}]

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

    def test_view(self, client_admin):
        # Get all courses
        rv = client_admin.get('/course')
        json = rv.get_json()
        assert json['message'] == 'Success.'
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['data'] == [{'course': 'math', 'teacher': 'admin'}]

    def test_view_with_non_member(self, client_student):
        # Get all courses with a user that is not a member
        rv = client_student.get('/course')
        json = rv.get_json()
        assert json['message'] == 'Success.'
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['data'] == []

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

    def test_delete_with_non_owner(self, client_teacher):
        # delete a course with a user that is not the owner nor an admin
        rv = client_teacher.delete('/course', json={'course': 'PE'})
        json = rv.get_json()
        assert json['message'] == 'Forbidden.'
        assert rv.status_code == 403
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
