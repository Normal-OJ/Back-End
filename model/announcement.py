from flask import Blueprint, request
from .auth import *
from mongo import *
from .utils import *
import os

__all__ = ['announcement_api']

announcement_api = Blueprint('announcement_api', __name__)

@announcement_api.route('/System', methods=['GET'])
def get_system_announcement():
    try:
        system_announcements = get_announcement('Public')
    except:
        return HTTPError('Announcement not exists', 404)
    data = []
    system_announcement = {}
    for i in range(0, len(system_announcements)):
        system_announcement = {
        "title": system_announcements[i].announcement_name,
        "content": system_announcements[i].markdown,
        "author": system_announcements[i].author,
        "create": system_announcements[i].create,
        "update": system_announcements[i].update
        }
        data.append(system_announcement)
    return HTTPResponse('Success get announcement.',200,'ok',data)

@announcement_api.route('/<course>', methods=['GET'])
@login_required
def get_announcement(user,course): #course = rourse_id
    try:
        announcements = get_announcement(course)
    except:
        return HTTPError('Announcement not exists', 404)
    data = []
    announcement = {}
    for i in range(0, len(announcements)):
        announcement = {
        "title": announcements[i].announcement_name,
        "content": announcements[i].markdown,
        "author": announcements[i].author,
        "create": announcements[i].create,
        "update": announcements[i].update
        }
        data.append(announcement)
    return HTTPResponse('Success get announcement.',200,'ok',data)

@announcement_api.route('/', method=['POST','PUT','DELETE'])# admin not add
@Required_json('course','title','content')
@login_required
def modify_announcement(user,course,title,content):
    # if you are a student
    if user.role == 2:# if you are a student
        return HTTPError('Forbidden.You canˊt post announcement.', 403)
    # System announcement must admin
    if course == 'Public' and user.role !=0:
        return HTTPError('Forbidden.You canˊt post announcement.', 403)
    if request.method =='POST':
        r = add_announcement(user,course,title,content)
    
