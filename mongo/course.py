from . import engine
from .user import *
from .utils import *
import re

__all__ = [
    'Course', 'get_all_courses', 'delete_course', 'add_course', 'edit_course',
    'perm', 'add_user', 'remove_user', 'get_user_courses'
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


def get_user_courses(user):
    return user.courses if user.role != 0 else get_all_courses()


def add_user(user, course):
    if course not in user.courses:
        user.courses.append(course)
        user.save()


def remove_user(user, course):
    user.courses.remove(course)
    user.save()


def delete_course(user, course):
    co = Course(course).obj
    if co is None:
        # course not found
        raise engine.DoesNotExist('Course')
    if not perm(co, user):
        # user is not the TA or teacher in course
        raise PermissionError

    remove_user(co.teacher, co)
    co.delete()
    return True


def add_course(course, teacher):
    if re.match(r'^[a-zA-Z0-9._\- ]+$', course) is None:
        raise ValueError
    te = User(teacher)
    if not te:
        raise engine.DoesNotExist('User')

    co = engine.Course(course_name=course, teacher=te.obj)
    co.save()
    add_user(te.obj, co)
    return True


def edit_course(user, course, new_course, teacher):
    if re.match(r'^[a-zA-Z0-9._\- ]+$', new_course) is None:
        raise ValueError

    co = Course(course).obj
    if co is None:
        raise engine.DoesNotExist('Course')
    if not perm(co, user):
        raise PermissionError
    te = User(teacher)
    if not te:
        raise engine.DoesNotExist('User')

    co.course_name = new_course
    if te.obj != co.teacher:
        remove_user(co.teacher, co)
        add_user(te.obj, co)
    co.teacher = te.obj
    co.save()
    return True
