from flask import Blueprint, request

from mongo import *
from .auth import *
from .utils import *
from mongo.utils import *
from mongo.course import *
from mongo import engine
from datetime import datetime

__all__ = ['course_api']

course_api = Blueprint('course_api', __name__)


@course_api.route('/', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def get_courses(user):
    @Request.json('course', 'new_course', 'teacher')
    @identity_verify(0, 1)
    def modify_courses(user, course, new_course, teacher):
        r = None
        if user.role == 1:
            teacher = user.username
        try:
            if request.method == 'POST':
                r = Course.add_course(course, teacher)
            if request.method == 'PUT':
                co = Course(course)
                co.edit_course(user, new_course, teacher)
            if request.method == 'DELETE':
                co = Course(course)
                co.delete_course(user)
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
        data = [{
            'course': c.course_name,
            'teacher': c.teacher.info,
        } for c in Course.get_user_courses(user)]
        return HTTPResponse('Success.', data=data)
    else:
        return modify_courses()


@course_api.route('/<course_name>', methods=['GET', 'PUT'])
@login_required
def get_course(user, course_name):
    course = Course(course_name)
    if not course:
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

            for user in set(course.tas) - set(tas):
                course.remove_user(user)
            for user in set(tas) - set(course.tas):
                course.add_user(user)
            course.tas = tas
        try:
            course.update_student_namelist(student_nicknames)
        except engine.DoesNotExist as e:
            return HTTPError(str(e), 404)
        return HTTPResponse('Success.')

    if request.method == 'GET':
        return HTTPResponse(
            'Success.',
            data={
                "teacher": course.teacher.info,
                "TAs": [ta.info for ta in course.tas],
                "students":
                [User(name).info for name in course.student_nicknames]
            },
        )
    else:
        return modify_course()


@course_api.route('/<course_name>/grade/<student>',
                  methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def grading(user, course_name, student):
    course = Course(course_name).obj
    if not course:
        return HTTPError('Course not found.', 404)
    permission = perm(course, user)
    if not permission:
        return HTTPError('You are not in this course.', 403)
    if student not in course.student_nicknames.keys():
        return HTTPError('The student is not in the course.', 404)
    if permission == 1 and (user.username != student
                            or request.method != 'GET'):
        return HTTPError('You can only view your score.', 403)

    def get_score():
        return HTTPResponse(
            'Success.',
            data=[{
                'title': score['title'],
                'content': score['content'],
                'score': score['score'],
                'timestamp': score['timestamp'].timestamp()
            } for score in course.student_scores.get(student, [])])

    @Request.json('title', 'content', 'score')
    def add_score(title, content, score):
        score_list = course.student_scores.get(student, [])
        if title in [score['title'] for score in score_list]:
            return HTTPError('This title is taken.', 400)
        score_list.append({
            'title': title,
            'content': content,
            'score': score,
            'timestamp': datetime.now()
        })
        course.student_scores[student] = score_list
        course.save()
        return HTTPResponse('Success.')

    @Request.json('title', 'new_title', 'content', 'score')
    def modify_score(title, new_title, content, score):
        score_list = course.student_scores.get(student, [])
        title_list = [score['title'] for score in score_list]
        if title not in title_list:
            return HTTPError('Score not found.', 404)
        index = title_list.index(title)
        if new_title is not None:
            if new_title in title_list:
                return HTTPError('This title is taken.', 400)
            title = new_title
        score_list[index] = {
            'title': title,
            'content': content,
            'score': score,
            'timestamp': datetime.now()
        }
        course.student_scores[student] = score_list
        course.save()
        return HTTPResponse('Success.')

    @Request.json('title')
    def delete_score(title):
        score_list = course.student_scores.get(student, [])
        title_list = [score['title'] for score in score_list]
        if title not in title_list:
            return HTTPError('Score not found.', 404)
        index = title_list.index(title)
        del score_list[index]
        course.student_scores[student] = score_list
        course.save()
        return HTTPResponse('Success.')

    methods = {
        'GET': get_score,
        'POST': add_score,
        'PUT': modify_score,
        'DELETE': delete_score
    }
    return methods[request.method]()


@course_api.route('/<course_name>/scoreboard', methods=['GET'])
@login_required
@Request.args('pids: str', 'start', 'end')
@Request.doc('course_name', 'course', Course)
def get_course_scoreboard(user, pids, start, end, course):
    try:
        pids = pids.split(',')
        pids = [int(pid.strip()) for pid in pids]
    except:
        return HTTPError('Error occurred when parsing `pids`.', 400)

    if start:
        try:
            start = float(start)
        except:
            return HTTPError('Type of `start` should be float.', 400)
    if end:
        try:
            end = float(end)
        except:
            return HTTPError('Type of `end` should be float.', 400)

    permission = perm(course, user)
    if permission < 2:
        return HTTPError('Permission denied', 403)

    ret = course.get_scoreboard(pids, start, end)

    return HTTPResponse(
        'Success.',
        data=ret,
    )
