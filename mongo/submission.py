import json
from mongoengine import NotUniqueError
from datetime import date
from typing import List

from . import engine
from .base import MongoBase
from .user import User
from .problem import Problem

__all__ = ['Submission']


class Submission(MongoBase, engine=engine.Submission):
    def __init__(self, submission_id):
        self.submission_id = submission_id

    def __getattr__(self, name):
        # convert mongo ObjectId to hex string for serialize
        if name == 'id':
            return str(self.obj.id)
        return super().__getattr__(name)

    def __str__(self):
        return f'submission [{self.submission_id}]'

    @property
    def to_py_obj(self):
        if not self:
            return {}

        old_keys = [
            '_id',
            # 'problem',
        ]
        new_keys = [
            'submissionId',
            # 'problemId',
        ]
        ret = json.loads(self.obj.to_json())
        for old, new in zip(old_keys, new_keys):
            ret[new] = ret[old]['$oid']
            del ret[old]

        ret['timestamp'] = ret['timestamp']['$date'] // 1000
        ret['problemId'] = engine.Problem.objects.get(
            id=ret['problem']['$oid']).problem_id
        del ret['problem']

        return ret

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
