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

    def edit_course(self, user, course, new_course, teacher):
        if re.match(r'^[a-zA-Z0-9._\- ]+$', new_course) is None:
            raise ValueError

        co = Course(course)
        if not co:
            raise engine.DoesNotExist('Course')
        if not perm(co, user):
            raise PermissionError
        te = User(teacher)
        if not te:
            raise engine.DoesNotExist('User')

        co.course_name = new_course
        if te.obj != co.teacher:
            co.remove_user(co.teacher)
            co.add_user(te.obj)
        co.teacher = te.obj
        co.save()
        return True

    def delete_course(self, user, course):
        co = Course(course)
        if not co:
            # course not found
            raise engine.DoesNotExist('Course')
        if not perm(co, user):
            # user is not the TA or teacher in course
            raise PermissionError

        co.remove_user(co.teacher)
        co.delete()
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