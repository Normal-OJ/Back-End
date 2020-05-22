from flask import Blueprint, request

from mongo import *
from .auth import *
from .utils import *
from mongo import engine

__all__ = ['ranking_api']

ranking_api = Blueprint('ranking_api', __name__)


@ranking_api.route('/', methods=['GET'])
def get_ranking():
    data = list({
        "user": user.info,
        "ACProblem": len(user.AC_problem_ids),
        "ACSubmission": user.AC_submission,
        "Submission": user.submission
    } for user in engine.User.objects())

    return HTTPResponse('Success.', data=data)
