from flask import Blueprint, request
from .auth import *
from mongo import User, HomeWork, course
from .utils import HTTPResponse, HTTPRedirect, HTTPError, Request
import os

__all__ = ['hw_api']

hw_api = Blueprint('hw_api', __name__)


@hw_api.route('/<course_name>', methods=['POST', 'PUT', 'DELETE', 'GET'])
@Request.json('name', 'newname', 'markdown', 'start', 'end', 'problemIds',
              'scoreboardStatus')
@login_required
def add_hw(user,
           course_name,
           name,
           newname,
           markdown,
           start,
           end,
           problemIds=[],
           scoreboardStatus=0):
    scoreboard_status = scoreboardStatus
    if request.method == 'POST':
        try:
            homework = HomeWork.add_hw(user, course_name, markdown, name,
                                       start, end, problemIds,
                                       scoreboard_status)
        except NameError:
            return HTTPError('user must be the teacher or ta of this course',
                             403)
        except FileExistsError:
            return HTTPError('homework exists in this course', 400)
        return HTTPResponse(
            'Add homework Success',
            200,
            'ok',
        )
    if request.method == 'PUT':
        try:
            homework = HomeWork.update(user, course_name, markdown, name,
                                       newname, start, end, problemIds,
                                       scoreboard_status)
        except NameError:
            return HTTPError('user must be the teacher of this course', 403)
        except FileNotFoundError:
            return HTTPError('course not exist', 404)
        except FileExistsError:
            return HTTPError(
                'the homework with the same name exists in this course', 400)
        return HTTPResponse('Update homework Success', 200, 'ok')
    if request.method == 'DELETE':
        try:
            homework = HomeWork.delete_problems(user, course_name, name)
        except NameError:
            return HTTPError('user must be the teacher of this course', 403)
        except FileNotFoundError:
            return HTTPError('homework not exists,unable delete', 404)
        return HTTPResponse('Delete homework Success', 200, 'ok')
    if request.method == 'GET':
        try:
            homeworks = HomeWork.get_homeworks(course_name)
            data = []
            homework = {}
            for i in range(0, len(homeworks)):
                homework = {
                    "name": homeworks[i].name,
                    "markdown": homeworks[i].markdown,
                    "start": homeworks[i].duration.start,
                    "end": homeworks[i].duration.end,
                    "problemIds": homeworks[i].problem_ids,
                    "scoreboard_status": homeworks[i].scoreboard_status
                }
                if (user.role <= 1):
                    homework["studentStatus"] = homeworks[i].student_status
                data.append(homework)
        except FileNotFoundError:
            return HTTPError('course not exists', 404)
        return HTTPResponse('get homeworks', 200, 'ok', data)


@hw_api.route('/get/<id>', methods=['GET'])
@login_required
def get_homework(user, id):
    try:
        homework = HomeWork.get_signal_homework(id)
    except FileNotFoundError:
        return HTTPError('homework not exists', 404)
    return HTTPResponse('get homeworks',
                        200,
                        'ok',
                        data={
                            "name": homework.name,
                            "start": homework.duration.start,
                            "end": homework.duration.end,
                            "problemIds": homework.problem_ids
                        })
