from flask import Blueprint, request
from .auth import *
from mongo import *
from .utils import *
from mongo.announcement import *
from mongo.course import *
from datetime import datetime
import os

__all__ = ['announcement_api']

announcement_api = Blueprint('announcement_api', __name__)


@announcement_api.route('/System', methods=['GET'])
def get_system_announcement():
    try:
        system_announcements = found_announcement('Public')
    except:
        return HTTPError('Announcement not exists', 404)
    data = []
    system_announcement = {}
    for x in system_announcements:
        system_announcement = {
            "id": str(x.id),
            "title": x.announcement_name,
            "content": x.markdown,
            "author": x.author.username,
            "created": x.created.timestamp(),
            "updated": x.updated.timestamp()
        }
        data.append(system_announcement)
    return HTTPResponse('Success get announcement.', 200, 'ok', data)


@announcement_api.route('/<course>', methods=['GET'])
@login_required
def get_announcement(user, course):  #course = course_name
    announcements = None
    try:
        announcements = found_announcement(course)
    except engine.engine.DoesNotExist:
        return HTTPError('Announcement not exists', 404)
    except FileNotFoundError:
        return HTTPError('Announcement not exists', 404)
    except FileExistsError:
        return HTTPError('Announcement not exists', 404)
    #refer course
    course_name = course
    course_obj = Course(course_name).obj
    permission = perm(course_obj, user)
    if not permission:
        return HTTPError('You are not in this course.', 403)
    data = []
    announcement = {}
    for x in announcements:
        announcement = {
            "id": str(x.id),
            "title": x.announcement_name,
            "content": x.markdown,
            "author": x.author.username,
            "created": x.created.timestamp(),
            "updated": x.updated.timestamp()
        }
        data.append(announcement)
    return HTTPResponse('Success get announcement.', data=data)


@announcement_api.route('/', methods=['POST', 'PUT', 'DELETE'])
@Request.json('course', 'title', 'content', 'targetAnnouncementId')
@login_required
def modify_announcement(user, course, title, content,
                        targetAnnouncementId):  # course = course_name
    #refer course
    '''permission 4: admin, 3: teacher, 2: TA, 1: student, 0: not found
    '''
    forbidden_message = 'Forbidden.You donˊt have authority to post/edit announcement.'
    # if you only want to edit() or delete(), have id not know couse
    if course == "":
        course = "Public"
    course_obj = Course(course).obj
    if course_obj is None:
        return HTTPError('Course not found.', 404)
    permission = perm(course_obj, user)
    if permission == 0:
        return HTTPError('You are not in this course.', 403)
    if permission == 1:
        return HTTPError(forbidden_message, 403)
    # System announcement must admin
    if course == 'Public' and user.role != 0:
        return HTTPError(forbidden_message, 403)
    r = None  # r set Response message
    if request.method == 'POST':
        r = add_announcement(user, course, title, content)
    if request.method == 'PUT':
        r = edit_announcement(user, title, content, targetAnnouncementId)
    if request.method == 'DELETE':
        r = delete_announcement(user, targetAnnouncementId)
    # Response
    if r is not None:
        return HTTPError(r, 404)

    return HTTPResponse('Success modify announcement.')
