from . import engine
from .user import *
from .course import *
from .base import *

__all__ = ['Announcement']


class Announcement(MongoBase, engine=engine.Announcement):
    qs_filter = {'status': 0}

    def __init__(self, annn_id):
        self.annn_id = annn_id

    # def __getattr__(self, name):
    #     try:
    #         obj = engine.Announcement.objects.get(id=self.annn_id, status=0)
    #     except (engine.DoesNotExist, engine.ValidationError):
    #         return None
    #     return obj.__getattribute__(name)

    @staticmethod
    def annn_list(user, course_name):
        course = Course(course_name).obj
        if course is None:
            return None
        if user.role != 0 and user != course.teacher and user not in course.tas and course not in user.courses:
            return None
        annns = engine.Announcement.objects(course=course,
                                            status=0).order_by('-createTime')
        return annns

    @staticmethod
    def new_annn(course_name, title, creater, markdown):
        course = Course(course_name).obj
        if course is None:
            return None
        if creater.role != 0 and creater != course.teacher and creater not in course.tas:
            return None
        annn = engine.Announcement(title=title,
                                   course=course,
                                   creater=creater,
                                   updater=creater,
                                   markdown=markdown)
        annn.save()
        return annn
