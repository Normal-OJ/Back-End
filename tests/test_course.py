from mongo import engine, Course, Homework, User
from mongo import DoesNotExist
from tests.conftest import ForgeClient
from tests.base_tester import BaseTester
from tests import utils

import pytest

import secrets


class TestAdminCourse(BaseTester):
    '''Test courses panel used my admins
    '''

    def test_add_with_invalid_username(self, client_admin):
        # add a course with non-existent username
        rv = client_admin.post(
            '/course',
            json={
                'course': 'math',
                'teacher': secrets.token_hex(4),
            },
        )
        json = rv.get_json()
        assert json['message'] == 'User not found.'
        assert rv.status_code == 404

    def test_add_with_invalid_course_name(self, client_admin):
        # add a course with not allowed course name
        rv = client_admin.post(
            '/course',
            json={
                'course': '體育',
                'teacher': 'admin',
            },
        )
        json = rv.get_json()
        assert json['message'] == 'Not allowed name.'
        assert rv.status_code == 400

    def test_add(self, client_admin):
        # add courses
        rv = client_admin.post(
            '/course',
            json={
                'course': 'math',
                'teacher': 'admin',
            },
        )
        json = rv.get_json()
        assert rv.status_code == 200

        rv = client_admin.post(
            '/course',
            json={
                'course': 'history',
                'teacher': 'teacher',
            },
        )
        json = rv.get_json()
        assert rv.status_code == 200

    def test_add_with_existent_course_name(self, client_admin):
        # add a course with existent name
        rv = client_admin.post(
            '/course',
            json={
                'course': 'math',
                'teacher': 'admin',
            },
        )
        json = rv.get_json()
        assert json['message'] == 'Course exists.', json
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
        assert 'User' in json['message']
        assert rv.status_code == 404

    def test_modify(self, client_teacher, problem_ids):
        Homework.add(
            user=User('teacher'),
            course_name='math',
            markdown=f'# HW 87\n\naaabbbbccccccc',
            hw_name='HW87',
            start=0,
            end=0,
            problem_ids=problem_ids('teacher', 3),
            scoreboard_status=0,
        )

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

    def test_modify_with_ta_does_not_exist(self, client_teacher):
        rv = client_teacher.put('/course/math',
                                json={
                                    'TAs': ['TADoesNotExist'],
                                    'studentNicknames': {}
                                })
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'User: TADoesNotExist not found.'

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

    def test_modify_remove_ta(self, client_teacher):
        rv = client_teacher.put('/course/math',
                                json={
                                    'TAs': [],
                                    'studentNicknames': {}
                                })
        assert rv.status_code == 200
        assert Course('math').tas == []


class TestCourseGrade(BaseTester):
    '''Test grading feature in courses
    '''

    def test_grading_with_course_does_not_exist(self, client_admin):
        rv = client_admin.post('/course/CourseDoesNotExist/grade/student',
                               json={
                                   'title': 'exam',
                                   'content': 'hard',
                                   'score': 'A+',
                               })
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'Course not found.'

    def test_grading_with_student_does_not_exist(self, client_admin):
        rv = client_admin.post('/course/Public/grade/StudentDoesNotExist',
                               json={
                                   'title': 'exam',
                                   'content': 'hard',
                                   'score': 'A+',
                               })
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'The student is not in the course.'

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

    def test_modify_existed_score(self, client_admin):
        # modify a score
        rv = client_admin.put('/course/math/grade/student',
                              json={
                                  'title': 'exam2 (edit)',
                                  'newTitle': 'exam',
                                  'content': 'easy',
                                  'score': 'E',
                              })

        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'This title is taken.'

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

    def test_delete_score_does_not_exist(self, client_admin):
        # delete a score
        rv = client_admin.delete('/course/math/grade/student',
                                 json={'title': 'exam'})

        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'Score not found.'

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


class TestScoreBoard(BaseTester):

    def test_view_with_invalid_pids(self, client_admin):
        rv = client_admin.get(f'/course/Public/scoreboard?pids=invalid,pids')
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json(
        )['message'] == 'Error occurred when parsing `pids`.'

    def test_view_with_invalid_start(self, client_admin):
        rv = client_admin.get(
            f'/course/Public/scoreboard?pids=1,2,3&start=invalid')
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'Type of `start` should be float.'

    def test_view_with_invalid_end(self, client_admin):
        rv = client_admin.get(
            f'/course/Public/scoreboard?pids=1,2,3&end=invalid')
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'Type of `end` should be float.'

    def test_admin_can_view_scoreboard(self, forge_client: ForgeClient):
        course = utils.course.create_course()
        client = forge_client('first_admin')
        rv = client.get(f'/course/{course.course_name}/scoreboard?pids=1,2,3')
        assert rv.status_code == 200, rv.json

    def test_teacher_can_view_scoreboard(self, forge_client: ForgeClient):
        course = utils.course.create_course()
        client = forge_client(course.teacher.username)
        rv = client.get(
            f'/course/{course.course_name}/scoreboard?pids=1,2,3&start=1&end=1'
        )
        assert rv.status_code == 200, rv.json

    def test_student_cannot_view_scoreboard(
        self,
        forge_client: ForgeClient,
    ):
        user = utils.user.create_user(role=engine.User.Role.STUDENT)
        course = utils.course.create_course(students=[user])
        client = forge_client(user.username)
        rv = client.get(f'/course/{course.course_name}/scoreboard?pids=1,2,3')
        assert rv.status_code == 403, rv.json

    def test_teacher_role_cannot_view_scoreboard(
        self,
        forge_client: ForgeClient,
    ):
        '''
        Users that has role 'teacher' but is not the teacher of that
        course should not have permission to view scoreboard
        '''
        course = utils.course.create_course()
        user = utils.user.create_user(role=engine.User.Role.TEACHER)
        assert user != course.teacher
        client = forge_client(user.username)
        rv = client.get(f'/course/{course.course_name}/scoreboard?pids=1,2,3')
        assert rv.status_code == 403, rv.json


class TestMongoCourse(BaseTester):

    def test_add_user_to_course_does_not_exist(self):
        course = Course('CourseDoesNotExist')
        with pytest.raises(DoesNotExist):
            course.add_user(User('student'))

    def test_edit_with_invalid_course_name(self):
        course = Course('Public')
        with pytest.raises(ValueError):
            course.edit_course(User('admin'), '!nval!d/name', 'teacher')

    def test_edit_without_perm(self, make_course):
        c_data = make_course('teacher')
        course = Course(c_data.name)
        with pytest.raises(PermissionError):
            course.edit_course(User('student'), 'NewName', 'teacher')

    def test_edit_with_new_teacher(self, make_course):
        c_data = make_course('teacher')
        course = Course(c_data.name)
        assert course.edit_course(User('admin'), 'NewName', 'student')
        assert course.teacher.username == 'student'

    def test_add_without_perm(self):
        with pytest.raises(PermissionError):
            Course.add_course('NewCourse', 'student')

    def test_add_and_get_public(self):
        course = Course('Public')
        course.edit_course(User('admin'), 'OldPublic', 'admin')
        assert Course.get_public().course_name == 'Public'


class TestCourseSummary(BaseTester):

    def test_course_summary(self, client_admin, app):
        client_admin.post('/course',
                          json={
                              'course': 'math',
                              'teacher': 'admin'
                          })
        client_admin.post('/course',
                          json={
                              'course': 'history',
                              'teacher': 'teacher'
                          })

        math_course = Course('math')
        history_course = Course('history')

        math_problem = utils.problem.create_problem(
            course=math_course.course_name, owner=User('admin'))
        history_problem = utils.problem.create_problem(
            course=history_course.course_name, owner=User('teacher'))

        math_course.add_user(User('student'))
        history_course.add_user(User('student'))

        Homework.add(
            user=User('admin'),
            course_name=math_course.course_name,
            markdown='',
            hw_name='HW1',
            start=0,
            end=0,
            problem_ids=[math_problem.id],
            scoreboard_status=0,
        )

        with app.app_context():
            utils.submission.create_submission(
                user=User('student'),
                problem=math_problem,
                score=100,
            )
            utils.submission.create_submission(
                user=User('student'),
                problem=history_problem,
                score=100,
            )
            utils.submission.create_submission(
                user=User('teacher'),
                problem=history_problem,
                score=0,
            )

        rv = client_admin.get('/course/summary')
        json = rv.get_json()

        assert rv.status_code == 200, json
        assert json['data']['courseCount'] == 3  # Includes 'Public' course
        assert len(json['data']['breakdown']) == 3

        breakdown = sorted(json['data']['breakdown'],
                           key=lambda x: x['course'])
        expected_breakdown = sorted(
            [
                {
                    'course': 'Public',
                    'userCount':
                    1,  # In testing, we have only one user `first_admin`
                    'homeworkCount': 0,
                    'submissionCount': 0,
                    'problemCount': 0,
                },
                {
                    'course': 'math',
                    'userCount': 2,
                    'homeworkCount': 1,
                    'submissionCount': 1,
                    'problemCount': 1,
                },
                {
                    'course': 'history',
                    'userCount': 2,
                    'homeworkCount': 0,
                    'submissionCount': 2,
                    'problemCount': 1,
                },
            ],
            key=lambda x: x['course'])
        assert breakdown == expected_breakdown, breakdown
