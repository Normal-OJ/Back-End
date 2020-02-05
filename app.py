from flask import Flask
from model import *
from mongo import *
from mongo import engine
from mongo import problem

# Create a flask app
app = Flask(__name__)
app.url_map.strict_slashes = False

# Regist flask blueprint
app.register_blueprint(auth_api, url_prefix='/auth')
app.register_blueprint(profile_api, url_prefix='/profile')
app.register_blueprint(problem_api, url_prefix='/problem')
app.register_blueprint(submission_api, url_prefix='/submission')
app.register_blueprint(inbox_api, url_prefix='/inbox')
app.register_blueprint(course_api, url_prefix='/course')
app.register_blueprint(homework_api, url_prefix='/homework')
app.register_blueprint(inbox_api, url_prefix='/inbox')
app.register_blueprint(test_api, url_prefix='/test')
app.register_blueprint(ann_api, url_prefix='/ann')
app.register_blueprint(ranking_api, url_prefix='/ranking')
app.register_blueprint(contest_api, url_prefix='/contest')
app.register_blueprint(post_api, url_prefix='/post')
app.register_blueprint(copycat_api, url_prefix='/copycat')

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
