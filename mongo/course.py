from mongo import engine
from .utils import *


class Course:
    pass


def get_all_courses():
    return engine.Course.objects


def delete_course(course):
    co = get_obj(engine.Course, coure_name=course)
    if co == None:
        return "Course not found."
    co.delete()


def add_course(course, teacher):
    if get_obj(engine.Course, course_name=course) != None:
        return "Course exists."

    te = get_obj(engine.User, username=teacher)
    if te == None:
        return "User not found."

    engine.Course(**{'course_name': course, 'teacher_id': te}).save()


def edit_course(course, new_course, teacher):
    co = get_obj(engine.Course, coure_name=course)
    if co == None:
        return "Course not found."

    te = get_obj(engine.User, username=teacher)
    if te == None:
        return "User not found."

    co.course_name = new_course
    co.teacher = te
