from flask import Blueprint, request

from mongo import *
from .auth import *
from .utils import *
from mongo import engine

__all__ = ['ranking_api']

ranking_api = Blueprint('ranking_api', __name__)


@ranking_api.route('/', methods=['GET'])
def get_ranking():
    users = {}
    data = []
    for submission in engine.Submission.objects():
        username = submission.user.username
        if username not in users:
            users[username] = {
                "ACProblem": Set(), "ACSubmission": 0, "Submission": 0}

        if submission.score == 100:
            users[username]["ACProblem"].add(submission.problem_id)
            users[username]["ACSubmission"] += 1

        users[username]["Submission"] += 1

    for username, info in users.items():
        info["username"] = username
        info["ACProblem"] = len(info["ACProblem"])
        data.append(info)

    return HTTPResponse('Success.', data=data)
