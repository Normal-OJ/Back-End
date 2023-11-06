import pymongo

from . import MONGO_HOST, DATABASE


def main():
    client = pymongo.MongoClient(MONGO_HOST)
    db = client[DATABASE]
    collection = db['course']
    collection.update_many({}, {'$unset': {'contests': 1}})
    collection = db['problem']
    collection.update_many({}, {'$unset': {'contests': 1}})


main()
