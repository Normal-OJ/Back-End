import json
import os
import io
import pathlib
import secrets
import logging
import requests as rq
from flask import current_app
from datetime import date
from typing import List
from zipfile import ZipFile, is_zipfile
from model.submission_config import SubmissionConfig

from . import engine
from .base import MongoBase
from .user import User
from .problem import Problem, can_view

__all__ = [
    'Submission',
    'get_token',
    'assign_token',
    'verify_token',
    'JudgeQueueFullError',
    'SourceNotFoundError',
    'NoSourceError',
]

# pid, hash()
p_hash = {}

# TODO: save tokens in db
tokens = {}


def get_token():
    return secrets.token_urlsafe()


def assign_token(submission_id, token_pool=tokens):
    '''
    generate a token for the submission
    '''
    token = get_token()
    token_pool[submission_id] = token
    return token


def verify_token(submission_id, token):
    if submission_id not in tokens:
        return False
    return secrets.compare_digest(tokens[submission_id], token)


# Errors
class JudgeQueueFullError(Exception):
    '''
    when sandbox task queue is full
    '''


class SourceNotFoundError(Exception):
    '''
    when source code not found but it shoud be
    '''


class NoSourceError(Exception):
    '''
    when source code haven't been uploaded but try to access them
    '''


class Submission(MongoBase, engine=engine.Submission):
    def __init__(self, submission_id):
        self.submission_id = str(submission_id)

    def __str__(self):
        return f'submission [{self.submission_id}]'

    @property
    def id(self):
        '''
        convert mongo ObjectId to hex string for serialize
        '''
        return str(self.obj.id)

    @property
    def problem_id(self):
        return self.problem.problem_id

    def to_dict(self):
        _ret = {
            'problemId': self.problem.problem_id,
            'user': User(self.user.username).info,
            'submissionId': self.id,
            'timestamp': self.timestamp.timestamp()
        }
        ret = json.loads(self.obj.to_json())

        old = [
            '_id',
            'problem',
        ]
        for o in old:
            del ret[o]

        for n in _ret.keys():
            ret[n] = _ret[n]

        return ret

    @property
    def code_dir(self) -> pathlib.Path:
        return SubmissionConfig.SOURCE_PATH / self.id

    @property
    def tmp_dir(self) -> pathlib.Path:
        return SubmissionConfig.TMP_DIR / self.id

    @property
    def main_code_path(self) -> str:
        lang2ext = {0: '.c', 1: '.cpp', 2: '.py'}
        if self.language not in lang2ext:
            raise ValueError
        return str(
            (self.code_dir / f'main{lang2ext[self.language]}').absolute())

    def get_code(self, path: str) -> str:
        path = self.code_dir / path

        if not path.exists():
            raise FileNotFoundError(path)

        return path.read_text()

    def make_source_zip(self):
        '''
        zip source file
        '''
        # check source code
        if not self.code:
            raise NoSourceError
        if not self.code_dir.exists():
            raise SourceNotFoundError
        # if source zip has been created, directly return
        zip_path = self.tmp_dir / 'source.zip'
        if zip_path.exists():
            return zip_path
        zip_path.parent.mkdir(exist_ok=True)
        with ZipFile(zip_path, 'w') as f:
            for code in self.code_dir.iterdir():
                f.write(code, arcname=code.name)
        return zip_path

    def rejudge(self) -> bool:
        '''
        rejudge this submission
        '''
        zip_path = self.make_source_zip()
        self.update(status=-1)
        if current_app.config['TESTING']:
            return False
        return self.send(zip_path)

    def submit(self, code_file, rejudge=False) -> bool:
        '''
        prepara data for submit code to sandbox and then send it

        Args:
            code_file: a zip file contains user's code
        '''
        # unexisted id
        if not self:
            raise engine.DoesNotExist(f'{self}')
        # init submission data

        if self.code_dir.is_dir():
            raise FileExistsError(f'{submission} code found on server')
        # check zip
        if not is_zipfile(code_file):
            raise ValueError('only accept zip file.')
        # save source
        self.code_dir.mkdir()
        with ZipFile(code_file) as f:
            f.extractall(self.code_dir)
        current_app.logger.debug(f'{self} code updated.')
        self.update(code=True, status=-1)
        self.reload()
        zip_path = self.make_source_zip()

        # we no need to actually send code to sandbox during testing
        if current_app.config['TESTING']:
            return False
        return self.send(zip_path)

    def send(self, code_zip_path) -> bool:
        '''
        send code to sandbox

        Args:
            code_zip_path: code path for the user's code zip file
        '''
        # prepare problem testcase
        # get testcases
        cases = self.problem.test_case.cases
        # metadata
        meta = {'language': self.language, 'tasks': []}
        # problem path
        testcase_zip_path = SubmissionConfig.TMP_DIR / str(
            self.problem_id) / 'testcase.zip'
        current_app.logger.debug(f'testcase path: {testcase_zip_path}')

        h = hash(str(self.problem.test_case.to_mongo()))
        if p_hash.get(self.problem_id) != h:
            p_hash[self.problem_id] = h
            testcase_zip_path.parent.mkdir(exist_ok=True)
            with ZipFile(testcase_zip_path, 'w') as zf:
                for i, case in enumerate(cases):
                    meta['tasks'].append({
                        'caseCount': case['case_count'],
                        'taskScore': case['case_score'],
                        'memoryLimit': case['memory_limit'],
                        'timeLimit': case['time_limit']
                    })

                    case_io = zip(case['input'], case['output'])
                    for j, (ip, op) in enumerate(case_io):
                        filename = f'{i:02d}{j:02d}'
                        zf.writestr(f'{filename}.in', ip)  # input
                        zf.writestr(f'{filename}.out', op)  # output

        # setup post body
        post_data = {
            'token': SubmissionConfig.SANDBOX_TOKEN,
            'checker': 'print("not implement yet. qaq")',
        }
        files = {
            'src': (
                f'{self.id}-source.zip',
                code_zip_path.open('rb'),
            ),
            'testcase': (
                f'{self.id}-testcase.zip',
                testcase_zip_path.open('rb'),
            ),
            'meta.json': (
                f'{self.id}-meta.json',
                io.StringIO(json.dumps(meta)),
            ),
        }

        judge_url = f'{SubmissionConfig.JUDGE_URL}/{self.id}'

        # send submission to snadbox for judgement
        resp = rq.post(
            judge_url,
            data=post_data,
            files=files,
        )

        # Queue is full now
        if resp.status_code == 500:
            raise JudgeQueueFullError
        # Invlid data
        elif resp.status_code == 400:
            raise ValueError(resp.text)
        elif resp.status_code != 200:
            exit(10086)
        return True

    def process_result(self, tasks: list):
        for task in tasks:
            for case in task:
                del case['exitCode']

        # process task
        for i, cases in enumerate(tasks):
            # find significant case
            _cases = cases[:]
            score = 0
            if not all(c['status'] == 0 for c in _cases):
                _cases = [*filter(lambda c: c['status'] != 0, _cases)]
            else:
                score = self.problem.cases[i].case_score
            case = sorted(
                _cases[:],
                lambda c: (c['memoryUsage'], c['execTime']),
            )[-1]
            tasks[i] = engine.TaskResult(
                status=case['status'],
                exec_time=case['exec_time'],
                memory_usage=case['memoryUsage'],
                score=score,
                cases=cases,
            )

        # get the task which has the longest memory usage, execution time
        _tasks = tasks[:]
        if not all(t['status'] == 0 for t in _tasks):
            _tasks = [*filter(lambda t: t['status'] != 0, _tasks)]
        m_task = sorted(
            tasks,
            key=lambda t: (t['memoryUsage'], t['execTime']),
        )[-1]

        submission.update(
            score=sum(task.score for task in tasks),
            status=m_task['status'],
            tasks=tasks,
            exec_time=m_task['execTime'],
            memory_usage=m_task['memoryUsage'],
        )

        # update user's submission
        user.add_submission(submission.reload())
        # update homework data
        for homework in submission.problem.homeworks:
            stat = homework.student_status[user.username][str(
                submission.problem_id)]
            stat['submissionIds'].append(submission.id)
            if submission.score >= stat['score']:
                stat['score'] = submission.score
                stat['problemStatus'] = submission.status
        # update problem
        ac_submissions = Submission.filter(
            user=user,
            offset=0,
            count=-1,
            problem=submission.problem,
            status=0,
        )
        ac_users = {s.user.username for s in ac_submissions}
        submission.problem.ac_user = len(ac_users)
        submission.problem.save()

        return True

    @staticmethod
    def count():
        return len(engine.Submission.objects)

    @staticmethod
    def filter(
        user,
        offset,
        count,
        problem=None,
        submission=None,
        q_user=None,
        status=None,
        language_type=None,
    ):
        if offset is None or count is None:
            raise ValueError('offset and count are required!')
        try:
            offset = int(offset)
            count = int(count)
        except ValueError:
            raise ValueError('offset and count must be integer!')
        if offset < 0:
            raise ValueError(f'offset must >= 0! get {offset}')
        if count < -1:
            raise ValueError(f'count must >=-1! get {count}')
        if not isinstance(problem, Problem):
            problem = Problem(problem).obj
        if isinstance(submission, Submission):
            submission = submission.id
        if not isinstance(q_user, User):
            q_user = User(q_user)
            q_user = q_user.obj if q_user else None

        # query args
        q = {
            'problem': problem,
            'id': submission,
            'status': status,
            'language': language_type,
            'user': q_user
        }
        q = {k: v for k, v in q.items() if v is not None}

        submissions = engine.Submission.objects(**q).order_by('-timestamp')
        submissions = [
            *filter(lambda s: can_view(user, s.problem), submissions)
        ]

        if offset >= len(submissions) and len(submissions):
            raise ValueError(f'offset ({offset}) is out of range!')

        right = min(offset + count, len(submissions))
        if count == -1:
            right = len(submissions)

        return submissions[offset:right]

    @staticmethod
    def count():
        return engine.Submission.objects.count()

    @classmethod
    def add(
            cls,
            problem_id: str,
            username: str,
            lang: int,
            timestamp: date,
    ) -> 'Submission':
        '''
        Insert a new submission into db

        Returns:
            The created submission
        '''
        user = User(username)
        if not user:
            raise engine.DoesNotExist(f'user {username} does not exist')

        problem = Problem(problem_id)
        if problem.obj is None:
            raise engine.DoesNotExist(f'problem {problem_id} dose not exist')

        submission = engine.Submission(
            problem=problem.obj,
            user=user.obj,
            language=lang,
            timestamp=timestamp,
        )
        submission.save()

        return cls(submission.id)
