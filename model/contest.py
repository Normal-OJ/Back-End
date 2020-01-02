from flask import Blueprint, request
from .auth import *
from mongo.contest import *
from mongoengine import DoesNotExist, NotUniqueError
from .utils import HTTPResponse, HTTPRedirect, HTTPError, Request
from .course import course_api
import os

__all__ = ['contest_api']

contest_api = Blueprint('contest_api', __name__)


@course_api.route('/<course_name>/content',
                  methods=['POST', 'PUT', 'DELETE', 'GET'])
@Request.json('name', 'new_name', 'start', 'end', 'problem_ids',
              'scoreboard_status', 'contest_mode')
@login_required
def contest(user, course_name, name, new_name, start, end, problem_ids,
            scoreboard_status, contest_mode):
    if request.method == 'POST':
        try:
            contest = Contest.add_contest(user, course_name, name,
                                          problem_ids, scoreboard_status,
                                          contest_mode, start, end)
        except NotUniqueError:
            return HTTPError(
                'the same contest name has already exist in course', 400)
        except AuthorityError:
            return HTTPError('user must be the teacher or ta of this course',
                             403)
        return HTTPResponse('Add contest Success')
    if request.method == 'PUT':
        try:
            Contest.update(user, course_name, name, new_name, start, end,
                           problem_ids, scoreboard_status, contest_mode)
        except DoesNotExist:
            return HTTPError('the contest does not exist in this course', 404)
        except NotUniqueError:
            return HTTPError(
                'the same contest name has already exist in this course', 400)
        except AuthorityError:
            HTTPError('user must be the teacher or ta of this course', 403)
        return HTTPResponse('update contest Success')
    if request.method == 'DELETE':
        try:
            Contest.delete(user, course_name, name)
        except AuthorityError:
            return HTTPError('user must be the teacher or ta of this course',
                             403)
        return HTTPResponse('delete contest Success')
    if request.method == 'GET':
        try:
            contests = Contest.get_course_contests(course_name)
            data = []
            for x in contests:
                contest = {
                    "name": x.name,
                    "start": int(x.duration.start.timestamp()),
                    "end":  int(x.duration.end.timestamp()),
                    "id": str(x.id)
                }
                if (user.role <= 1):
                    contest["participants"] = x.participants
                data.append(contest)
        except DoesNotExist:
            return HTTPError('course not exists', 404)
        return HTTPResponse('get contest', data=data)


@contest_api.route('/view/<id>', methods=['GET'])
@login_required
def get_single_contest(user, id):
    try:
        data = Contest.get_single_contest(user, id)
    except DoesNotExist:
        return HTTPError('unable to find contest', 404)
    return HTTPResponse('get contest success', data=data)


@contest_api.route('/', methods=['GET'])
@login_required
def check_user_is_in_contest(user):
    try:
        contest = get_user_contest(user)
    except DoesNotExist:
        HTTPError('user is not in contest', 404)
    return HTTPResponse('get contest success',
                        data={
                            "name": contest.name,
                            "id": contest.id
                        })


@contest_api.route('/join/<id>', methods=['GET'])
@login_required
def join_contest(user, id):
    try:
        Contest.add_user_in_contest(user, id)
    except DoesNotExist:
        return HTTPError('contest is not exist', 404)
    except UserIsNotInCourse:
        return HTTPError("user not in the contest's course", 403)
    except ExistError:
        return HTTPError("user is already in a contest", 400)
    return HTTPResponse('user join contest success')


@contest_api.route('/leave', methods=['GET'])
@login_required
def leave_contest(user):
    try:
        Contest.user_leave_contest(user)
    except UserIsNotInCourse:
        return HTTPError("user not in the contest", 400)
    return HTTPResponse('user leave contest success')
