from mongoengine import connect
from mongo.user import User
from .conftest import *


class BaseTester:
    MONGO_HOST = 'mongomock://localhost'
    DB = 'normal-oj'

    @classmethod
    def drop_db(cls):
        conn = connect(cls.DB, host=cls.MONGO_HOST)
        conn.drop_database(cls.DB)

    @classmethod
    def setup_class(cls):
        cls.drop_db()

        ADMIN = {
            'username': 'admin',
            'password': 'verysuperstrongandlongpasswordforadmin',
            'email': 'i.am.admin@noj.tw'
        }

        admin = User.signup(**ADMIN)
        admin.update(active=True, role=0)

        TEACHER = {
            'username': 'teacher',
            'password': 'strongandlongpasswordforteacher',
            'email': 'i.am.teacher@noj.tw'
        }

        teacher = User.signup(**TEACHER)
        teacher.update(active=True, role=1)

        STUDENT = {
            'username': 'student',
            'password': 'normalpasswordforstudent',
            'email': 'i.am.student@noj.tw'
        }

        student = User.signup(**STUDENT)
        student.update(active=True, role=2)

    @classmethod
    def teardown_class(cls):
        cls.drop_db()

    @classmethod
    def new_user(cls, username, role):
        USER = {
            'username': username,
            'password': f'{username}_password',
            'email': f'i.am.{username}@noj.tw'
        }

        user = User.signup(**USER)
        user.update(active=True, role=1)
        c = client()
        c.set_cookie('test.test', 'piann', User(user).jwt)
        return c
