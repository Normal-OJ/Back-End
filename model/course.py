from typing import Optional
from fastapi import APIRouter, Depends
from datetime import datetime

from mongo import *
from .auth import identity_verify, login_required
from .utils import *
from .schemas import (
    ModifyCoursesBody,
    UpdateCourseBody,
    AddGradeBody,
    UpdateGradeBody,
    DeleteGradeBody,
    GetCourseScoreboardQuery,
)
from mongo.utils import *
from mongo.course import *
from mongo import engine

__all__ = ['course_router']

course_router = APIRouter()


@course_router.get('')
def get_courses(user=Depends(login_required)):
    data = [{
        'course': c.course_name,
        'teacher': c.teacher.info,
    } for c in Course.get_user_courses(user)]
    return HTTPResponse('Success.', data=data)


@course_router.get('/summary')
def get_courses_summary(user: User = identity_verify(0)):
    courses = [Course(c) for c in Course.get_all()]
    summary = {"courseCount": len(courses), "breakdown": []}
    for course in courses:
        problems = Problem.get_problem_list(user, course=course.course_name)
        course_summary = course.get_course_summary(problems)
        course_summary["problemCount"] = len(problems)
        summary["breakdown"].append(course_summary)
    return HTTPResponse("Success.", data=summary)


@course_router.post('')
def create_course(body: ModifyCoursesBody, user: User = identity_verify(0, 1)):
    teacher = body.teacher
    if user.role == 1:
        teacher = user.username
    try:
        Course.add_course(body.course, teacher)
    except ValueError:
        return HTTPError('Not allowed name.', 400)
    except NotUniqueError:
        return HTTPError('Course exists.', 400)
    except PermissionError:
        return HTTPError('Forbidden.', 403)
    except engine.DoesNotExist as e:
        return HTTPError(f'{e} not found.', 404)
    return HTTPResponse('Success.')


@course_router.put('')
def update_course_meta(body: ModifyCoursesBody,
                       user: User = identity_verify(0, 1)):
    teacher = body.teacher
    if user.role == 1:
        teacher = user.username
    try:
        co = Course(body.course)
        co.edit_course(user, body.new_course, teacher)
    except ValueError:
        return HTTPError('Not allowed name.', 400)
    except NotUniqueError:
        return HTTPError('Course exists.', 400)
    except PermissionError:
        return HTTPError('Forbidden.', 403)
    except engine.DoesNotExist as e:
        return HTTPError(f'{e} not found.', 404)
    return HTTPResponse('Success.')


@course_router.delete('')
def delete_course(body: ModifyCoursesBody, user: User = identity_verify(0, 1)):
    try:
        co = Course(body.course)
        co.delete_course(user)
    except ValueError:
        return HTTPError('Not allowed name.', 400)
    except PermissionError:
        return HTTPError('Forbidden.', 403)
    except engine.DoesNotExist as e:
        return HTTPError(f'{e} not found.', 404)
    return HTTPResponse('Success.')


@course_router.get('/{course_name}')
def get_course(course_name: str, user=Depends(login_required)):
    course = Course(course_name)
    if not course:
        return HTTPError('Course not found.', 404)
    if not course.permission(user, Course.Permission.VIEW):
        return HTTPError('You are not in this course.', 403)
    return HTTPResponse(
        'Success.',
        data={
            "teacher": course.teacher.info,
            "TAs": [ta.info for ta in course.tas],
            "students": [User(name).info for name in course.student_nicknames],
        },
    )


@course_router.put('/{course_name}')
def update_course(course_name: str,
                  body: UpdateCourseBody,
                  user=Depends(login_required)):
    TAs = body.TAs
    student_nicknames = body.student_nicknames
    course = Course(course_name)

    if not course:
        return HTTPError('Course not found.', 404)
    if not course.permission(user, Course.Permission.VIEW):
        return HTTPError('You are not in this course.', 403)
    if not course.permission(user, Course.Permission.MODIFY):
        return HTTPError('Forbidden.', 403)

    tas = []
    for ta in TAs:
        permit_user = User(ta).obj
        if not User(ta):
            return HTTPResponse(f'User: {ta} not found.', 404)
        tas.append(permit_user)

    for permit_user in set(course.tas) - set(tas):
        course.remove_user(permit_user)
    for permit_user in set(tas) - set(course.tas):
        course.add_user(permit_user)
    course.tas = tas

    try:
        course.update_student_namelist(student_nicknames)
    except engine.DoesNotExist as e:
        return HTTPError(str(e), 404)
    return HTTPResponse('Success.')


@course_router.get('/{course_name}/grade/{student}')
def get_grade(course_name: str, student: str, user=Depends(login_required)):
    course = Course(course_name)
    if not course:
        return HTTPError('Course not found.', 404)
    if not course.permission(user, Course.Permission.VIEW):
        return HTTPError('You are not in this course.', 403)
    if student not in course.student_nicknames.keys():
        return HTTPError('The student is not in the course.', 404)
    if course.permission(user,
                         Course.Permission.SCORE) and user.username != student:
        return HTTPError('You can only view your score.', 403)
    return HTTPResponse(
        'Success.',
        data=[{
            'title': score['title'],
            'content': score['content'],
            'score': score['score'],
            'timestamp': score['timestamp'].timestamp(),
        } for score in course.student_scores.get(student, [])],
    )


@course_router.post('/{course_name}/grade/{student}')
def add_grade(
        course_name: str,
        student: str,
        body: AddGradeBody,
        user=Depends(login_required),
):
    course = Course(course_name)
    if not course:
        return HTTPError('Course not found.', 404)
    if not course.permission(user, Course.Permission.VIEW):
        return HTTPError('You are not in this course.', 403)
    if student not in course.student_nicknames.keys():
        return HTTPError('The student is not in the course.', 404)
    if course.permission(user, Course.Permission.SCORE):
        return HTTPError('You can only view your score.', 403)

    score_list = course.student_scores.get(student, [])
    if body.title in [s['title'] for s in score_list]:
        return HTTPError('This title is taken.', 400)
    score_list.append({
        'title': body.title,
        'content': body.content,
        'score': body.score,
        'timestamp': datetime.now(),
    })
    course.student_scores[student] = score_list
    course.save()
    return HTTPResponse('Success.')


@course_router.put('/{course_name}/grade/{student}')
def update_grade(
        course_name: str,
        student: str,
        body: UpdateGradeBody,
        user=Depends(login_required),
):
    course = Course(course_name)
    if not course:
        return HTTPError('Course not found.', 404)
    if not course.permission(user, Course.Permission.VIEW):
        return HTTPError('You are not in this course.', 403)
    if student not in course.student_nicknames.keys():
        return HTTPError('The student is not in the course.', 404)
    if course.permission(user, Course.Permission.SCORE):
        return HTTPError('You can only view your score.', 403)

    score_list = course.student_scores.get(student, [])
    title_list = [s['title'] for s in score_list]
    if body.title not in title_list:
        return HTTPError('Score not found.', 404)
    index = title_list.index(body.title)
    title = body.new_title if body.new_title is not None else body.title
    if body.new_title is not None and body.new_title in title_list:
        return HTTPError('This title is taken.', 400)
    score_list[index] = {
        'title': title,
        'content': body.content,
        'score': body.score,
        'timestamp': datetime.now(),
    }
    course.student_scores[student] = score_list
    course.save()
    return HTTPResponse('Success.')


@course_router.delete('/{course_name}/grade/{student}')
def delete_grade(
        course_name: str,
        student: str,
        body: DeleteGradeBody,
        user=Depends(login_required),
):
    course = Course(course_name)
    if not course:
        return HTTPError('Course not found.', 404)
    if not course.permission(user, Course.Permission.VIEW):
        return HTTPError('You are not in this course.', 403)
    if student not in course.student_nicknames.keys():
        return HTTPError('The student is not in the course.', 404)
    if course.permission(user, Course.Permission.SCORE):
        return HTTPError('You can only view your score.', 403)

    score_list = course.student_scores.get(student, [])
    title_list = [s['title'] for s in score_list]
    if body.title not in title_list:
        return HTTPError('Score not found.', 404)
    index = title_list.index(body.title)
    del score_list[index]
    course.student_scores[student] = score_list
    course.save()
    return HTTPResponse('Success.')


@course_router.get('/{course_name}/scoreboard')
def get_course_scoreboard(
        course_name: str,
        query: GetCourseScoreboardQuery = Depends(),
        user=Depends(login_required),
        course: Course = get_doc('course_name', Course),
):
    pids = query.pids
    start = query.start
    end = query.end
    try:
        pids = pids.split(',')
        pids = [int(pid.strip()) for pid in pids]
    except Exception:
        return HTTPError('Error occurred when parsing `pids`.', 400)

    if start:
        try:
            start = float(start)
        except Exception:
            return HTTPError('Type of `start` should be float.', 400)
    if end:
        try:
            end = float(end)
        except Exception:
            return HTTPError('Type of `end` should be float.', 400)

    if not course.permission(user, Course.Permission.GRADE):
        return HTTPError('Permission denied', 403)

    ret = course.get_scoreboard(pids, start, end)
    return HTTPResponse('Success.', data=ret)
