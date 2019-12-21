from flask import Blueprint, request
from .auth import *
from mongo import *
from .utils import *
from mongo.announcement import *
from mongo import announcement
from datetime import datetime, timedelta
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
    return HTTPResponse('Success get announcement.',200,'ok',data)

@announcement_api.route('/<course>', methods=['GET'])
@login_required
def get_announcement(user,course): #course = course_name
    try:
        announcements = found_announcement(course)
    except:
        return HTTPError('Announcement not exists', 404)
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
    return HTTPResponse('Success get announcement.',200,'ok',data)

@announcement_api.route('/', methods=['POST','PUT','DELETE'])
@Request.json('course','title','content','targetAnnouncementId')
@login_required
def modify_announcement(user,course,title,content,targetAnnouncementId):# course = course_name
    # if you are a student
    if user.role == 2:
        return HTTPError('Forbidden.You donˊt have authority to post/edit announcement.', 403)
    # System announcement must admin
    if course == 'Public' and user.role !=0:
        return HTTPError('Forbidden.You donˊt have authority to post/edit announcement.', 403)
    r = None # r set Response message
    if request.method == 'POST':
        r = add_announcement(user,course,title,content)
    if request.method == 'PUT':
        r = edit_announcement(user,course,title,content,targetAnnouncementId)
    if request.method == 'DELETE':
        r = delete_announcement(user,targetAnnouncementId)
    # Response
    if r == "Forbidden, Only author can edit." or r == "Forbidden, Only author can delete.":
        return HTTPError(r, 403)
    if r is not None:
        return HTTPError(r, 404)

    return HTTPResponse('Success',200,'ok')
