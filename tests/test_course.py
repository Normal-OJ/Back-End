import pytest
from tests.base_tester import BaseTester


class TestAdminCourse(BaseTester):
    '''Test courses panel used my admins
    '''
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

    def test_add_with_invalid_course_name(self, client_admin):
        # add a course with not allowed course name
        rv = client_admin.post('/course',
                               json={
                                   'course': '體育',
                                   'teacher': 'admin'
                               })
        json = rv.get_json()
        assert json['message'] == 'Not allowed name.'
        assert rv.status_code == 400

    def test_add(self, client_admin):
        # add courses
        rv = client_admin.post('/course',
                               json={
                                   'course': 'math',
                                   'teacher': 'admin'
                               })
        json = rv.get_json()
        assert rv.status_code == 200

        rv = client_admin.post('/course',
                               json={
                                   'course': 'history',
                                   'teacher': 'teacher'
                               })
        json = rv.get_json()
        assert rv.status_code == 200

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

    def test_edit_with_invalid_course_name(self, client_admin):
        # edit a course with non-existent course
        rv = client_admin.put('/course',
                              json={
                                  'course': 'c++',
                                  'newCourse': 'PE',
                                  'teacher': 'teacher'
                              })
        json = rv.get_json()
        assert json['message'] == 'Course not found.'
        assert rv.status_code == 404

    def test_edit_with_invalid_username(self, client_admin):
        # edit a course with non-existent username
        rv = client_admin.put('/course',
                              json={
                                  'course': 'history',
                                  'newCourse': 'PE',
                                  'teacher': 'teacherr'
                              })
        json = rv.get_json()
        assert json['message'] == 'User not found.'
        assert rv.status_code == 404

    def test_edit(self, client_admin):
        # edit a course
        rv = client_admin.put('/course',
                              json={
                                  'course': 'history',
                                  'newCourse': 'PE',
                                  'teacher': 'teacher'
                              })
        json = rv.get_json()
        assert rv.status_code == 200

    def test_delete_with_invalid_course_name(self, client_admin):
        # delete a course with non-existent course name
        rv = client_admin.delete('/course', json={'course': 'art'})
        json = rv.get_json()
        assert json['message'] == 'Course not found.'
        assert rv.status_code == 404

    def test_delete_with_non_owner(self, client_teacher):
        # delete a course with a user that is not the owner nor an admin
        rv = client_teacher.delete('/course', json={'course': 'math'})
        json = rv.get_json()
        assert json['message'] == 'Forbidden.'
        assert rv.status_code == 403

    def test_delete(self, client_admin):
        # delete a course
        rv = client_admin.delete('/course', json={
            'course': 'math',
        })
        json = rv.get_json()
        assert rv.status_code == 200

    def test_view(self, client_admin):
        # Get all courses
        rv = client_admin.get('/course')
        json = rv.get_json()
        assert rv.status_code == 200
        # The first one is 'Public'
        assert len(json['data']) == 2
        assert json['data'][-1]['course'] == 'PE'
        assert json['data'][-1]['teacher']['username'] == 'teacher'

    def test_view_with_non_member(self, client_student):
        # Get all courses with a user that is not a member
        rv = client_student.get('/course')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['data'] == []


class TestTeacherCourse(BaseTester):
    '''Test courses panel used my teachers and admins
    '''
    def test_modify_invalid_course(self, client_admin):
        # modify a non-existent course

        # create a course
        client_admin.post('/course',
                          json={
                              'course': 'math',
                              'teacher': 'teacher'
                          })

        rv = client_admin.put('/course/PE',
                              json={
                                  'TAs': ['admin'],
                                  'studentNicknames': {
                                      'student': 'noobs'
                                  }
                              })
        json = rv.get_json()
        assert json['message'] == 'Course not found.'
        assert rv.status_code == 404

    def test_modify_when_not_in_course(self, forge_client):
        # modify a course when not in it
        client = forge_client('teacher-2')
        rv = client.put('/course/math',
                        json={
                            'TAs': ['admin'],
                            'studentNicknames': {
                                'student': 'noobs'
                            }
                        })
        json = rv.get_json()
        assert json['message'] == 'You are not in this course.'
        assert rv.status_code == 403

    def test_modify_with_invalid_user(self, client_admin):
        # modify a course with non-exist user
        rv = client_admin.put('/course/math',
                              json={
                                  'TAs': ['admin'],
                                  'studentNicknames': {
                                      'studentt': 'noobs'
                                  }
                              })
        json = rv.get_json()
        assert json['message'] == 'User: studentt not found.'
        assert rv.status_code == 404

    def test_modify(self, client_teacher):
        # modify a course
        rv = client_teacher.put('/course/math',
                                json={
                                    'TAs': ['teacher'],
                                    'studentNicknames': {
                                        'student': 'noobs',
                                    }
                                })
        json = rv.get_json()
        assert rv.status_code == 200

        rv = client_teacher.get('/course')
        json = rv.get_json()
        print(json)

        assert len(json['data']) == 1
        assert rv.status_code == 200

    def test_modify_with_only_student(self, client_student):
        # modify a course when not TA up
        rv = client_student.put('/course/math',
                                json={
                                    'TAs': ['admin'],
                                    'studentNicknames': {
                                        'student': 'noobs'
                                    }
                                })
        json = rv.get_json()
        assert json['message'] == 'Forbidden.'
        assert rv.status_code == 403

    def test_view(self, client_student):
        # view a course
        rv = client_student.get('/course/math')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['data']['TAs'][0]['username'] == 'teacher'
        assert json['data']['teacher']['username'] == 'teacher'
        assert json['data']['students'][0]['username'] == 'student'


class TestCourseGrade(BaseTester):
    '''Test grading feature in courses
    '''
    def test_add_score(self, client_admin):
        # add scores

        # create a course
        client_admin.post('/course',
                          json={
                              'course': 'math',
                              'teacher': 'admin'
                          })

        # add a student
        client_admin.put('/course/math',
                         json={
                             'TAs': ['admin'],
                             'studentNicknames': {
                                 'student': 'noobs'
                             }
                         })

        rv = client_admin.post('/course/math/grade/student',
                               json={
                                   'title': 'exam',
                                   'content': 'hard',
                                   'score': 'A+',
                               })

        assert rv.status_code == 200

        rv = client_admin.post('/course/math/grade/student',
                               json={
                                   'title': 'exam2',
                                   'content': 'easy',
                                   'score': 'F',
                               })

        assert rv.status_code == 200

    def test_add_existed_score(self, client_admin):
        # add an existed score
        rv = client_admin.post('/course/math/grade/student',
                               json={
                                   'title': 'exam',
                                   'content': '?',
                                   'score': 'B',
                               })

        assert rv.status_code == 400
        json = rv.get_json()
        assert json['message'] == 'This title is taken.'

    def test_modify_score(self, client_admin):
        # modify a score
        rv = client_admin.put('/course/math/grade/student',
                              json={
                                  'title': 'exam2',
                                  'newTitle': 'exam2 (edit)',
                                  'content': 'easy',
                                  'score': 'E',
                              })

        assert rv.status_code == 200

    def test_student_modify_score(self, client_student):
        # modify a score while being a student
        rv = client_student.put('/course/math/grade/student',
                                json={
                                    'title': 'exam',
                                    'newTitle': 'exam (edit)',
                                    'content': 'super hard',
                                    'score': 'A+++++',
                                })

        assert rv.status_code == 403
        json = rv.get_json()
        assert json['message'] == 'You can only view your score.'

    def test_modify_non_existed_score(self, client_admin):
        # modify a score that is not existed
        rv = client_admin.put('/course/math/grade/student',
                              json={
                                  'title': 'exam3',
                                  'newTitle': 'exam2 (edit)',
                                  'content': 'easy',
                                  'score': 'E',
                              })

        assert rv.status_code == 404
        json = rv.get_json()
        assert json['message'] == 'Score not found.'

    def test_delete_score(self, client_admin):
        # delete a score
        rv = client_admin.delete('/course/math/grade/student',
                                 json={'title': 'exam'})

        assert rv.status_code == 200

    def test_get_score(self, client_student):
        # get scores
        rv = client_student.get('/course/math/grade/student')

        json = rv.get_json()
        assert rv.status_code == 200
        assert len(json['data']) == 1
        assert json['data'][0]['title'] == 'exam2 (edit)'
        assert json['data'][0]['content'] == 'easy'
        assert json['data'][0]['score'] == 'E'

    def test_get_score_when_not_in_course(self, client_teacher):
        # get scores when not in the course
        rv = client_teacher.get('/course/math/grade/student')

        assert rv.status_code == 403
        json = rv.get_json()
        assert json['message'] == 'You are not in this course.'
