from datetime import datetime
from flask import Blueprint, request

from mongo import *
from .auth import *
from .utils import *

__all__ = ['annn_api']

annn_api = Blueprint('annn_api', __name__)


@annn_api.route('/', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def annncmnt(user):
    @Request.json('course_name')
    def get_annns(course_name):
        # Get an announcement list
        try:
            annns = Announcement.annn_list(user.obj, course_name or 'Public')
        except (DoesNotExist, ValidationError):
            return HTTPError('Cannot Access a Announcement', 403)
        if annns is None:
            return HTTPError('Announcement Not Found', 404)
        data = [{
            'annnId': str(an.id),
            'title': an.title,
            'createTime': int(an.create_time.timestamp()),
            'updateTime': int(an.update_time.timestamp()),
            'creater': an.creater.username,
            'updater': an.updater.username,
            'markdown': an.markdown
        } for an in annns]
        return HTTPResponse('Announcement List', data=data)

    @Request.json('title', 'markdown', 'course_name')
    def create(title, markdown, course_name):
        # Create a new announcement
        try:
            annn = Announcement.new_annn(course_name or 'Public', title,
                                         user.obj, markdown)
        except ValidationError as ve:
            return HTTPError('Failed to Create Announcement',
                             400,
                             data=ve.to_dict())
        if annn is None:
            return HTTPError('Failed to Create Announcement', 403)
        data = {
            'annnId': str(annn.id),
            'createTime': int(annn.create_time.timestamp())
        }
        return HTTPResponse('Announcement Created', data=data)

    @Request.json('annn_id', 'title', 'markdown')
    def update(annn_id, title, markdown):
        # Update an announcement
        annn = Announcement(annn_id)
        if not annn:
            return HTTPError('Announcement Not Found', 404)
        course = annn.course
        if user.role != 0 and user != course.teacher and user not in course.tas:
            return HTTPError('Failed to Update Announcement', 403)
        try:
            annn.update(title=title,
                        markdown=markdown,
                        update_time=datetime.utcnow(),
                        updater=user.obj)
        except ValidationError as ve:
            return HTTPError('Failed to Update Announcement',
                             400,
                             data=ve.to_dict())
        return HTTPResponse('Updated')

    @Request.json('annn_id')
    def delete(annn_id):
        # Delete an announcement
        annn = Announcement(annn_id)
        if not annn:
            return HTTPError('Announcement Not Found', 404)
        course = annn.course
        if user.role != 0 and user != course.teacher and user.obj not in course.tas:
            return HTTPError('Failed to Delete Announcement', 403)
        annn.update(status=1)
        return HTTPResponse('Deleted')

    methods = {
        'GET': get_annns,
        'POST': create,
        'PUT': update,
        'DELETE': delete
    }

    return methods[request.method]()
