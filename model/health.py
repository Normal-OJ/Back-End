from flask import Blueprint
from pymongo import MongoClient

from .utils import *
from mongo.utils import RedisCache
from mongo.engine import MONGO_HOST

__all__ = ('health_api', )

health_api = Blueprint('health_api', __name__)


@health_api.route('/')
def health():
    # Check mongo
    client = MongoClient(MONGO_HOST)
    mongo_ok = client.server_info().get('ok', 0) == 1.0
    # Check redis
    redis_ok = RedisCache().client.ping()
    noj_ok = mongo_ok and redis_ok
    if noj_ok:
        return HTTPResponse()
    else:
        return HTTPError(
            message='Service is not available',
            status_code=500,
            data={
                'mongo': mongo_ok,
                'redis': redis_ok
            },
        )
