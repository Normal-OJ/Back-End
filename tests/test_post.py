import pytest
from tests.base_tester import BaseTester
from mongo import Course


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
        # create an other course
        client_admin.post('/course',
                          json={
                              'course': 'english',
                              'teacher': 'admin'
                          })
        # let student add math
        client_admin.put('/course/math',
                         json={
                             'TAs': ['admin'],
                             'studentNicknames': {
                                 'student': 'noobs',
                                 'student-2': 'noobs-2'
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

    def test_add_post_to_public(self, client_admin):
        rv = client_admin.post('/post', json={
            'course': 'Public',
        })
        assert rv.status_code == 403, rv.get_json()
        assert rv.get_json()['message'] == 'You can not add post in system.'

    def test_add_post_with_course_and_thread_id(self, client_admin):
        rv = client_admin.post('/post',
                               json={
                                   'course': 'CourseName',
                                   'targetThreadId': 'ThreadId',
                               })
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json(
        )['message'] == 'Request is fail,course or target_thread_id must be none.'

    def test_add_post_without_course_and_thread_id(self, client_admin):
        rv = client_admin.post('/post', json={})
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json(
        )['message'] == 'Request is fail,course and target_thread_id are both none.'

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

    def test_add_reply_too_deep(self, client_student):
        rvget = client_student.get('/post/math')
        id = rvget.get_json()['data'][0]['thread']['reply'][0]['id']
        rv = client_student.post('/post',
                                 json={
                                     'targetThreadId': id,
                                     'title': 'deep reply',
                                     'content': 'reply message.'
                                 })
        rvget = client_student.get('/post/math')
        id = rvget.get_json(
        )['data'][0]['thread']['reply'][0]['reply'][0]['id']
        rv = client_student.post('/post',
                                 json={
                                     'targetThreadId': id,
                                     'title': 'Deeeeeeper reply',
                                     'content': 'reply message.'
                                 })
        assert rv.status_code == 403, rv.get_json()
        assert rv.get_json(
        )['message'] == 'Forbidden,you can not reply too deap (not open).'

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

    def test_edit_post_without_perm(self, forge_client):
        id = str(Course('math').posts[0].id)
        client_student = forge_client('student-2')
        rv = client_student.put('/post', json={
            'targetThreadId': id,
        })
        assert rv.status_code == 403, rv.get_json()
        assert rv.get_json(
        )['message'] == 'Forbidden, you don\'t have enough permission to edit it.'

    def test_delete_post_without_perm(self, forge_client):
        id = str(Course('math').posts[0].id)
        client_student = forge_client('student-2')
        rv = client_student.delete('/post', json={'targetThreadId': id})
        assert rv.status_code == 403, rv.get_json()
        assert rv.get_json(
        )['message'] == 'Forbidden, you don\'t have enough permission to delete it.'

    def test_delete_post(self, client_student):
        rvget = client_student.get('/post/math')
        jsonget = rvget.get_json()
        id = jsonget['data'][0]['thread']['id']  # get post id (thread)
        rv = client_student.delete('/post', json={'targetThreadId': id})
        json = rv.get_json()
        assert rv.status_code == 200

    def test_delete_post_without_thread_id(self, client_student):
        rv = client_student.delete('/post',
                                   json={
                                       'course': 'math',
                                       'content': 'The reply is edited.'
                                   })
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json(
        )['message'] == 'Request is fail,you should provide target_thread_id replace course.'

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

    def test_edit_reply_without_thread_id(self, client_student):
        rv = client_student.put('/post',
                                json={
                                    'course': 'math',
                                    'content': 'The reply is edited.'
                                })
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json(
        )['message'] == 'Request is fail,you should provide target_thread_id replace course.'

    def test_view(self, client_student):
        rv = client_student.get('/post/math')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['data'][0]['title'] == '*The Post was deleted*'
        assert json['data'][0]['thread']['content'] == '*Content was deleted.*'
        assert json['data'][0]['thread']['author']['username'] == 'student'
        assert json['data'][0]['thread']['reply'][0][
            'content'] == 'The reply is edited.'
        assert json['data'][0]['thread']['reply'][0]['author'][
            'username'] == 'student'

    def test_view_with_course_does_not_exist(self, client_student):
        rv = client_student.get('/post/CourseDoesNotExist')
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'Course not found.'

    def test_view_from_non_course_member(self, make_course, forge_client):
        c_data = make_course('teacher')
        client_student = forge_client('student')
        rv = client_student.get(f'/post/{c_data.name}')
        assert rv.status_code == 403, rv.get_json()
        assert rv.get_json()['message'] == 'You are not in this course.'

    def test_view_thread_does_not_exist(self, client_student):
        rv = client_student.get('/post/view/math/ThreadDoesNotExist')
        assert rv.status_code == 200, rv.get_json()
        assert rv.get_json()['data'] == []

    def test_view_thread_with_course_does_not_exist(self, client_student):
        rv = client_student.get('/post/view/CourseDoesNotExist/aaabbbccc')
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'Course not found.'

    def test_view_thread_from_non_course_member(self, make_course,
                                                forge_client):
        c_data = make_course('teacher')
        client_student = forge_client('student')
        rv = client_student.get(f'/post/view/{c_data.name}/aaabbbccc')
        assert rv.status_code == 403, rv.get_json()
        assert rv.get_json()['message'] == 'You are not in this course.'

    def test_view_thread_without_thread_id(self, make_course, forge_client):
        c_data = make_course('teacher')
        client_teacher = forge_client('teacher')
        rv = client_teacher.get(f'/post/view/{c_data.name}/aaabbcc/')
        assert rv.status_code == 200, rv.get_json()
        assert rv.get_json()['data'] == []
