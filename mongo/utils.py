import abc
import hashlib
import os
import redis
from functools import wraps
from typing import Dict, Optional, Any, TYPE_CHECKING
from . import engine

if TYPE_CHECKING:
    from .user import User
    from .problem import Problem

__all__ = (
    'hash_id',
    'perm',
    'can_view_problem',
    'RedisCache',
    'doc_required',
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


def can_view_problem(user: 'User', problem: 'Problem'):
    '''cheeck if a user can view the problem'''
    from .user import User
    if user.role == User.engine.Role.ADMIN:
        return True
    if user.contest:
        if user.contest in problem.contests:
            return True
        return False
    if user.username == problem.owner:
        return True
    for course in problem.courses:
        permission = 1 if course.course_name == 'Public' else perm(
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


def doc_required(
    src,
    des,
    cls=None,
    null=False,
):
    '''
    query db to inject document into functions.
    if the document does not exist in db, raise `engine.DoesNotExist`.
    if `src` not in parameters, this funtcion will raise `TypeError`
    `doc_required` will check the existence of `des` in `func` parameters,
    if `des` is exist, this function will override it, so `src == des`
    are acceptable
    '''
    # user the same name for `src` and `des`
    # e.g. `doc_required('user', User)` will replace parameter `user`
    if cls is None:
        cls = des
        des = src

    def deco(func):

        @wraps(func)
        def wrapper(*args, **ks):
            # try get source param
            if src not in ks:
                raise TypeError(f'{src} not found in function argument')
            src_param = ks.get(src)
            # convert it to document
            # TODO: add type checking, whether the cls is a subclass of `MongoBase`
            #       or maybe it is not need
            if type(cls) != type:
                raise TypeError('cls must be a type')
            # process `None`
            if src_param is None:
                if not null:
                    raise ValueError('src can not be None')
                doc = None
            elif not isinstance(src_param, cls):
                doc = cls(src_param)
            # or, it is already target class instance
            else:
                doc = src_param
            # not None and non-existent
            if doc is not None and not doc:
                raise engine.DoesNotExist(f'{doc} not found!')
            # replace original paramters
            del ks[src]
            if des in ks:
                current_app.logger.warning(
                    f'replace a existed argument in {func}')
            ks[des] = doc
            return func(*args, **ks)

        return wrapper

    return deco


def drop_none(d: Dict):
    return {k: v for k, v in d.items() if v is not None}
