from flask import Blueprint, request
from mongo import *
from mongo import engine
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
    permission = perm(target_course, user)
    if not permission:
        return HTTPError('You are not in this course.', 403)
    data = found_post(target_course)
    return HTTPResponse('success', data=data)


@post_api.route('/', methods=['POST', 'PUT', 'DELETE'])
@Request.json('course', 'title', 'content', 'targetThreadId')
@login_required
def modify_post(user, course, title, content, targetThreadId):
    if course == 'Public':
        return HTTPError('You can not add post in system.', 403)
    # 0 1 or 1 0
    if course and targetThreadId:
        return HTTPError(
            'Request is fail,course or targetThreadId must be none', 403)
    elif course:
        try:
            course_obj = Course(course).obj
        except engine.DoesNotExist:
            return HTTPError('Course not exist', 404)
        permission = perm(course_obj, user)
    elif targetThreadId:
        try:
            target_thread = engine.PostThread.objects.get(id=targetThreadId)
        except engine.DoesNotExist:
            try:  # to protect input post id
                target_post = engine.Post.objects.get(id=targetThreadId)
            except engine.DoesNotExist:
                return HTTPError('Post/reply not exist', 404)
                target_thread = target_post.thread
                targetThreadId = target_thread.id
        target_course = target_thread.course_id
        permission = perm(target_course, user)
    else:
        return HTTPError(
            'Request is fail,course or targetThreadId must be none', 403)
    if not permission:
        return HTTPError('You are not in this course.', 403)
    if request.method == 'POST':
        #add reply
        if course:
            r = add_post(course, user, content, title)
        #add course post
        elif targetThreadId:
            r = add_reply(target_thread, user, content)
    if request.method == 'PUT':
        if course:
            return HTTPError(
                "Request is fail,you should provide targetThreadId replace course ",
                403)
        r = edit_post(target_thread, user, content, title, permission)
    if request.method == 'DELETE':
        if course:
            return HTTPError(
                "Request is fail,you should provide targetThreadId replace course ",
                403)
        r = delete_post(target_thread, user, permission)
    if r is not None:
        return HTTPError(r, 403)
    return HTTPResponse('success')
