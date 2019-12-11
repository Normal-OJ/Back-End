from flask import Blueprint, request

from mongo import *
from .auth import *
from .utils import *

__all__ = ['course_api']

course_api = Blueprint('course_api', __name__)


@course_api.route('/', methods=['GET', 'POST', 'PUT', 'DELETE'])
@identity_verify(0)
def get_courses(user):
    @Request.json(['course', 'new_course', 'teacher'])
    def modify_courses(course, new_course, teacher):
        r = None

        try:
            if request.method == 'POST':
                r = add_course(course, teacher)
            if request.method == 'PUT':
                r = edit_course(course, new_course, teacher)
            if request.method == 'DELETE':
                r = delete_course(course)

            if r is not None:
                return HTTPError(r, 404)
        except NotUniqueError as ne:
            return HTTPError('Course exists.', 400)

        return HTTPResponse('Success.')

    if request.method == 'GET':
        data = []
        for co in get_all_courses():
            data.append({
                'course': co.course_name,
                'teacher': co.teacher.username
            })

        return HTTPResponse('Success.', data=data)
    else:
        return modify_courses()


@course_api.route('/<course_name>', methods=['GET', 'POST'])
@identity_verify(0, 1)
def get_course(user, course_name):
    course = Course(course_name).obj
    if course is None:
        return HTTPError('Course not found.', 404)
    if user.obj.role != 0 and course.teacher != user.obj:
        return HTTPError('Forbidden.', 403)

    @Request.json(['TAs', 'student_nicknames'])
    def modify_course(TAs, student_nicknames):
        tas = []
        for ta in TAs:
            user = User(ta).obj
            if user is None:
                return HTTPResponse(f'User: {ta} not found.', 404)
            tas.append(user)

        student_dict = {}
        for student, nickname in student_nicknames.items():
            user = User(student).obj
            if user is None:
                return HTTPResponse(f'User: {student} not found.', 404)
            student_dict[student] = nickname

        course.tas = tas
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
                                "TAs": tas,
                                "studentNicknames": student_dict
                            })
    else:
        return modify_course()
