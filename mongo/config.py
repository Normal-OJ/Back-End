import pymongo

# Database name
DB_NAME = 'normal-oj'

# Collection name
USER = 'user'

mongo_client = pymongo.MongoClient('mongodb://mongo:27017/')
db = mongo_client[DB_NAME]
