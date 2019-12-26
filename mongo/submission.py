from mongoengine import NotUniqueError
from datetime import date
from typing import List

from . import engine
from .user import User

__all__ = ['Submission']


class Submission:
    def __init__(self, submission_id):
        self.submission_id = submission_id

    def __getattr__(self, name):
        if not self.exist:
            return None
        # convert mongo ObjectId to hex string for serialize
        if name == 'id':
            return str(self.obj.id)
        return self.obj.__getattribute__(name)

    def __str__(self):
        return f'submission [{self.submission_id}]'

    @property
    def exist(self):
        try:
            self.obj = engine.Submission.objects.get(id=self.submission_id)
        except engine.DoesNotExist:
            return False
        return True

    @classmethod
    def add(cls, problem_id: str, user: User, lang: int,
            timestamp: date) -> str:
        '''
        Insert a new submission into db

        Returns:
            The created submission's unique id in string type
        '''
        submission = engine.Submission(
            problem_id=problem_id,
            user=user,
            language=lang,
            timestamp=timestamp)
        submission.save()
        return str(submission.id)
