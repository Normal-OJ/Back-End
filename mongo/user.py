from datetime import datetime, timedelta
from hmac import compare_digest

from . import engine
from .utils import *

import base64
import hashlib
import html
import json
import jwt
import os

__all__ = ['User', 'jwt_decode']

JWT_EXP = timedelta(days=int(os.environ.get('JWT_EXP', '30')))
JWT_ISS = os.environ.get('JWT_ISS', 'test.test')
JWT_SECRET = os.environ.get('JWT_SECRET', 'SuperSecretString')


class User:
    def __init__(self, username):
        self.username = html.escape(username or '') or username

    def __getattr__(self, name):
        try:
            obj = engine.User.objects.get(username=self.username)
        except engine.DoesNotExist:
            return None
        return obj.__getattribute__(name)

    def __eq__(self, other):
        return self.user_id == other.user_id

    @property
    def obj(self):
        try:
            obj = engine.User.objects.get(username=self.username)
        except:
            return None
        return obj

    @classmethod
    def signup(cls, username, password, email):
        user = cls(username)
        user_id = hash_id(user.username, password)
        engine.User(user_id=user_id,
                    username=user.username,
                    email=email,
                    active=False).save()
        return user

    @classmethod
    def login(cls, username, password):
        # try to find a user by username
        user = cls(username)
        if user.user_id is None:
            # try to find a user by email
            username = cls.get_username_by_email(username)
            if username is None:
                return None
            user = cls(username)
        # checking password hash
        user_id = hash_id(user.username, password)
        if compare_digest(user.user_id, user_id):
            return user
        return None

    @staticmethod
    def get_username_by_email(email):
        try:
            obj = engine.User.objects.get(email=email)
        except:
            return None
        return obj.username

    @property
    def jwt(self):
        if self.user_id is None:
            return ''
        user = self.to_mongo()
        keys = ['username']
        data = {k: user.get(k) for k in keys}
        payload = {
            'iss': JWT_ISS,
            'exp': datetime.utcnow() + JWT_EXP,
            'data': data
        }
        return jwt.encode(payload, JWT_SECRET, algorithm='HS256').decode()

    @property
    def info(self):
        if self.user_id is None:
            return ''
        user = self.to_mongo()
        keys = ['username', 'email', 'active', 'profile', 'editorConfig']
        data = {k: user.get(k) for k in keys}
        payload = {
            'iss': JWT_ISS,
            'exp': int((datetime.utcnow() + JWT_EXP).timestamp()),
            'data': data
        }
        head = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
        body = base64.b64encode(json.dumps(payload).encode()).decode()
        sign = hashlib.sha224(body.encode()).hexdigest()[:24]
        return '.'.join([head, body, sign])

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
