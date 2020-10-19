from flask import Blueprint, request

from mongo import *
from .auth import *
from .utils import *
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
        for co in get_user_courses(user):
            data.append({'course': co.course_name, 'teacher': co.teacher.info})

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

            for user in set(course.tas) - set(tas):
                remove_user(user, course)
            for user in set(tas) - set(course.tas):
                add_user(user, course)
            course.tas = tas

        student_dict = {}
        for student, nickname in student_nicknames.items():
            user = User(student).obj
            if not User(student):
                return HTTPResponse(f'User: {student} not found.', 404)
            student_dict[student] = nickname

        drop_user = set(course.student_nicknames) - set(student_dict)
        new_user = set(student_dict) - set(course.student_nicknames)

        for user in drop_user:
            remove_user(User(user).obj, course)
        for user in new_user:
            add_user(User(user).obj, course)
        course.student_nicknames = student_dict

        for homework in course.homeworks:
            for user in drop_user:
                del homework.student_status[user]

            user_problems = {}
            for pid in homework.problem_ids:
                user_problems[str(pid)] = Homework.default_problem_status()
            for user in new_user:
                homework.student_status[user] = user_problems

            homework.save()

        course.save()
        return HTTPResponse('Success.')

    if request.method == 'GET':
        student_dict = {}
        for student, nickname in course.student_nicknames.items():
            student_dict[student] = nickname

        return HTTPResponse('Success.',
                            data={
                                "teacher": course.teacher.info,
                                "TAs": [ta.info for ta in course.tas],
                                "studentNicknames": student_dict
                            })
    else:
        return modify_course()


@course_api.route('/<course_name>/grade/<student>',
                  methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def grading(user, course_name, student):
    course = Course(course_name).obj
    if course is None:
        return HTTPError('Course not found.', 404)

    permission = perm(course, user)
    if not permission:
        return HTTPError('You are not in this course.', 403)

    if not User(student) or not student in course.student_nicknames.keys():
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
