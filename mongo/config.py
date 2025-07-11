import os

FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False') == 'True'
MINIO_HOST = os.getenv('MINIO_HOST')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY')
MINIO_BUCKET = os.getenv('MINIO_BUCKET', 'normal-oj-testing')
