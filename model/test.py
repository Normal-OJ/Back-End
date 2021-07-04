from flask import Blueprint, current_app, request

from .auth import *
from .utils import *

__all__ = ['test_api']

test_api = Blueprint('test_api', __name__)


@test_api.route('/')
@login_required
def test(user):
    return HTTPResponse(user.username)


@test_api.route('/role')
@identity_verify(0, 1, ...)
def role(user):
    return HTTPResponse(str(user.obj.role))


@test_api.route('/log')
def log():
    current_app.logger.debug('this is a DEBUG log')
    current_app.logger.info('this is a INFO log')
    current_app.logger.warning('this is a WARNING log')
    current_app.logger.error('this is a ERROR log')
    current_app.logger.critical('this is a CRITICAL log')
    return HTTPResponse('check the log')


@test_api.route('/header')
def check_header():
    current_app.logger.debug(f'{request.headers}')
    return HTTPResponse('ok')
