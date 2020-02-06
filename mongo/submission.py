import json
import os
import pathlib
import secrets
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

    def submit(self, code_file) -> bool:
        '''
        prepara data for submit code to sandbox and then send it

        Args:
            code_file: a zip file contains user's code
        '''
        # unexisted id
        if not self:
            raise engine.DoesNotExist(f'{self}')
        if self.code_dir.is_dir():
            raise FileExistsError(f'{submission} code found on server')

        # create submission folder
        self.code_dir.mkdir()
        # tmp path to store zipfile
        zip_path = self.tmp_dir / 'source.zip'
        zip_path.parent.mkdir()
        zip_path.write_bytes(code_file.read())
        if not is_zipfile(zip_path):
            # delete source file
            zip_path.unlink()
            raise ValueError('only accept zip file.')
        with ZipFile(zip_path, 'r') as f:
            f.extractall(self.code_dir)
        self.update(code=True, status=-1)

        # we no need to actually send code to sandbox during testing
        if current_app.config['TESTING']:
            return False
        return self.send(zip_path)

    def send(self, code_path) -> bool:
        '''
        send code to sandbox

        Args:
            code_path: code path for the user's code zip file
        '''
        # prepare problem testcase
        # get testcases
        cases = self.problem.test_case.cases
        # metadata
        meta = {'language': self.language, 'tasks': []}
        # problem path
        testcase_zip_path = SubmissionConfig.TMP_DIR / str(
            self.problem_id) / 'testcase.zip'

        h = hash(str(cases))
        if p_hash.get(self.problem_id) != h:
            p_hash[self.problem_id] = h
            with ZipFile(testcase_zip_path, 'w') as zf:
                for i, case in enumerate(cases):
                    meta['tasks'].append({
                        'caseCount': case['case_count'],
                        'taskScore': case['case_score'],
                        'memoryLimit': case['memory_limit'],
                        'timeLimit': case['time_limit']
                    })

                    for j in range(len(case['input'])):
                        filename = f'{i:02d}{j:02d}'
                        zf.writestr(f'{filename}.in', case['input'][j])
                        zf.writestr(f'{filename}.out', case['output'][j])

        # generate token for submission
        token = assign_token(self.id)
        # setup post body
        post_data = {
            'token': token,
            'checker': 'print("not implement yet. qaq")',
        }
        files = {
            'src': (
                f'{self.id}-source.zip',
                zip_path.open('rb'),
            ),
            'testcase': (
                f'{self.id}-testcase.zip',
                testcase_zip_path.open('rb'),
            ),
            'meta.json': (f'{self.id}-meta.json', io.BytesIO(str(meta)))
        }

        judge_url = f'{SubmissionConfig.JUDGE_URL}/{self.id}'

        # send submission to snadbox for judgement
        resp = rq.post(
            judge_url,
            data=post_data,
            files=files,
            cookies=request.cookies,
        )  # cookie: for debug, need better solution

        # Queue is full now
        if resp.status_code == 500:
            raise JudgeQueueFullError
        # Invlid data
        elif resp.status_code == 400:
            raise ValueError(resp.text)
        elif resp.status_code != 200:
            exit(10086)
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
