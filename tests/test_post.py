import pytest
from tests.base_tester import BaseTester


class TestPost(BaseTester):
    '''Test post
    '''
    def test_add_to_invalid_course(self, client_admin):
        # add a post to a non-existent course

        # create a course
        client_admin.post('/course',
                          json={
                              'course': 'math',
                              'teacher': 'admin'
                          })
        client_admin.put('/course/math',
                         json={
                             'TAs': ['admin'],
                             'studentNicknames': {
                                 'student': 'noobs'
                             }
                         })

        rv = client_admin.post('/post',
                               json={
                                   'course': 'PE',
                                   'title': 'Work',
                                   'content': 'Coding.'
                               })
        json = rv.get_json()
        assert rv.status_code == 404
        assert json['message'] == 'Course not exist.'

    def test_add(self, client_student):
        # add a post
        rv = client_student.post('/post',
                                 json={
                                     'course': 'math',
                                     'title': 'Work',
                                     'content': 'Coding.'
                                 })
        json = rv.get_json()
        assert rv.status_code == 200

    def test_view(self, client_student):
        # view posts
        rv = client_student.get('/post/math')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['data'][0]['title'] == 'Work'
        assert json['data'][0]['thread']['content'] == 'Coding.'
        assert json['data'][0]['thread']['author'] == 'student'
        assert json['data'][0]['thread']['reply'] == []
