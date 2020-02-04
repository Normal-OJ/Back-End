import json
import os
import pathlib
from datetime import date
from typing import List
from model.submission_config import SubmissionConfig

from . import engine
from .base import MongoBase
from .user import User
from .problem import Problem, can_view

__all__ = ['Submission']


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
    def main_code_path(self) -> str:
        lang2ext = {
            0: '.c',
            1: '.cpp',
            2: '.py'
        }
        if self.language not in lang2ext:
            raise ValueError
        return SubmissionConfig.SOURCE_PATH / self.id / f'main.{lang2ext[self.language]}'

    def get_code(self, path: str):
        path = SubmissionConfig.SOURCE_PATH / self.id / path

        if not path.exists():
            raise FileNotFoundError(path)

        return path.read_text()

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
