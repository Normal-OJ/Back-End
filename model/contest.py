from flask import Blueprint, request
from .auth import *
from mongo import User
from mongo.contest import *
from mongoengine import DoesNotExist,NotUniqueError
from .utils import HTTPResponse, HTTPRedirect, HTTPError, Request
import os

__all__ = ['contest_api']

contest_api = Blueprint('contest_api', __name__)

@contest_api.route('/<course_name>', methods=['POST', 'PUT', 'DELETE', 'GET'])
@Request.json('name','new_name','start','end','problem_ids','scoreboard_status')
@login_required
def contest(user,course_name,name,new_name,start,end,problem_ids,scoreboard_status):
    if request.method == 'POST':
       try:
           Contest.add_contest(user,course_name,name,start,end,problem_ids,scoreboard_status)
       except NotUniqueError:
           return HTTPError('the same contest name has already exist in course',400)
       except AuthorityError:
           return HTTPError('user must be the teacher or ta of this course',403)
       return HTTPResponse(
            'Add contest Success',
            200,
            'ok',
        )
    if request.method == 'PUT':
       try:
           Contest.update(user,course_name,name,new_name,start,end,problem_ids,scoreboard_status)
       except DoesNotExist:
           return HTTPError('the contest does not exist in this course',404)
       except NotUniqueError:
           return HTTPError('the same contest name has already exist in this course',400)
       except AuthorityError:
           HTTPError('user must be the teacher or ta of this course',403)
       return HTTPResponse(
            'update contest Success',
            200,
            'ok',
        )    
    if request.method == 'DELETE':
       try:
           Contest.delete(user,course_name,name)
       except AuthorityError:
           return HTTPError('user must be the teacher or ta of this course',403)
       return HTTPResponse(
            'delete contest Success',
            200,
            'ok',
        )
    if request.method == 'GET':
        try:
            contests = Contest.get_course_contests(course_name)
            data = []
            for x in contests:
                contest = {
                    "name": x.name,
                    "markdown": x.markdown,
                    "start": x.duration.start,
                    "end": x.end,
                    "problemIds":x.problem_ids,
                    "scoreboard_status": x.scoreboard_status
                }
                if (user.role <= 1):
                    contest["participants"] = x.participants
                data.append(homework)
        except DoesNotExist:
            return HTTPError('course not exists', 404)
        return HTTPResponse('get contest', 200, 'ok', data)

@contest_api.route('/get/<id>', methods=['GET'])
@Request.json('name','start','end','problem_ids')
@login_required
def get_single_contest(user,contest_name,name,start,end,problem_ids):
    try:
        contest = Contest.get_single_contest(id)
    except DoesNotExist:
        HTTPError('unable to find contest',404)
    return HTTPResponse('get contest success',
                        200,
                        'ok',
                        data={
                            "name": contest.name,
                            "start": contest.duration.start,
                            "end": contest.duration.end,
                            "problemIds": contest.problem_ids
                        })