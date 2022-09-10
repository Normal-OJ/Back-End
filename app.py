import logging
from flask import Flask
from model import *
from mongo import *


def app():
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
        (health_api, '/health'),
    ]
    for api, prefix in api2prefix:
        app.register_blueprint(api, url_prefix=prefix)

    if not User('first_admin'):
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
        # TODO: use a single method to active.
        #       we won't call `activate` here because it required the
        #       course 'Public' should exist, but create a course
        #       also need a teacher.
        #       but at least make it can work now...
        # admin.activate(PROFILE)
        admin.update(
            active=True,
            role=0,
            profile=PROFILE,
        )
    if not Course('Public'):
        Course.add_course('Public', 'first_admin')

    if __name__ != '__main__':
        logger = logging.getLogger('gunicorn.error')
        app.logger.handlers = logger.handlers
        app.logger.setLevel(logger.level)

    return app
