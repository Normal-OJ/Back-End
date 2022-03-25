import secrets
from typing import Optional, Union, List, Dict, Any, date
from mongo import *
from . import problem as problem_lib
from . import course as course_lib
from . import user as user_lib

__all__ = ('create_submission')


def create_submission(
    *,
    user: Union[User, str],
    problem: Optional[Union[Problem, int]] = None,
    lang: Optional[int] = None,
    timestamp: Optional[date] = None,
    score: Optional[int] = None,
    status: Optional[int] = None,
    runTime: Optional[int] = None,
    memoryUsage: Optional[int] = None,
) -> Problem:
    if isinstance(user, str):
        user = User(user)
    if isinstance(problem, int):
        problem = Problem(problem)
    if user is None or problem is None:
        raise ValueError('user and problem cannot be None')
    params = {
        'problem_id': problem.id,
        'username': user.username,
        'lang': lang,
        timestamp: timestamp,
    }
    sid = Submission.add(**params)
    submission = Submission(sid)
    for k in ['score', 'status', 'runTime', 'memoryUsage']:
        if locals()[k] is not None:
            submission.update(k, locals()[k])
    submission.save()
    return submission
