from flask import Blueprint, request, current_app
from mongo import *
from .utils import *
from .auth import *

import mosspy
import threading
import logging
import requests

__all__ = ['copycat_api']

copycat_api = Blueprint('copycat_api', __name__)


def get_report_task(user, problem_id, student_dict):
    # select all ac code
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
        if s.user.username in list(student_dict.keys()):
            if s.language in [0, 1] and s.user.username not in last_cc_submission:
                last_cc_submission[submission.user.username] = s.main_code_path
            elif s.language in [2] \
                and s.user.username not in last_python_submission:
                last_python_submission[submission.user.username] = s.main_code_path

    moss_userid = 97089070

    # check for c or cpp code
    m1 = mosspy.Moss(moss_userid, "cc")

    for user, code_path in last_cc_submission.items():
        logging.info(f'send {user} {code_path}')
        m1.addFile(code_path)
    cpp_report_url = m1.send()

    # check for python code
    m2 = mosspy.Moss(moss_userid, "python")

    for user, code_path in last_python_submission.items():
        logging.info(f'send {user} {code_path}')
        m2.addFile(code_path)
    python_report_url = m2.send()

    # insert report url into DB
    problem = Problem(problem_id)
    problem.obj.update(
        cpp_report_url=cpp_report_url,
        python_report_url=python_report_url,
        moss_status=2,
    )


def get_report_by_url(url: str):
    try:
        response = requests.get(url)
        return response.text
    except (requests.exceptions.MissingSchema,
            requests.exceptions.InvalidSchema):
        return 'No report.'


@copycat_api.route('/', methods=['GET'])
@login_required
@Request.args('course', 'problem_id')
def get_report(user, course, problem_id):
    if not (problem_id and course):
        return HTTPError(
            'missing arguments!',
            400,
            data={
                'need': ['course', 'problemId'],
            },
        )
    # some privilege or exist check
    try:
        problem = Problem(int(problem_id)).obj
    except ValueError:
        return HTTPError('problemId must be integer', 400)
    course = Course(course).obj
    permission = perm(course, user)

    if permission < 2:
        return HTTPError('Forbidden.', 403)
    if problem is None:
        return HTTPError('Problem not exist.', 404)
    if course is None:
        return HTTPError('Course not found.', 404)

    cpp_report_url = problem.cpp_report_url
    python_report_url = problem.python_report_url

    if problem.moss_status == 0:
        return HTTPResponse("No report found. Please make a post request to copycat api to generate a report", data={})
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


@copycat_api.route('/', methods=['POST'])
@login_required
@Request.json('course', 'problem_id', 'student_nicknames')
def detect(user, course, problem_id, student_nicknames):
    if not (problem_id and course and student_nicknames):
        return HTTPError(
            'missing arguments!',
            400,
            data={
                'need': ['course', 'problemId', 'studentNicknames'],
            },
        )

    course = Course(course).obj
    problem = Problem(problem_id).obj
    permission = perm(course, user)

    # Check if student is in course
    student_dict = {}
    for student, nickname in student_nicknames.items():
        if not User(student):
            return HTTPResponse(f'User: {student} not found.', 404)
        student_dict[student] = nickname
    # Check student_dict
    if not student_dict:
        return HTTPResponse('Empty student list.', 404)
    # some privilege or exist check
    if permission < 2:
        return HTTPError('Forbidden.', 403)
    if problem is None:
        return HTTPError('Problem not exist.', 404)
    if course is None:
        return HTTPError('Course not found.', 404)

    if not current_app.config['TESTING']:
        problem = Problem(problem_id)
        problem.obj.update(
            cpp_report_url="",
            python_report_url="",
            moss_status=1
        )
        threading.Thread(
            target=get_report_task,
            args=(
                user,
                problem_id,
                student_dict,
            ),
        ).start()

    # return Success
    return HTTPResponse('Success.')
