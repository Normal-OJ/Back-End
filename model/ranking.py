from fastapi import APIRouter

from mongo import *
from .utils import *
from mongo import engine

__all__ = ['ranking_router']

ranking_router = APIRouter()


@ranking_router.get('')
def get_ranking():
    data = list({
        "user": user.info,
        "ACProblem": len(user.AC_problem_ids),
        "ACSubmission": user.AC_submission,
        "Submission": user.submission
    } for user in engine.User.objects())

    return HTTPResponse('Success.', data=data)
