from . import engine
from .user import *
from .course import *
from .base import *
from .utils import *

__all__ = ['Announcement']


class Announcement(MongoBase, engine=engine.Announcement):
    qs_filter = {'status': 0}

    def __init__(self, ann_id):
        self.ann_id = ann_id

    @classmethod
    def ann_list(cls, user, course_name):
        if course_name == 'Public':
            return engine.Announcement.objects(
                course=Course('Public'), status=0).order_by('-createTime')
        course = Course(course_name)
        if not course:
            return None
        if not perm(course, user):
            return None
        anns = engine.Announcement.objects(course=course.obj,
                                           status=0).order_by('-createTime')
        return anns

    @classmethod
    @doc_required('course', 'course', Course)
    def new_ann(
        cls,
        title,
        creator,
        markdown,
        pinned,
        course: Course,
    ):
        if perm(course, creator) < 2:
            return None
        ann = engine.Announcement(
            title=title,
            course=course.obj,
            creator=creator,
            updater=creator,
            markdown=markdown,
            pinned=pinned,
        )
        ann.save()
        return ann
