from datetime import datetime, timedelta
from hmac import compare_digest

from . import engine
from .utils import *
from .base import *

import base64
import hashlib
import html
import json as jsonlib
import jwt
import os

__all__ = ['User', 'jwt_decode']

JWT_EXP = timedelta(days=int(os.environ.get('JWT_EXP', '30')))
JWT_ISS = os.environ.get('JWT_ISS', 'test.test')
JWT_SECRET = os.environ.get('JWT_SECRET', 'SuperSecretString')


class User(MongoBase, engine=engine.User):
    def __init__(self, username):
        self.username = username

    @classmethod
    def signup(cls, username, password, email):
        user = cls(username)
        user_id = hash_id(user.username, password)
        cls.engine(user_id=user_id,
                   username=user.username,
                   email=email,
                   active=False).save(force_insert=True)
        return user.reload()

    @classmethod
    def login(cls, username, password):
        try:
            user = cls.get_by_username(username)
        except engine.DoesNotExist:
            user = cls.get_by_email(username)
        user_id = hash_id(user.username, password)
        print(user.user_id, user_id)
        if compare_digest(user.user_id, user_id):
            return user
        raise engine.DoesNotExist

    @classmethod
    def get_by_username(cls, username):
        obj = cls.engine.objects.get(username=username)
        return cls(obj.username)

    @classmethod
    def get_by_email(cls, email):
        obj = cls.engine.objects.get(email=email)
        return cls(obj.username)

    @property
    def cookie(self):
        keys = [
            'username', 'email', 'active', 'role', 'profile', 'editorConfig'
        ]
        return self.jwt(*keys)

    @property
    def secret(self):
        keys = ['username', 'userId']
        return self.jwt(*keys, secret=True)

    def jwt(self, *keys, secret=False, **kwargs):
        if not self:
            return ''
        user = self.reload().to_mongo()
        user['username'] = user.get('_id')
        data = {k: user.get(k) for k in keys}
        data.update(kwargs)
        payload = {
            'iss': JWT_ISS,
            'exp': datetime.utcnow() + JWT_EXP,
            'secret': secret,
            'data': data
        }
        return jwt.encode(payload, JWT_SECRET, algorithm='HS256').decode()

    def change_password(self, password):
        user_id = hash_id(self.username, password)
        self.update(user_id=user_id)


def jwt_decode(token):
    try:
        json = jwt.decode(token,
                          JWT_SECRET,
                          issuer=JWT_ISS,
                          algorithms='HS256')
    except jwt.exceptions.PyJWTError:
        return None
    return json
