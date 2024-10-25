from datetime import datetime
from . import engine
from .base import *

class LoginRecord(MongoBase, engine=engine.LoginRecords):
    @classmethod
    def record_login(cls, user_id, ip_addr, success)->None:
        cls.engine(
            user_id=user_id,
            ip_addr=ip_addr,
            success=success,
            last_login=datetime.now()
        ).save(force_insert=True)

    @classmethod
    def get_records_by_ip(cls, ip_addr):
        return cls.engine.objects.get(ip_addr=ip_addr)


    @classmethod
    def get_records_by_user_id(cls, user_id):
        return cls.engine.objects.get(user_id=user_id)
