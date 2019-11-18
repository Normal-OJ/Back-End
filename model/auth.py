from flask import Blueprint
from functools import wraps
from mongo import User

from .utils import HTTPResponse, HTTPError, Request, send_noreply

import jwt
import os

JWT_ISS = os.environ.get('JWT_ISS')
JWT_SECRET = os.environ.get('JWT_SECRET')

auth_api = Blueprint('auth_api', __name__)


def login_required(func):
    @wraps(func)
    @Request.cookies(vars_dict={ 'token': 'jwt' })
    def wrapper(token, *args, **kwargs):
        if token == None:
            return HTTPError('Not logged in.', 403)
        try:
            json = jwt.decode(token, JWT_SECRET, issuer=JWT_ISS)
        except:
            return HTTPError('Invalid token.', 403)
        user = User(json['data']['username'])
        if not user.is_valid:
            return HTTPError('Invalid user.', 403)
        return func(*args, **kwargs) 
    return wrapper


@auth_api.route('/signup', methods=['POST'])
@Request.json(['username', 'password', 'email'])
def signup(username, password, email):
    if not all([username, password, email]):
        return HTTPError('Incomplete data.', 400)
    if len(username) > 16:
        return HTTPError('Length of username should be <= 16.', 400)
    user = User.signup(username, password, email)
    if user == None:
        return HTTPError('User exists.', 400)
    send_noreply([email], '[N-OJ] Varify Your Email', user.jwt)
    return HTTPResponse('Signup success.')


@auth_api.route('/login', methods=['POST'])
@Request.json(['username', 'password'])
def login(username, password):
    if not all([username, password]):
        return HTTPError('Incomplete data.', 400)
    user = User.login(username, password)
    if user == None:
        return HTTPError('Login failed.', 403)
    cookies = {'jwt': user.jwt}
    return HTTPResponse('Login success.', cookies=cookies)


@auth_api.route('/logout', methods=['POST'])
@login_required
def logout():
    return HTTPResponse('Logout success.', cookies={'jwt': None})
