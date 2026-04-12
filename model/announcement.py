from datetime import datetime
from flask import Blueprint

from mongo import *
from mongo.utils import *
from .auth import *
from .utils import *
from .schemas import CreateAnnouncementBody, UpdateAnnouncementBody, DeleteAnnouncementBody
from .course import *

__all__ = ['ann_api']

ann_api = Blueprint('ann_api', __name__)


@ann_api.route('/', methods=['GET'])
@ann_api.route('/<ann_id>', methods=['GET'])
def get_sys_ann(ann_id=None):
    public_name = Course.get_public().course_name
    anns = Announcement.ann_list(None, public_name)
    data = [{
        'annId': str(an.id),
        'title': an.title,
        'createTime': int(an.create_time.timestamp()),
        'updateTime': int(an.update_time.timestamp()),
        'creator': an.creator.info,
        'updater': an.updater.info,
        'markdown': an.markdown,
        'pinned': an.pinned
    } for an in anns if ann_id == None or str(an.id) == ann_id]
    return HTTPResponse('Sys Ann bro', data=data)


@course_api.get('/<course_name>/ann')
@ann_api.get('/<course_name>/<ann_id>')
@login_required
def get_announcements(user, course_name=None, ann_id=None):
    # Get an announcement list
    try:
        anns = Announcement.ann_list(user.obj, course_name or 'Public')
    except (DoesNotExist, ValidationError):
        return HTTPError('Cannot Access a Announcement', 403)
    if anns is None:
        return HTTPError('Announcement Not Found', 404)
    data = [{
        'annId': str(an.id),
        'title': an.title,
        'createTime': int(an.create_time.timestamp()),
        'updateTime': int(an.update_time.timestamp()),
        'creator': an.creator.info,
        'updater': an.updater.info,
        'markdown': an.markdown,
        'pinned': an.pinned
    } for an in anns if ann_id is None or str(an.id) == ann_id]
    return HTTPResponse('Announcement List', data=data)


@ann_api.post('/')
@login_required
@parse_body(CreateAnnouncementBody)
def create_announcement(user, body: CreateAnnouncementBody):
    # Create a new announcement
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
        'createTime': int(ann.create_time.timestamp())
    }
    return HTTPResponse('Announcement Created', data=data)


@ann_api.put('/')
@login_required
@parse_body(UpdateAnnouncementBody)
def update_announcement(user, body: UpdateAnnouncementBody):
    # Update an announcement
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
        return HTTPError(
            'Failed to Update Announcement',
            400,
            data=ve.to_dict(),
        )
    return HTTPResponse('Updated')


@ann_api.delete('/')
@login_required
@parse_body(DeleteAnnouncementBody)
def delete_announcement(user, body: DeleteAnnouncementBody):
    # Delete an announcement
    ann = Announcement(body.ann_id)
    if not ann:
        return HTTPError('Announcement Not Found', 404)

    course = Course(ann.course)
    if not course.permission(user, Course.Permission.GRADE):
        return HTTPError('Failed to Delete Announcement', 403)
    ann.update(status=1)
    return HTTPResponse('Deleted')
