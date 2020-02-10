import logging
from flask import Flask
from model import *
from mongo import *
from mongo import engine
from mongo import problem

logging.basicConfig(
    filename='backend.log',
    level=logging.DEBUG,
)

# Create a flask app
app = Flask(__name__)
app.url_map.strict_slashes = False

# Register flask blueprint
api2prefix = [
    (auth_api, '/auth'),
    (profile_api, '/profile'),
    (problem_api, '/problem'),
    (submission_api, '/submission'),
    (inbox_api, '/inbox'),
    (course_api, '/course'),
    (homework_api, '/homework'),
    (test_api, '/test'),
    (ann_api, '/ann'),
    (ranking_api, '/ranking'),
    (contest_api, '/contest'),
    (post_api, '/post'),
    (copycat_api, '/copycat'),
]
for api, prefix in api2prefix:
    app.register_blueprint(api, url_prefix=prefix)

if not User("first_admin"):
    ADMIN = {
        'username': 'first_admin',
        'password': 'firstpasswordforadmin',
        'email': 'i.am.first.admin@noj.tw'
    }
    PROFILE = {
        'displayed_name': 'the first admin',
        'bio': 'I am super good!!!!!'
    }

    admin = User.signup(**ADMIN)
    admin.update(active=True, role=0, profile=PROFILE)

if Course("Public").obj is None:
    add_course("Public", "first_admin")

if Number("serial_number").obj is None:
    engine.Number(name="serial_number").save()

problem.number = Number("serial_number").obj.number
