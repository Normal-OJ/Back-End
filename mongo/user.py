from datetime import datetime, timedelta
from .config import db, USER

import hashlib
import html
import jwt
import os

JWT_EXP = timedelta(days=int(os.environ.get('JWT_EXP')))
JWT_ISS = os.environ.get('JWT_ISS')
JWT_SECRET = os.environ.get('JWT_SECRET')

db_user = db[USER]


def hash_user_id(username, password):
    text = (username+password).encode()
    sha = hashlib.sha3_512(text)
    return sha.hexdigest()[:24]


class User:
    def __init__(self, username):
        self.username = html.escape(username)

    @classmethod
    def signup(cls, username, password, email):
        user = cls.get_user_by_email(email)
        if user:
            return None
        user = cls(username)
        if user.info:
            return None
        user_id = hash_user_id(user.username, password)
        db_user.insert_one({
            'userId': user_id,
            'username': user.username,
            'email': email,
            'active': False
        })
        return user

    @classmethod
    def login(cls, username, password):
        user = cls(username)
        user_id = hash_user_id(user.username, password)
        info = user.info
        if info and info['userId'] == user_id:
            return user
        user = cls.get_user_by_email(username)
        if user:
            user_id = hash_user_id(user.username, password)
            info = user.info
            if info and info['userId'] == user_id:
                return user
        return None

    @classmethod
    def get_user_by_email(cls, email):
        info = db_user.find_one({'email': email})
        if not info:
            return None
        return cls(info['username'])

    @property
    def info(self):
        return db_user.find_one({'username': self.username})
    
    @property
    def is_valid(self):
        info = self.info
        return info and info.get('active')

    @property
    def jwt_data(self):
        info = self.info
        if info == None:
            return {}
        keys = ['username', 'email', 'profile', 'editor']
        data = { k: info.get(k) for k in keys }
        return data

    @property
    def jwt(self):
        payload = {
            'iss': JWT_ISS,
            'exp': datetime.utcnow() + JWT_EXP,
            'data': self.jwt_data
        }
        return jwt.encode(payload, JWT_SECRET, algorithm='HS256').decode()

    
