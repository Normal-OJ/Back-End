import json
import os
import pathlib
from datetime import date
from typing import List
from model.submission_config import SubmissionConfig

from . import engine
from .base import MongoBase
from .user import User
from .problem import Problem

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

    def get_code(self, path: str):
        path = SubmissionConfig.SOURCE_PATH / self.id / path

        if not path.exists():
            raise FileNotFoundError(path)

        with open(path) as f:
            ret = f.read()

        return ret

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
            user=engine.User(username=username),
            language=lang,
            timestamp=timestamp,
        )
        submission.save()

        return cls(str(submission.id))
