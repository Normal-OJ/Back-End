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
    from .course import Course  # pragma: no cover

__all__ = ['User', 'jwt_decode']

JWT_EXP = timedelta(days=int(os.environ.get('JWT_EXP', '30')))
JWT_ISS = os.environ.get('JWT_ISS', 'test.test')
JWT_SECRET = os.environ.get('JWT_SECRET', 'SuperSecretString')


class User(MongoBase, engine=engine.User):

    @classmethod
    def signup(
        cls,
        username: str,
        password: str,
        email: str,
    ):
        if re.match(r'^[a-zA-Z0-9_\-]+$', username) is None:
            raise ValueError(f'Invalid username [username={username}]')
        user_id = hash_id(username, password)
        email = email.lower().strip()
        user = cls.engine(
            user_id=user_id,
            user_id2=user_id,
            username=username,
            email=email,
            md5=hashlib.md5(email.encode()).hexdigest(),
            active=False,
        ).save(force_insert=True)
        return cls(user).reload()

    @classmethod
    def batch_signup(
        cls,
        new_users: List[Dict[str, str]],
        course: Optional['Course'] = None,
        force: bool = False,
    ):
        '''
        Register multiple students with course
        '''
        # Validate
        keys = {'username', 'password', 'email'}
        if not all(({*u.keys()} >= keys) for u in new_users):
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
                new_user = cls.signup(
                    username=u['username'],
                    password=u['password'],
                    email=u['email'],
                )
                activate_payload = drop_none({
                    'displayedName':
                    u.get('displayedName'),
                })
                new_user.activate(activate_payload)
                if (role := u.get('role')) is not None:
                    new_user.update(role=role)
                    new_user.reload('role')
            except engine.NotUniqueError:
                try:
                    new_user = cls.get_by_username(u['username'])
                except engine.DoesNotExist:
                    new_user = cls.get_by_email(u['email'])
                if force:
                    new_user.force_update(u, course)
            registered_users.append(new_user)
        if course is not None:
            new_student_nicknames = {
                **course.student_nicknames,
                **{u.username: u.username
                   for u in registered_users}
            }
            course.update_student_namelist(new_student_nicknames)
        return new_users

    def force_update(self, new_user: Dict[str, Any], course: Optional[Course]):
        '''
        Force update an existent user in batch update procedure
        '''
        if (displayed_name := new_user.get('displayedName')) is not None:
            self.update(profile__displayed_name=displayed_name)
        if (role := new_user.get('role')) is not None:
            self.update(role=role)
        if (password := new_user.get('password')) is not None:
            self.change_password(password)
        if (email := new_user.get('email')) is not None:
            self.update(email=email,
                        md5=hashlib.md5(email.encode()).hexdigest())
        if course is not None:
            self.update(add_to_set__courses=course.id)
        self.reload()

    @classmethod
    def login(cls, username, password, ip_addr):
        try:
            user = cls.get_by_username(username)
        except engine.DoesNotExist:
            user = cls.get_by_email(username)
        user_id = hash_id(user.username, password)
        if (compare_digest(user.user_id, user_id)
                or compare_digest(user.user_id2, user_id)):
            engine.LoginRecords(user_id=user_id, ip_addr=ip_addr,
                                success=True).save(force_insert=True)
            return user
        engine.LoginRecords(user_id=user_id,
                            ip_addr=ip_addr).save(force_insert=True)
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
        user = self.to_mongo()
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
