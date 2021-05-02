from datetime import datetime
from flask import Blueprint, request

from mongo import *
from mongo.utils import *
from .auth import *
from .utils import *
from .course import *

__all__ = ['ann_api']

ann_api = Blueprint('ann_api', __name__)


@ann_api.route('/', methods=['GET'])
@ann_api.route('/<ann_id>', methods=['GET'])
def get_sys_ann(ann_id=None):
    anns = Announcement.ann_list(None, 'Public')
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


@ann_api.route('/', methods=['POST', 'PUT', 'DELETE'])
@course_api.route('/<course_name>/ann', methods=['GET'])
@ann_api.route('/<course_name>/<ann_id>', methods=['GET'])
@login_required
def anncmnt(user, course_name=None, ann_id=None):
    def get_anns():
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
        } for an in anns if ann_id == None or str(an.id) == ann_id]
        return HTTPResponse('Announcement List', data=data)

    @Request.json('title', 'markdown', 'course_name', 'pinned')
    def create(title, markdown, course_name, pinned):
        # Create a new announcement
        try:
            ann = Announcement.new_ann(
                course_name or 'Public',
                title,
                user.obj,
                markdown,
                pinned,
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

    @Request.json('ann_id', 'title', 'markdown', 'pinned')
    def update(ann_id, title, markdown, pinned):
        # Update an announcement
        ann = Announcement(ann_id)
        if not ann:
            return HTTPError('Announcement Not Found', 404)
        course = ann.course
        if perm(course, user) < 2:
            return HTTPError('Failed to Update Announcement', 403)
        try:
            ann.update(
                title=title,
                markdown=markdown,
                update_time=datetime.now(),
                updater=user.obj,
                pinned=pinned,
            )
        except ValidationError as ve:
            return HTTPError(
                'Failed to Update Announcement',
                400,
                data=ve.to_dict(),
            )
        return HTTPResponse('Updated')

    @Request.json('ann_id')
    def delete(ann_id):
        # Delete an announcement
        ann = Announcement(ann_id)
        if not ann:
            return HTTPError('Announcement Not Found', 404)
        course = ann.course
        if perm(course, user) < 2:
            return HTTPError('Failed to Delete Announcement', 403)
        ann.update(status=1)
        return HTTPResponse('Deleted')

    methods = {
        'GET': get_anns,
        'POST': create,
        'PUT': update,
        'DELETE': delete
    }

    return methods[request.method]()
