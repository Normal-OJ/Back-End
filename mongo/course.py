from . import engine
from .user import *
from .utils import *

__all__ = [
    'Course', 'get_all_courses', 'delete_course', 'add_course', 'edit_course'
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


def get_all_courses():
    return engine.Course.objects


def delete_course(course):
    co = Course(course).obj
    if co is None:
        return "Course not found."
    co.delete()


def add_course(course, teacher):
    te = User(teacher).obj
    if te is None:
        return "User not found."

    engine.Course(**{'course_name': course, 'teacher': te}).save()


def edit_course(course, new_course, teacher):
    co = Course(course).obj
    if co is None:
        return "Course not found."

    te = User(teacher).obj
    if te is None:
        return "User not found."

    co.course_name = new_course
    co.teacher = te
    co.save()
