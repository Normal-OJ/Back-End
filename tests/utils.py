from mongo import *
from mongo import engine

import random
import secrets

__all__ = ['problem_result']


def task_result(
    status: int,
    task: engine.ProblemCase,
):
    exec_time = (4, task.time_limit)
    memory_limit = (4096, task.memory_limit)
    # TLE
    if status == 3:
        exec_time = (task.time_limit, task.time_limit * 2)
    # MLE
    elif status == 4:
        memory_limit = (4, task.memory_limit)
    return {
        'exitCode': -1,  # exitCode will be ignored
        'status': status,
        'stdout': secrets.token_urlsafe(),
        'stderr': secrets.token_urlsafe(),
        'execTime': random.randint(*exec_time),
        'memoryUsage': random.randint(*memory_limit),
    }


def problem_result(pid):
    '''
    make a fake problem result by given problem id
    '''
    problem = Problem(pid).obj
    if problem is None:
        raise engine.DoesNotExist(f'Unexited problem {pid}')
    ret = []
    status2code = [*Submission('aaaaaaaaaaaaaaaaaaaaaaaa').status2code.keys()]
    for task in problem.test_case.tasks:
        ret.append([])
        for case in range(task.case_count):
            # generate result
            ret[-1].append(task_result(
                random.choice(status2code),
                task,
            ))
    return ret


def drop_db(
    host: str = 'mongomock://localhost',
    db: str = 'normal-oj',
):
    conn = connect(db, host=host)
    conn.drop_database(db)
