from mongoengine import connect
from mongo.user import User
from .conftest import *


class BaseTester:
    MONGO_HOST = 'mongomock://localhost'
    DB = 'normal-oj'
    USER_CONFIG = 'tests/user.json'

    @classmethod
    def drop_db(cls):
        conn = connect(cls.DB, host=cls.MONGO_HOST)
        conn.drop_database(cls.DB)

    @classmethod
    def setup_class(cls):
        cls.drop_db()

        with open(cls.USER_CONFIG) as f:
            import json
            config = json.load(f)
            users = {}
            tcls = cls
            while True:
                users.update(config.get(tcls.__name__, {}))
                if tcls.__name__ == 'BaseTester':
                    break
                tcls = tcls.__base__

            for name, role in users.items():
                cls.new_user(name, role)

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
        user.update(active=True, role=role)
