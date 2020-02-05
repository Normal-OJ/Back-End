from flask import Blueprint, request
from mongo import *
from .utils import *
from .auth import *

import mosspy

__all__ = ['copycat_api']

copycat_api = Blueprint('copycat_api', __name__)


@copycat_api.route('/', methods=['POST'])
@login_required
@Request.json('course', 'problem_id')
def detect(user, course, problem_id):
    course = Course(course).obj
    permission = perm(course, user)

    if permission < 2:
        return HTTPError('Forbidden.', 403)

    # select all ac code
    submissions = Submission.filter(user=user,
                                    offset=0,
                                    count=-1,
                                    status=0,
                                    problem=problem_id)

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
        m1.addFile(code_path)
    cc_report_url = m1.send()

    # check for python code
    m2 = mosspy.Moss(moss_userid, "python")

    for user, code_path in last_python_submission.items():
        m2.addFile(code_path)
    python_report_url = m2.send()

    # return c & cpp or python report
    return HTTPResponse('Success.',
                        data={
                            "ccReport": cc_report_url,
                            "pythonReport": python_report_url
                        })
