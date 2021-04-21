import abc
import hashlib
import os
import redis
from typing import Optional, Any

__all__ = (
    'hash_id',
    'perm',
    'can_view_problem',
    'RedisCache',
)


def hash_id(salt, text):
    text = ((salt or '') + (text or '')).encode()
    sha = hashlib.sha3_512(text)
    return sha.hexdigest()[:24]


def perm(course, user):
    '''4: admin, 3: teacher, 2: TA, 1: student, 0: not found
    '''
    return 4 - [
        user.role == 0, user == course.teacher, user in course.tas,
        user.username in course.student_nicknames.keys(), True
    ].index(True)


def can_view_problem(user, problem):
    '''cheeck if a user can view the problem'''
    if user.role == 0:
        return True
    if user.contest:
        if user.contest in problem.contests:
            return True
        return False
    if user.username == problem.owner:
        return True
    for course in problem.courses:
        permission = 1 if course.course_name == "Public" else perm(
            course, user)
        if permission and (problem.problem_status == 0 or permission >= 2):
            return True
    return False


class Cache(abc.ABC):
    @abc.abstractmethod
    def exists(self, key: str) -> bool:
        '''
        check whether a value exists
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def get(self, key: str):
        '''
        get value by key
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def set(self, key: str, value, ex: Optional[int] = None):
        '''
        set a value and set expire time in seconds
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def delete(self, key: str):
        '''
        delete a value by key
        '''
        raise NotImplementedError


class RedisCache(Cache):
    POOL = None

    def __new__(cls) -> Any:
        if cls.POOL is None:
            cls.HOST = os.getenv('REDIS_HOST')
            cls.PORT = os.getenv('REDIS_PORT')
            cls.POOL = redis.ConnectionPool(
                host=cls.HOST,
                port=cls.PORT,
                db=0,
            )

        return super().__new__(cls)

    def __init__(self) -> None:
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if self.PORT is None:
                import fakeredis
                self._client = fakeredis.FakeStrictRedis()
            else:
                self._client = redis.Redis(connection_pool=self.POOL)
        return self._client

    def exists(self, key: str) -> bool:
        return self.client.exists(key)

    def get(self, key: str):
        return self.client.get(key)

    def delete(self, key: str):
        return self.client.delete(key)

    def set(self, key: str, value, ex: Optional[int] = None):
        return self.client.set(key, value, ex=ex)
