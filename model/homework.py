import os
from flask import Blueprint, request

from mongo import *
from .utils import *
from .auth import login_required
from .course import course_api

__all__ = ['homework_api']

homework_api = Blueprint('homework_api', __name__)


@homework_api.route('/', methods=['POST'])
@homework_api.route('/<homework_id>', methods=['PUT', 'DELETE', 'GET'])
@login_required
def homework_entry(user, homework_id=None):
    '''
    apply a operation to single homework
    '''
    @Request.json('name', 'course_name', 'markdown', 'start', 'end',
                  'problem_ids', 'scoreboard_status')
    def add_homework(course_name, name, markdown, start, end, problem_ids,
                     scoreboard_status):
        try:
            homework = Homework.add_hw(user=user,
                                       course_name=course_name,
                                       markdown=markdown,
                                       hw_name=name,
                                       start=start,
                                       end=end,
                                       problem_ids=problem_ids,
                                       scoreboard_status=scoreboard_status)
        except NameError:
            return HTTPError('user must be the teacher or ta of this course',
                             403)
        except FileExistsError:
            return HTTPError('homework exists in this course', 400)
        return HTTPResponse('Add homework Success')

    @Request.json('name', 'markdown', 'start', 'end', 'problem_ids',
                  'scoreboard_status')
    def update_homework(name, markdown, start, end, problem_ids,
                        scoreboard_status):
        try:
            homework = Homework.update(user=user,
                                       homework_id=homework_id,
                                       markdown=markdown,
                                       new_hw_name=name,
                                       start=start,
                                       end=end,
                                       problem_ids=problem_ids,
                                       scoreboard_status=scoreboard_status)
        except NameError:
            return HTTPError('user must be the teacher or ta of this course',
                             403)
        except FileNotFoundError:
            return HTTPError('course not exist', 404)
        except FileExistsError:
            return HTTPError(
                'the homework with the same name exists in this course', 400)
        return HTTPResponse('Update homework Success')

    def delete_homework():
        try:
            homework = Homework.delete_problems(user, homework_id)
        except NameError:
            return HTTPError('user must be the teacher or ta of this course',
                             403)
        except FileNotFoundError:
            return HTTPError('homework not exists, unable to delete', 404)
        return HTTPResponse('Delete homework Success')

    def get_homework():
        try:
            homework = Homework.get_by_id(homework_id)
        except FileNotFoundError:
            return HTTPError('homework not exists', 404)
        return HTTPResponse('get homework',
                            data={
                                'name': homework.homework_name,
                                'start':
                                int(homework.duration.start.timestamp()),
                                'end': int(homework.duration.end.timestamp()),
                                'problemIds': homework.problem_ids,
                                'markdown': homework.markdown
                            })

    handler = {
        'GET': get_homework,
        'POST': add_homework,
        'PUT': update_homework,
        'DELETE': delete_homework
    }

    return handler[request.method]()


@course_api.route('/<course_name>/homework', methods=['GET'])
@login_required
def get_homework_list(user, course_name):
    '''
    get a list of homework
    '''
    try:
        homeworks = Homework.get_homeworks(course_name)
        data = []
        for homework in homeworks:
            # convert to dict
            homework = homework.to_mongo()
            # field convertion
            homework.update({
                'id': str(homework['_id']),
                'start': homework['duration']['start'],
                'end': homework['duration']['end']
            })
            del homework['_id']
            del homework['duration']
            # normal user can not view student status
            if user.role > 1:
                del homework["studentStatus"]

            data.append(homework)
    except FileNotFoundError:
        return HTTPError('course not exists',
                         404,
                         data={'courseName': course_name})
    return HTTPResponse('get homeworks', data=data)


@homework_api.route('/check/<homework_name>')
@login_required
@Request.json('course_name')
def check(user, homework_name, course_name):
    course = Course(course_name)
    role = perm(course, user)

    if role <= 1:
        return HTTPError('students can not call this API', 403)
    if Homework.get_by_name(course_name, homework_name) is None:
        return HTTPResponse('homework name can be used', data={'valid': 1})
    else:
        return HTTPResponse('homework name exist', data={'valid': 0})
