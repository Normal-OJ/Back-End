from flask import Blueprint, request

from .utils import HTTPResponse, HTTPError, Request
from flask.json import jsonify
from mongo.course import *
from .auth import login_required

course_api = Blueprint('course_api', __name__)


@course_api.route('/', methods=['GET', 'POST', 'UPDATE', 'DELETE'])
@login_required
def get_courses(user):
    if user.obj.role != 0:
        return HTTPError('Forbidden.', 403)

    @Request.json(['course', 'new_course', 'teacher'])
    def modify_course(course, new_course, teacher):
        r = None

        if request.method == 'POST':
            r = add_course(course, teacher)
        if request.method == 'UPDATE':
            r = edit_course(course, new_course, teacher)
        if request.method == 'DELETE':
            r = delete_course(course)

        if r != None:
            return HTTPError(r, 404)

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
        return modify_course()


@course_api.route('/<id>', methods=['GET', 'POST'])
@login_required
def get_course(user, id):
    if user.obj.role != 0:
        return HTTPError('Forbidden.', 403)
