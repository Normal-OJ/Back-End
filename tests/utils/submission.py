from datetime import date
from typing import Optional, Union
from mongo import *

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
    if not user or not problem:
        raise ValueError('Both user and problem must be provided')
    params = {
        'problem_id': problem.id,
        'username': user.username,
        'lang': lang,
        'timestamp': timestamp,
    }
    sid = Submission.add(**params)
    submission = Submission(sid)
    for k in ['score', 'status', 'runTime', 'memoryUsage']:
        if locals()[k] is not None:
            submission.update(k, locals()[k])
    if status == 0:
        # AC submission should be scored 100
        submission.update('score', 100)
        submission.update('runTime', max(0, runTime or -1))
        submission.update('memoryUsage', max(0, memoryUsage or -1))
    elif status in [-1, 2, 6]:
        # PE, CE, JE
        submission.update('score', 0)
        submission.update('runTime', -1)
        submission.update('memoryUsage', -1)
    else:
        submission.update('score', min(99, score or -1))
        submission.update('runTime', max(0, runTime or -1))
        submission.update('memoryUsage', max(0, memoryUsage or -1))
    submission.save()
    return submission
