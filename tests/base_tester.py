from mongoengine import connect
from mongo.user import User


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
        admin.obj.update(active=True, role=0)

    @classmethod
    def teardown_class(cls):
        cls.drop_db()
