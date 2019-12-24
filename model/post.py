from flask import Blueprint, request
from mongo import *
from .auth import *
from .utils import *
from mongo.post import *
from mongo.course import *

__all__ = ['post_api']

post_api = Blueprint('post_api', __name__)


@post_api.route('/<course>', methods=['GET'])
@login_required
def get_post(user, course):
    try:
        target_course = engine.Course.objects.get(course_name=course)
    except engine.DoesNotExist:
        return HTTPError("Course not found.", 404)
    try:
        target_thread = engine.PostThread.objects.get(course_id=target_course)
    except engine.DoesNotExist:
        return HTTPError("Post/Reply not found.", 404)
    #refer course
    course_name = course
    course_obj = Course(course_name).obj
    permission = perm(course_obj, user)
    if not permission:
        return HTTPError('You are not in this course.', 403)
    data = []
    return HTTPResponse('success', data=data)


@post_api.route('/', methods=['POST', 'PUT', 'DELETE'])
@Request.json('course', 'title', 'content', 'targetThreadId')
@login_required
def modify_post(user, course, title, content, targetThreadId):
    if course == 'Public':
        return HTTPError('You can not add post in system.', 403)
    permission = perm(Course(course).obj, user)
    if not permission:
        return HTTPError('You are not in this course.', 403)
    if request.method == 'POST':
        #add reply
        if not course:
            r = add_reply(targetThreadId, user, content)
        #add course post
        elif not targetThreadId:
            r = add_post(course, user, content, title)
        else:
            return HTTPError(
                'Request is fail,course or targetThreadId must be none', 403)
    if request.method == 'PUT':  #permission not use
        r = edit_post(targetThreadId, user, content, title)
    if request.method == 'DELETE':  #permission not use
        r = delete_post(targetThreadId, user)
    if r is not None:
        return HTTPError(r, 403 if r == "Forbidden." else 404)
    return HTTPResponse('success')
