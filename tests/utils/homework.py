import secrets
from typing import Optional, Union, List, Dict, Any
from mongo import *
from tests import utils

__all__ = ('add_homework', )


def add_homework(
    user: User,
    course,
    hw_name: str ,
    problem_ids: List[int],
    markdown: str,
    scoreboard_status: int,
    start: Optional[float],
    end: Optional[float],
    penalty: Optional[str],
):
    '''
    Add problem with default arguments
    '''
    if hw_name is None:
        problem_name = secrets.token_hex(16)

    return Homework.add(
        user=user,
        course_name=course,
        markdown=markdown,
        hw_name=hw_name,
        start=start,
        end=end,
        penalty=penalty,
        problem_ids=problem_ids,
        scoreboard_status=scoreboard_status,
    )
