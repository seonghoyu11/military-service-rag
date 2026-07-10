from pymongo import MongoClient

import config

_client = MongoClient(config.MONGO_URI)


def get_db():
    """Returns the shared MongoDB Atlas database handle."""
    return _client[config.MONGO_DB_NAME]
