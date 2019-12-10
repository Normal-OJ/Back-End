from mongoengine import connect

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
    
    @classmethod
    def teardown_class(cls):
        cls.drop_db()