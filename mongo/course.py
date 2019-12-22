from . import engine
from .user import *
from .utils import *
import re

__all__ = [
    'Course', 'get_all_courses', 'delete_course', 'add_course', 'edit_course',
    'perm'
]


class Course:
    def __init__(self, course_name):
        self.course_name = course_name

    @property
    def obj(self):
        try:
            obj = engine.Course.objects.get(course_name=self.course_name)
        except:
            return None
        return obj


def perm(course, user):
    '''4: admin, 3: teacher, 2: TA, 1: student, 0: not found
    '''
    return 4 - [
        user.role == 0, user == course.teacher, user in course.tas,
        user.username in course.student_nicknames.keys(), True
    ].index(True)


def get_all_courses():
    return engine.Course.objects


def delete_course(user, course):
    co = Course(course).obj
    if co is None:
        # course not found
        raise engine.DoesNotExist('course')
    if not perm(co, user):
        # user is not the TA or teacher in course
        raise PermissionError

    co.delete()
    return True


def add_course(course, teacher):
    if re.match(r'^[a-zA-Z0-9._]+$', course) is None:
        raise ValueError
    te = User(teacher).obj
    if te is None:
        raise engine.DoesNotExist('teacher')

    engine.Course(course_name=course, teacher=te).save()
    return True


def edit_course(user, course, new_course, teacher):
    if re.match(r'^[a-zA-Z0-9._]+$', new_course) is None:
        raise ValueError

    co = Course(course).obj
    if co is None:
        raise engine.DoesNotExist('course')
    if not perm(co, user):
        raise PermissionError
    te = User(teacher).obj
    if te is None:
        raise engine.DoesNotExist('teacher')

    co.course_name = new_course
    co.teacher = te
    co.save()
    return True
