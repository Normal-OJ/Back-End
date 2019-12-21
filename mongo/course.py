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
        return "Course not found."

    if not perm(co, user):
        return "Forbidden."

    co.delete()


def add_course(course, teacher):
    if re.match('^\w+$', course) is None:
        return 'Not allowed name.'

    te = User(teacher).obj
    if te is None:
        return "User not found."

    engine.Course(course_name=course, teacher=te).save()


def edit_course(user, course, new_course, teacher):
    if re.match('^\w+$', new_course) is None:
        return 'Not allowed name.'

    co = Course(course).obj
    if co is None:
        return "Course not found."

    if not perm(co, user):
        return "Forbidden."

    te = User(teacher).obj
    if te is None:
        return "User not found."

    co.course_name = new_course
    co.teacher = te
    co.save()
