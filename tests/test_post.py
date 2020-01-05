import pytest
from tests.base_tester import BaseTester


class TestPost(BaseTester):
    '''Test post
    '''
    def test_add_post_to_invalid_course(self, client_admin):
        # add a post to a non-existent course

        # create a course
        client_admin.post('/course',
                          json={
                              'course': 'math',
                              'teacher': 'admin'
                          })
        #create an other course
        client_admin.post('/course',
                          json={
                              'course': 'english',
                              'teacher': 'admin'
                          })
        #let student add math
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

    def test_add_post(self, client_student):
        # add a post
        rv = client_student.post('/post',
                                 json={
                                     'course': 'math',
                                     'title': 'Work',
                                     'content': 'Coding.'
                                 })
        json = rv.get_json()
        assert rv.status_code == 200

    def test_add_post_when_not_in_course(self, client_student):
        # create another course in line 17
        # not add student to the course ('english')
        # add a post
        rv = client_student.post('/post',
                                 json={
                                     'course': 'english',
                                     'title': 'Work',
                                     'content': 'Coding.'
                                 })
        json = rv.get_json()
        assert rv.status_code == 403
        assert json['message'] == 'You are not in this course.'

    def test_add_reply(self, client_student):
        rvget = client_student.get('/post/math')
        jsonget = rvget.get_json()
        id = jsonget['data'][0]['thread']['id']  # get post id (thread)
        rv = client_student.post('/post',
                                 json={
                                     'targetThreadId': id,
                                     'title': 'reply',
                                     'content': 'reply message.'
                                 })
        json = rv.get_json()
        assert rv.status_code == 200

    def test_add_reply_to_not_exist_post(self, client_student):
        id = 'aaaabbbbccccdddd00000000'  # not exist id
        rv = client_student.post('/post',
                                 json={
                                     'targetThreadId': id,
                                     'title': 'reply',
                                     'content': 'reply message.'
                                 })
        json = rv.get_json()
        assert rv.status_code == 404
        assert json['message'] == 'Post/reply not exist.'

    def test_delete_post(self, client_student):
        rvget = client_student.get('/post/math')
        jsonget = rvget.get_json()
        id = jsonget['data'][0]['thread']['id']  # get post id (thread)
        rv = client_student.delete('/post', json={'targetThreadId': id})
        json = rv.get_json()
        assert rv.status_code == 200

    def test_add_reply_to_deleted_post(self, client_student):
        rvget = client_student.get('/post/math')
        jsonget = rvget.get_json()
        id = jsonget['data'][0]['thread']['id']  # get post id (thread)
        rv = client_student.post('/post',
                                 json={
                                     'targetThreadId': id,
                                     'title': 'reply to delete',
                                     'content': 'reply to delete message.'
                                 })
        json = rv.get_json()
        assert rv.status_code == 403
        assert json['message'] == 'Forbidden,the post/reply is deleted.'

    def test_edit_reply(self, client_student):
        rvget = client_student.get('/post/math')
        jsonget = rvget.get_json()
        id = jsonget['data'][0]['thread']['reply'][0]['id']  # get reply id
        rv = client_student.put('/post',
                                json={
                                    'targetThreadId': id,
                                    'content': 'The reply is edited.'
                                })
        json = rv.get_json()
        assert rv.status_code == 200

    def test_view(self, client_student):
        rv = client_student.get('/post/math')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['data'][0]['title'] == 'The Post is deleted.'
        assert json['data'][0]['thread']['content'] == 'Content is deleted.'
        assert json['data'][0]['thread']['author']['username'] == 'student'
        assert json['data'][0]['thread']['reply'][0][
            'content'] == 'The reply is edited.'
        assert json['data'][0]['thread']['reply'][0]['author'][
            'username'] == 'student'
