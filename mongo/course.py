from . import engine
from .user import *
from .utils import *
import re
from typing import Optional
from .base import MongoBase

__all__ = [
    'Course',
]


class Course(MongoBase, engine=engine.Course):
    def __new__(cls, course_name, *args, **kwargs):
        try:
            new = super().__new__(cls, course_name)
        except engine.ValidationError:
            try:
                pk = Course.engine.objects(course_name=course_name).get()
                new = super().__new__(cls, pk)
            except engine.DoesNotExist:
                new = super().__new__(cls, '0' * 24)
        return new

    def add_user(self, user):
        obj = self.obj
        if obj is None:
            raise engine.DoesNotExist(f'Course [{self.course_name}]')
        if obj not in user.courses:
            user.courses.append(obj)
            user.save()

    def remove_user(self, user):
        user.courses.remove(self.obj)
        user.save()

    @classmethod
    def get_all(cls):
        return engine.Course.objects

    @classmethod
    def get_user_courses(cls, user):
        if user.role != 0:
            return user.courses
        else:
            return cls.get_all()

    def edit_course(self, user, new_course, teacher):
        if re.match(r'^[a-zA-Z0-9._\- ]+$', new_course) is None:
            raise ValueError

        if not self:
            raise engine.DoesNotExist('Course')
        if not perm(self, user):
            raise PermissionError
        te = User(teacher)
        if not te:
            raise engine.DoesNotExist('User')

        self.course_name = new_course
        if te.obj != self.teacher:
            self.remove_user(self.teacher)
            self.add_user(te.obj)
        self.teacher = te.obj
        self.save()
        return True

    def delete_course(self, user):
        if not self:
            # course not found
            raise engine.DoesNotExist('Course')
        if not perm(self, user):
            # user is not the TA or teacher in course
            raise PermissionError

        self.remove_user(self.teacher)
        self.delete()
        return True

    @classmethod
    def add_course(cls, course, teacher):
        if re.match(r'^[a-zA-Z0-9._\- ]+$', course) is None:
            raise ValueError
        teacher = User(teacher)
        if not teacher:
            raise engine.DoesNotExist('User')
        if teacher.role >= 2:
            raise PermissionError(
                f'{teacher} is not permitted to create a course')
        co = cls.engine(
            course_name=course,
            teacher=teacher.obj,
        ).save()
        cls(co).add_user(teacher.obj)
        return True