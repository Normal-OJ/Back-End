from fastapi import APIRouter, Depends
from mongo import *
from mongo import engine
from .auth import login_required
from .utils import *
from .schemas import ModifyPostBody
from mongo.utils import *
from mongo.post import *
from mongo.course import *

__all__ = ['post_router']

post_router = APIRouter()


@post_router.get('/{course}')
def get_post(course: str, user=Depends(login_required)):
    target_course = Course(course)
    if not target_course:
        return HTTPError("Course not found.", 404)
    if not target_course.permission(user, Course.Permission.VIEW):
        return HTTPError('You are not in this course.', 403)
    data = Post.found_post(target_course)
    return HTTPResponse('Success.', data=data)


@post_router.get('/view/{course}/{target_thread_id}')
def get_single_post(course: str,
                    target_thread_id: str,
                    user=Depends(login_required)):
    target_course = Course(course)
    if not target_course:
        return HTTPError("Course not found.", 404)
    if not target_course.permission(user, Course.Permission.VIEW):
        return HTTPError('You are not in this course.', 403)
    data = Post.found_post(target_course, target_thread_id)
    return HTTPResponse('Success.', data=data)


def _resolve_post_target(body: ModifyPostBody, user):
    """Shared logic to resolve course/thread context and check permissions."""
    course = body.course
    target_thread_id = body.target_thread_id

    if course == 'Public':
        return HTTPError('You can not add post in system.',
                         403), None, None, None

    if course and target_thread_id:
        return HTTPError(
            'Request is fail,course or target_thread_id must be none.',
            400), None, None, None

    if course:
        course_obj = Course(course)
        if not course_obj:
            return HTTPError('Course not exist.', 404), None, None, None
        target_course = course_obj
        target_thread = None
    elif target_thread_id:
        try:
            target_thread = engine.PostThread.objects.get(id=target_thread_id)
        except engine.DoesNotExist:
            try:
                target_post = engine.Post.objects.get(id=target_thread_id)
            except engine.DoesNotExist:
                return HTTPError('Post/reply not exist.',
                                 404), None, None, None
            target_thread = target_post.thread
            target_thread_id = target_thread.id
        if target_thread.status:
            return HTTPResponse('Forbidden,the post/reply is deleted.',
                                403), None, None, None
        target_course = Course(target_thread.course_id)
    else:
        return HTTPError(
            'Request is fail,course and target_thread_id are both none.',
            400), None, None, None

    capability = target_course.own_permission(user)
    if not (capability & Course.Permission.VIEW):
        return HTTPError('You are not in this course.', 403), None, None, None

    return None, target_course, target_thread, capability


@post_router.post('')
def add_post(body: ModifyPostBody, user=Depends(login_required)):
    err, target_course, target_thread, capability = _resolve_post_target(
        body, user)
    if err is not None:
        return err
    course = body.course
    target_thread_id = body.target_thread_id
    if course:
        r = Post.add_post(course, user, body.content, body.title)
    else:
        r = Post.add_reply(target_thread, user, body.content)
    if r is not None:
        return HTTPError(r, 403)
    return HTTPResponse('success.')


@post_router.put('')
def edit_post(body: ModifyPostBody, user=Depends(login_required)):
    err, target_course, target_thread, capability = _resolve_post_target(
        body, user)
    if err is not None:
        return err
    if body.course:
        return HTTPError(
            "Request is fail,you should provide target_thread_id replace course.",
            400)
    r = Post.edit_post(target_thread, user, body.content, body.title,
                       capability)
    if r is not None:
        return HTTPError(r, 403)
    return HTTPResponse('success.')


@post_router.delete('')
def delete_post(body: ModifyPostBody, user=Depends(login_required)):
    err, target_course, target_thread, capability = _resolve_post_target(
        body, user)
    if err is not None:
        return err
    if body.course:
        return HTTPError(
            "Request is fail,you should provide target_thread_id replace course.",
            400)
    r = Post.delete_post(target_thread, user, capability)
    if r is not None:
        return HTTPError(r, 403)
    return HTTPResponse('success.')
