from flask import Blueprint, request

from .utils import HTTPResponse, HTTPError, Request
from flask.json import jsonify
from mongo.course import *
from .auth import *
from mongoengine.errors import NotUniqueError

course_api = Blueprint('course_api', __name__)


@course_api.route('/', methods=['GET', 'POST', 'PUT', 'DELETE'])
@identity_verify(0)
@login_required
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

            if r != None:
                return HTTPError(r, 404)
        except NotUniqueError as ne:
            return HTTPError('Course exists', 400)

        return HTTPResponse('Success.')

    if request.method == 'GET':
        data = []
        for co in get_all_courses():
            data.append({
                'course': co.course_name,
                'teacher': co.teacher_id.username
            })

        return HTTPResponse('Success.', data=data)
    else:
        return modify_courses()


@course_api.route('/<course_name>', methods=['GET', 'POST'])
@identity_verify(0, 1)
@login_required
def get_course(user, course_name):
    course = Course(course_name).obj
    if course is None:
        return HTTPError('Course not found.', 404)
    if user.obj.role != 0 or course.teacher_id != user.obj:
        return HTTPError('Forbidden.', 403)

    @Request.json(['TAs', 'students'])
    def modify_course(TAs, students):
        try:
            tas = []
            for ta in TAs:
                user = User(ta).obj
                if user is None:
                    return HTTPResponse(f'User: {ta} not found.', 404)
                tas.append(user)

            student_dict = {}
            for student, nickname in students:
                user = User(student).obj
                if user is None:
                    return HTTPResponse(f'User: {student} not found.', 404)
                student_dict[user] = nickname

            course.ta_ids = tas
            course.students = student_dict
            course.save()
            return HTTPResponse('Success.')
        except:
            return HTTPError('Upload failed.')

    if request.method == 'GET':
        tas = []
        for ta in course.ta_ids:
            tas.append(ta.username)

        student_dict = {}
        for student, nickname in course.students.items:
            student_dict[student.username] = nickname

        return HTTPResponse('Success.', data={"TAs": tas, "students": student_dict})
    else:
        return modify_course()
