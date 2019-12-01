from flask import Blueprint, request
from functools import wraps
from mongo import course, NotUniqueError, ValidationError

from .utils import HTTPResponse, HTTPRedirect, HTTPError, Request, send_noreply
from flask.json import jsonify
from mongo.course import *

course_api = Blueprint('auth_api', __name__)


@course_api.route('/course', methods=['GET', 'POST', 'UPDATE', 'DELETE'])
@login_required
def get_course(user):
    if user.obj.role != 0:
        return HTTPError('Forbidden.', 403)

    if request.method == 'GET':
        data = []
        for co in get_all_courses:
            data.append({'course': co.course_name,
                         'teacher': co.teacher_id.username})

        return HTTPResponse('Success.', data=jsonify(data))

    r = None

    if request.method == 'POST':
        r = add_course()
    if request.method == 'UPDATE':
        r = edit_course()
    if request.method == 'DELETE':
        r = delete_course()

    if r == -1:
        return HTTPError('Course not found.', 404)
    if r == -2:
        return HTTPError('Teacher not found.', 404)

    return HTTPResponse('Success.')
