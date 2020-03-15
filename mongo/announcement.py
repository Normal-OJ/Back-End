from . import engine
from .user import *
from .course import *
from .base import *

__all__ = ['Announcement']


class Announcement(MongoBase, engine=engine.Announcement):
    qs_filter = {'status': 0}

    def __init__(self, ann_id):
        self.ann_id = ann_id

    @staticmethod
    def ann_list(user, course_name):
        if course_name == 'Public':
            return engine.Announcement.objects(
                course=Course('Public').obj, status=0).order_by('-createTime')
        course = Course(course_name).obj
        if course is None:
            return None
        if not perm(course, user):
            return None
        anns = engine.Announcement.objects(course=course,
                                           status=0).order_by('-createTime')
        return anns

    @staticmethod
    def new_ann(
        course_name,
        title,
        creator,
        markdown,
        pinned,
    ):
        course = Course(course_name).obj
        if course is None:
            return None
        if perm(course, creator) < 2:
            return None
        ann = engine.Announcement(
            title=title,
            course=course,
            creator=creator,
            updater=creator,
            markdown=markdown,
            pinned=pinned,
        )
        ann.save()
        return ann
