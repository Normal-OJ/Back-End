from flask import Blueprint, request

from mongo import *
from .auth import *
from .utils import *
from mongo.course import *
from mongo import engine

__all__ = ['course_api']

course_api = Blueprint('course_api', __name__)


@course_api.route('/', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def get_courses(user):
    @Request.json('course', 'new_course', 'teacher')
    def modify_courses(course, new_course, teacher):
        if user.role > 1:
            return HTTPError('Forbidden.', 403)
        r = None
        if user.role == 1:
            teacher = user.username

        try:
            if request.method == 'POST':
                r = add_course(course, teacher)
            if request.method == 'PUT':
                r = edit_course(user, course, new_course, teacher)
            if request.method == 'DELETE':
                r = delete_course(user, course)
        except ValueError:
            return HTTPError('Not allowed name.', 400)
        except NotUniqueError:
            return HTTPError('Course exists.', 400)
        except PermissionError:
            return HTTPError('Forbidden.', 403)
        except engine.DoesNotExist as e:
            return HTTPError(f'{e} not found.', 404)

        return HTTPResponse('Success.')

    if request.method == 'GET':
        data = []
        for co in get_all_courses():
            if perm(co, user):
                data.append({
                    'course': co.course_name,
                    'teacher': co.teacher.username
                })

        return HTTPResponse('Success.', data=data)
    else:
        return modify_courses()


@course_api.route('/<course_name>', methods=['GET', 'PUT'])
@login_required
def get_course(user, course_name):
    course = Course(course_name).obj
    if course is None:
        return HTTPError('Course not found.', 404)

    permission = perm(course, user)
    if not permission:
        return HTTPError('You are not in this course.', 403)

    @Request.json('TAs', 'student_nicknames')
    def modify_course(TAs, student_nicknames):
        if permission < 2:
            return HTTPError('Forbidden.', 403)

        if permission > 2:
            tas = []
            for ta in TAs:
                user = User(ta).obj
                if not User(ta):
                    return HTTPResponse(f'User: {ta} not found.', 404)
                tas.append(user)
            course.tas = tas

        student_dict = {}
        for student, nickname in student_nicknames.items():
            user = User(student).obj
            if not User(student):
                return HTTPResponse(f'User: {student} not found.', 404)
            student_dict[student] = nickname
        course.student_nicknames = student_dict

        course.save()
        return HTTPResponse('Success.')

    if request.method == 'GET':
        tas = []
        for ta in course.tas:
            tas.append(ta.username)

        student_dict = {}
        for student, nickname in course.student_nicknames.items():
            student_dict[student] = nickname

        return HTTPResponse('Success.',
                            data={
                                "teacher": course.teacher.username,
                                "TAs": tas,
                                "studentNicknames": student_dict
                            })
    else:
        return modify_course()
