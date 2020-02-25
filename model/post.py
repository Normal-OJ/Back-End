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
        target_course = Course(course).obj
    except engine.DoesNotExist:
        return HTTPError("Course not found.", 404)
    permission = perm(target_course, user)
    if not permission:
        return HTTPError('You are not in this course.', 403)
    data = found_post(target_course)
    return HTTPResponse('Success.', data=data)


@post_api.route('/view/<course>/<target_thread_id>', methods=['GET'])
@login_required
def get_single_post(user, course, target_thread_id):
    try:
        target_course = Course(course).obj
    except engine.DoesNotExist:
        return HTTPError("Course not found.", 404)
    permission = perm(target_course, user)
    if not permission:
        return HTTPError('You are not in this course.', 403)
    if not target_thread_id:
        return HTTPError('Must contain target_thread_id', 400)
    data = found_post(target_course, target_thread_id)
    return HTTPResponse('Success.', data=data)


@post_api.route('/', methods=['POST', 'PUT', 'DELETE'])
@Request.json('course', 'title', 'content', 'target_thread_id')
@login_required
def modify_post(user, course, title, content, target_thread_id):
    if course == 'Public':
        return HTTPError('You can not add post in system.', 403)
    if course and target_thread_id:
        return HTTPError(
            'Request is fail,course or target_thread_id must be none.', 400)
    elif course:
        course_obj = Course(course).obj
        if course_obj is None:
            return HTTPError('Course not exist.', 404)
        permission = perm(course_obj, user)
    elif target_thread_id:
        try:
            target_thread = engine.PostThread.objects.get(id=target_thread_id)
        except engine.DoesNotExist:
            try:  # to protect input post id
                target_post = engine.Post.objects.get(id=target_thread_id)
            except engine.DoesNotExist:
                return HTTPError('Post/reply not exist.', 404)
            target_thread = target_post.thread
            target_thread_id = target_thread.id
        if target_thread.status:  # 1 is deleted
            return HTTPResponse('Forbidden,the post/reply is deleted.', 403)
        target_course = target_thread.course_id
        permission = perm(target_course, user)
    else:
        return HTTPError(
            'Request is fail,course and target_thread_id are both none.', 400)
    if not permission:
        return HTTPError('You are not in this course.', 403)
    if request.method == 'POST':
        # add reply
        if course:
            r = add_post(course, user, content, title)
        # add course post
        elif target_thread_id:
            r = add_reply(target_thread, user, content)
    if request.method == 'PUT':
        if course:
            return HTTPError(
                "Request is fail,you should provide target_thread_id replace course.",
                400)
        r = edit_post(target_thread, user, content, title, permission)
    if request.method == 'DELETE':
        if course:
            return HTTPError(
                "Request is fail,you should provide target_thread_id replace course.",
                400)
        r = delete_post(target_thread, user, permission)
    if r is not None:
        return HTTPError(r, 403)
    return HTTPResponse('success.')
