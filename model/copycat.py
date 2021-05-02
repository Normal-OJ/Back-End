from flask import Blueprint, request, current_app
from mongo import *
from mongo.utils import *
from .utils import *
from .auth import *

import mosspy
import threading
import logging

__all__ = ['copycat_api']

copycat_api = Blueprint('copycat_api', __name__)


def get_report_task(user, problem_id):
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
    )


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

    return HTTPResponse(
        'Success.',
        data={
            "cppReport": cpp_report_url,
            "pythonReport": python_report_url
        },
    )


@copycat_api.route('/', methods=['POST'])
@login_required
@Request.json('course', 'problem_id')
def detect(user, course, problem_id):
    course = Course(course).obj
    problem = Problem(problem_id).obj
    permission = perm(course, user)

    # some privilege or exist check
    if permission < 2:
        return HTTPError('Forbidden.', 403)
    if problem is None:
        return HTTPError('Problem not exist.', 404)
    if course is None:
        return HTTPError('Course not found.', 404)

    if not current_app.config['TESTING']:
        threading.Thread(
            target=get_report_task,
            args=(
                user,
                problem_id,
            ),
        ).start()

    # return Success
    return HTTPResponse('Success.')
