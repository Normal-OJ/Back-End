from __future__ import annotations
from datetime import datetime, timedelta
from hmac import compare_digest
from typing import Any, Dict, List, TYPE_CHECKING, Optional

from . import engine, course
from .utils import *
from .base import *

import hashlib
import jwt
import os
import re

if TYPE_CHECKING:
    from .course import Course

__all__ = ['User', 'jwt_decode']

JWT_EXP = timedelta(days=int(os.environ.get('JWT_EXP', '30')))
JWT_ISS = os.environ.get('JWT_ISS', 'test.test')
JWT_SECRET = os.environ.get('JWT_SECRET', 'SuperSecretString')


class User(MongoBase, engine=engine.User):
    @classmethod
    def signup(cls, username, password, email):
        if re.match(r'^[a-zA-Z0-9_\-]+$', username) is None:
            raise ValueError(f'Invalid username [username={username}]')
        user = cls(username)
        user_id = hash_id(user.username, password)
        email = email.lower().strip()
        cls.engine(
            user_id=user_id,
            user_id2=user_id,
            username=user.username,
            email=email,
            md5=hashlib.md5(email.encode()).hexdigest(),
            active=False,
        ).save(force_insert=True)
        return user.reload()

    @classmethod
    def batch_signup(
        cls,
        new_users: List[Dict[str, str]],
        course: Optional['Course'] = None,
    ):
        '''
        Register multiple students with course
        '''
        # Validate
        keys = {'username', 'password', 'email'}
        if any(({*u.keys()} < keys) for u in new_users):
            raise ValueError('The input of batch_signup has invalid keys')
        for u in new_users:
            if (role := u.get('role')) is not None:
                try:
                    role = int(role)
                    u['role'] = role
                except ValueError:
                    username = u['username']
                    raise ValueError(
                        'Got invalid role in batch signup '
                        f'[username={username}, role={role}]', )
        # Register
        registered_users = []
        for u in new_users:
            try:
                displayed_name = u.pop('displayedName')
                if displayed_name is not None:
                    activate_payload = {'displayedName': displayed_name}
                else:
                    activate_payload = {}
                role = u.pop('role')
                new_user = cls.signup(**u)
                new_user.activate(activate_payload)
                if role is not None:
                    new_user.update(role=role)
                    new_user.reload('role')
            except engine.NotUniqueError:
                try:
                    new_user = cls.get_by_username(u['username'])
                except engine.DoesNotExist:
                    new_user = cls.get_by_email(u['email'])
            registered_users.append(new_user)
        if course is not None:
            new_student_nicknames = {
                **course.student_nicknames,
                **{u.username: u.username
                   for u in registered_users}
            }
            course.update_student_namelist(new_student_nicknames)
        return new_users

    @classmethod
    def login(cls, username, password):
        try:
            user = cls.get_by_username(username)
        except engine.DoesNotExist:
            user = cls.get_by_email(username)
        user_id = hash_id(user.username, password)
        if (compare_digest(user.user_id, user_id)
                or compare_digest(user.user_id2, user_id)):
            return user
        raise engine.DoesNotExist

    @classmethod
    def get_by_username(cls, username):
        obj = cls.engine.objects.get(username=username)
        return cls(obj)

    @classmethod
    def get_by_email(cls, email):
        obj = cls.engine.objects.get(email=email.lower())
        return cls(obj)

    @property
    def displayedName(self):
        return self.profile.displayed_name

    @property
    def bio(self):
        return self.profile.bio

    @property
    def cookie(self):
        keys = (
            'username',
            'email',
            'md5',
            'active',
            'role',
            'profile',
            'editorConfig',
        )
        return self.jwt(*keys)

    @property
    def secret(self):
        keys = (
            'username',
            'userId',
        )
        return self.jwt(*keys, secret=True)

    def jwt(self, *keys, secret=False, **kwargs):
        if not self:
            return ''
        data = self.properties(*keys)
        data.update(kwargs)
        payload = {
            'iss': JWT_ISS,
            'exp': datetime.now() + JWT_EXP,
            'secret': secret,
            'data': data
        }
        return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

    def properties(self, *keys) -> Dict[str, Any]:
        '''
        Extract proeprties from user and serialize it to a dictionary
        '''
        whiltelists = {
            'username',
            'userId',
            'email',
            'md5',
            'active',
            'role',
            'profile',
            'editorConfig',
            'bio',
            'displayedName',
        }
        if any((k not in whiltelists) for k in keys):
            raise ValueError('Found unallowed key')
        user = self.reload().to_mongo()
        user['username'] = user.get('_id')
        return {k: user.get(k, getattr(self, k, None)) for k in keys}

    def change_password(self, password):
        user_id = hash_id(self.username, password)
        self.update(user_id=user_id, user_id2=user_id)
        self.reload()

    def activate(self, profile={}) -> 'User':
        '''
        activate a user

        raises:
            ValidationError: when user field in db is wrong or data isn't valid
            engine.DoesNotExist
        '''
        # check whether `Public` is exists
        pub_course = course.Course('Public').obj
        if pub_course is None:
            raise engine.DoesNotExist('Public Course Not Exists')
        # update user data
        self.update(
            active=True,
            profile={
                'displayed_name': profile.get('displayedName'),
                'bio': profile.get('bio'),
            },
            push__courses=pub_course,
        )
        # update `Public`
        pub_course.student_nicknames.update({
            self.username: self.username,
        })
        return self.reload()

    def add_submission(self, submission: engine.Submission):
        if submission.score == 100:
            self.update(
                add_to_set__AC_problem_ids=submission.problem_id,
                inc__AC_submission=1,
            )
        self.submission += 1
        self.save()


def jwt_decode(token):
    try:
        json = jwt.decode(
            token,
            JWT_SECRET,
            issuer=JWT_ISS,
            algorithms='HS256',
        )
    except jwt.exceptions.PyJWTError:
        return None
    return json
