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
    posts = found_post(target_course)
    '''try:
        target_thread = engine.PostThread.objects.get(course_id=target_course)
    except engine.DoesNotExist:
        return HTTPError("Post/Reply not found.", 404)'''
    #refer course
    data = []
    thread = []
    for x
    return HTTPResponse('success', data=data)


@post_api.route('/', methods=['POST', 'PUT', 'DELETE'])
@Request.json('course', 'title', 'content', 'targetThreadId')
@login_required
def modify_post(user, course, title, content, targetThreadId):
    if course == 'Public':
        return HTTPError('You can not add post in system.', 403)
    if course and targetThreadId:
        return HTTPError(
            'Request is fail,course or targetThreadId must be none', 403)
    elif course:
        try:
            permission = perm(Course(course).obj, user)
        except engine.DoesNotExist:
            return HTTPError('Course not exist', 404)
    elif targetThreadId:
        try:
            target_thread = engine.PostThread.objects.get(id=targetThreadId)
        except engine.DoesNotExist:
            try:  # to protect input post id
                target_post = engine.Post.objects.get(id=targetThreadId)
                target_thread = target_post.thread
                targetThreadId = target_thread.id
            except engine.DoesNotExist:
                return HTTPError('Post/reply not exist', 404)
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
    if request.method == 'PUT':  #permission not use
        if course:
            return HTTPError(
                "Request is fail,you should provide targetThreadId replace course ",
                403)
        r = edit_post(target_thread, user, content, title, permission)
    if request.method == 'DELETE':  #permission not use
        if course:
            return HTTPError(
                "Request is fail,you should provide targetThreadId replace course ",
                403)
        r = delete_post(target_thread, user, permission)
    if r is not None:
        return HTTPError(r, 403 if r == "Forbidden." else 404)
    return HTTPResponse('success')
