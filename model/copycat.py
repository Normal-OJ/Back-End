from flask import Blueprint, request
from mongo import *


__all__ = ['copycat_api']

copycat_api = Blueprint('copycat_api', __name__)

@course_api.route('/', methods=['POST'])
@login_required
@Request.json('course', 'problem_id')
def detect(user, course):
    permission = perm(course, user)

    if permission < 2:
        return HTTPError('Forbidden.', 403)

    submissions = Submission.filter(user=user, offset=0, count=-1, status=0, problem=problem_id)
    
    last_submission = {}
    for submission in submissions:
        if submission.user.username not in last_submission:
            last_submission[submission.user.username] = Submission(submission.id).get_code()
    
    for user, code in last_submission.items():
        

