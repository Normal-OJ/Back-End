from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends

from mongo import *
from mongo.utils import *
from .auth import login_required
from .utils import *
from .schemas import CreateAnnouncementBody, UpdateAnnouncementBody, DeleteAnnouncementBody
from .course import course_router

__all__ = ['ann_router']

ann_router = APIRouter()


def _format_ann(an):
    return {
        'annId': str(an.id),
        'title': an.title,
        'createTime': int(an.create_time.timestamp()),
        'updateTime': int(an.update_time.timestamp()),
        'creator': an.creator.info,
        'updater': an.updater.info,
        'markdown': an.markdown,
        'pinned': an.pinned,
    }


@ann_router.get('')
@ann_router.get('/{ann_id}')
def get_sys_ann(ann_id: Optional[str] = None):
    public_name = Course.get_public().course_name
    anns = Announcement.ann_list(None, public_name)
    data = [
        _format_ann(an) for an in anns
        if ann_id is None or str(an.id) == ann_id
    ]
    return HTTPResponse('Sys Ann bro', data=data)


@course_router.get('/{course_name}/ann')
def get_course_announcements(course_name: str, user=Depends(login_required)):
    try:
        anns = Announcement.ann_list(user.obj, course_name)
    except (DoesNotExist, ValidationError):
        return HTTPError('Cannot Access a Announcement', 403)
    if anns is None:
        return HTTPError('Announcement Not Found', 404)
    data = [_format_ann(an) for an in anns]
    return HTTPResponse('Announcement List', data=data)


@ann_router.get('/{course_name}/{ann_id}')
def get_ann_by_id(course_name: str, ann_id: str, user=Depends(login_required)):
    try:
        anns = Announcement.ann_list(user.obj, course_name)
    except (DoesNotExist, ValidationError):
        return HTTPError('Cannot Access a Announcement', 403)
    if anns is None:
        return HTTPError('Announcement Not Found', 404)
    data = [_format_ann(an) for an in anns if str(an.id) == ann_id]
    return HTTPResponse('Announcement List', data=data)


@ann_router.post('')
def create_announcement(body: CreateAnnouncementBody,
                        user=Depends(login_required)):
    try:
        ann = Announcement.new_ann(
            title=body.title,
            creator=user.obj,
            markdown=body.markdown,
            pinned=body.pinned,
            course=body.course_name or 'Public',
        )
    except ValidationError as ve:
        return HTTPError('Failed to Create Announcement',
                         400,
                         data=ve.to_dict())
    if ann is None:
        return HTTPError('Failed to Create Announcement', 403)
    data = {
        'annId': str(ann.id),
        'createTime': int(ann.create_time.timestamp()),
    }
    return HTTPResponse('Announcement Created', data=data)


@ann_router.put('')
def update_announcement(body: UpdateAnnouncementBody,
                        user=Depends(login_required)):
    ann = Announcement(body.ann_id)
    if not ann:
        return HTTPError('Announcement Not Found', 404)
    course = Course(ann.course)
    if not course.permission(user, Course.Permission.GRADE):
        return HTTPError('Failed to Update Announcement', 403)
    try:
        ann.update(
            title=body.title,
            markdown=body.markdown,
            update_time=datetime.now(),
            updater=user.obj,
            pinned=body.pinned,
        )
    except ValidationError as ve:
        return HTTPError('Failed to Update Announcement',
                         400,
                         data=ve.to_dict())
    return HTTPResponse('Updated')


@ann_router.delete('')
def delete_announcement(body: DeleteAnnouncementBody,
                        user=Depends(login_required)):
    ann = Announcement(body.ann_id)
    if not ann:
        return HTTPError('Announcement Not Found', 404)
    course = Course(ann.course)
    if not course.permission(user, Course.Permission.GRADE):
        return HTTPError('Failed to Delete Announcement', 403)
    ann.update(status=1)
    return HTTPResponse('Deleted')
