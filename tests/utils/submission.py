import tempfile
import warnings
import zipfile
import pytest
from datetime import date, datetime
from random import randint, choice
from typing import Any, Optional, Union
from mongo import *
from mongo.utils import drop_none

__all__ = ('create_submission', )


def create_submission(
    *,
    user: Union[User, str],
    problem: Optional[Union[Problem, int]] = None,
    lang: Optional[int] = 0,
    timestamp: Optional[float] = None,
    score: Optional[int] = None,
    status: Optional[int] = None,
    exec_time: Optional[int] = None,
    memory_usage: Optional[int] = None,
    code: Optional[str] = '',
) -> Submission:
    if isinstance(user, str):
        user = User(user)
    if isinstance(problem, int):
        problem = Problem(problem)
    if not user or not problem:
        raise ValueError('Both user and problem must be provided')
    if timestamp:
        timestamp = datetime.fromtimestamp(timestamp)
    params = {
        'problem_id': problem.id,
        'username': user.username,
        'lang': lang,
        'timestamp': timestamp,
    }
    sid = Submission.add(**params)
    submission = Submission(sid)
    if status is None:
        if score is not None:
            status = 0 if score == 100 else choice([1, 3, 4, 5])
        else:
            status = randint(-1, 7)
    if status in [(PE := -1), (CE := 2), (JE := 6)]:
        if score is not None:
            warnings.warn("score is overridden since status is PE/CE/JE")
        score, exec_time, memory_usage = 0, -1, -1
    else:
        if status == (AC := 0):
            if score is not None:
                warnings.warn("score is overridden since status is AC")
            score = 100
        if score is None:
            score = randint(0, 999)
        if exec_time is None:
            exec_time = randint(0, 999)
        if memory_usage is None:
            memory_usage = randint(0, 99999)
    ext_name = ['c', 'cpp', 'py']
    with tempfile.SpooledTemporaryFile() as tmp:
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as arc:
            arc.writestr(f'main.{ext_name[lang]}', code)
            tmp.seek(0)
        submission.submit(code_file=tmp)
    submission.update(**drop_none({
        'status': status,
        'score': score,
        'exec_time': exec_time,
        'memory_usage': memory_usage,
    }))
    submission.reload()
    return submission
