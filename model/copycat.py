import os
import re
import logging
import threading
from typing import Dict
import httpx
import mosspy
from fastapi import APIRouter, Depends

from mongo import *
from mongo.utils import *
from .utils import *
from .auth import login_required
from .schemas import GetReportQuery, DetectBody

__all__ = ['copycat_router']

copycat_router = APIRouter()


def is_valid_url(url):
    regex = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$',
        re.IGNORECASE,
    )
    return url is not None and regex.search(url)


def get_report_task(user, problem_id, student_dict: Dict):
    submissions = Submission.filter(
        user=user,
        offset=0,
        count=-1,
        status=0,
        problem=problem_id,
    )

    last_cc_submission = {}
    last_python_submission = {}
    for submission in submissions:
        s = Submission(submission.id)
        if s.user.username in student_dict:
            if s.language in [0, 1
                              ] and s.user.username not in last_cc_submission:
                last_cc_submission[
                    submission.user.username] = s.main_code_path()
            elif s.language in [
                    2
            ] and s.user.username not in last_python_submission:
                last_python_submission[
                    submission.user.username] = s.main_code_path()

    moss_userid = 97089070
    logger = logging.getLogger(__name__)
    problem = Problem(problem_id)

    cpp_report_url = ''
    python_report_url = ''
    if problem.allowed_language != 4:
        m1 = mosspy.Moss(moss_userid, "cc")
        for user, code_path in last_cc_submission.items():
            logger.info(f'send {user} {code_path}')
            m1.addFile(code_path)
        response = m1.send()
        if is_valid_url(response):
            cpp_report_url = response
        else:
            logger.info(f"[copycat] {response}")
            cpp_report_url = ''

    if problem.allowed_language >= 4:
        m2 = mosspy.Moss(moss_userid, "python")
        for user, code_path in last_python_submission.items():
            logger.info(f'send {user} {code_path}')
            m2.addFile(code_path)
        response = m2.send()
        if is_valid_url(response):
            python_report_url = response
        else:
            logger.info(f"[copycat] {response}")
            python_report_url = ''

    if cpp_report_url != '':
        mosspy.download_report(
            cpp_report_url,
            f"submissions_report/{problem_id}/cpp_report/",
            connections=8,
            log_level=10,
        )
    if python_report_url != '':
        mosspy.download_report(
            python_report_url,
            f"submissions_report/{problem_id}/python_report/",
            connections=8,
            log_level=10,
        )

    problem.obj.update(
        cpp_report_url=cpp_report_url,
        python_report_url=python_report_url,
        moss_status=2,
    )


def get_report_by_url(url: str):
    try:
        response = httpx.get(url)
        return response.text
    except httpx.InvalidURL:
        return 'No report.'


@copycat_router.get('')
def get_report(query: GetReportQuery = Depends(),
               user=Depends(login_required)):
    course = query.course
    problem_id = query.problem_id
    if not (problem_id and course):
        return HTTPError(
            'missing arguments! (In HTTP GET argument format)',
            400,
            data={'need': ['course', 'problemId']},
        )
    try:
        problem = Problem(int(problem_id))
    except ValueError:
        return HTTPError('problemId must be integer', 400)

    course = Course(course)
    if not course.permission(user, Course.Permission.GRADE):
        return HTTPError('Forbidden.', 403)
    if not problem:
        return HTTPError('Problem not exist.', 404)
    if not course:
        return HTTPError('Course not found.', 404)

    cpp_report_url = problem.cpp_report_url
    python_report_url = problem.python_report_url

    if problem.moss_status == 0:
        return HTTPError(
            "No report found. Please make a post request to copycat api to generate a report",
            404,
            data={},
        )
    elif problem.moss_status == 1:
        return HTTPResponse("Report generating...", data={})
    else:
        cpp_report = get_report_by_url(cpp_report_url)
        python_report = get_report_by_url(python_report_url)
        return HTTPResponse(
            "Success.",
            data={
                "cpp_report": cpp_report,
                "python_report": python_report
            },
        )


@copycat_router.post('')
def detect(body: DetectBody, user=Depends(login_required)):
    course = body.course
    problem_id = body.problem_id
    student_nicknames = body.student_nicknames
    if not (problem_id and course and type(student_nicknames) is dict):
        return HTTPError(
            'missing arguments! (In Json format)',
            400,
            data={'need': ['course', 'problemId', 'studentNicknames']},
        )

    course = Course(course)
    problem = Problem(problem_id)

    student_dict = {}
    for student, nickname in student_nicknames.items():
        if not User(student):
            return HTTPResponse(f'User: {student} not found.', 404)
        student_dict[student] = nickname
    if not student_dict:
        return HTTPResponse('Empty student list.', 404)
    if not course.permission(user, Course.Permission.GRADE):
        return HTTPError('Forbidden.', 403)
    if not problem:
        return HTTPError('Problem not exist.', 404)
    if not course:
        return HTTPError('Course not found.', 404)

    problem = Problem(problem_id)
    problem.update(cpp_report_url="", python_report_url="", moss_status=1)
    if not is_testing():
        threading.Thread(
            target=get_report_task,
            args=(user, problem_id, student_dict),
        ).start()

    return HTTPResponse('Success.')
