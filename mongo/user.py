from datetime import datetime, timedelta
from .utils import hash_id
from . import engine

import hashlib
import html
import jwt
import os

JWT_EXP = timedelta(days=int(os.environ.get('JWT_EXP')))
JWT_ISS = os.environ.get('JWT_ISS')
JWT_SECRET = os.environ.get('JWT_SECRET')


class User:
    def __init__(self, username):
        self.username = html.escape(username or '') or username

    @classmethod
    def signup(cls, username, password, email):
        user = cls(username)
        user_id = hash_id(user.username, password)
        engine.User(
            **{
                'user_id': user_id,
                'username': user.username,
                'email': email,
                'active': False
            }).save()
        return user

    @classmethod
    def login(cls, username, password):
        if cls(username).obj == None:
            username = cls.get_username_by_email(username)
            if username == None:
                return None
        user = cls(username)
        obj = user.obj
        user_id = hash_id(user.username, password)
        if obj and obj.user_id == user_id:
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
    def obj(self):
        try:
            obj = engine.User.objects.get(username=self.username)
        except:
            return None
        return obj
    
    @property
    def is_valid(self):
        obj = self.obj
        return obj if obj == None else obj.active

    @property
    def jwt(self):
        obj = self.obj
        if obj == None:
            return {}
        obj = obj.to_mongo()
        keys = ['username', 'email', 'profile', 'editor_config']
        data = {k: obj.get(k) for k in keys}
        payload = {
            'iss': JWT_ISS,
            'exp': datetime.utcnow() + JWT_EXP,
            'data': data
        }
        return jwt.encode(payload, JWT_SECRET, algorithm='HS256').decode()

    
