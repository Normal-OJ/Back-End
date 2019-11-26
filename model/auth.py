from flask import Blueprint
from functools import wraps
from mongo import User, NotUniqueError, ValidationError

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
            return HTTPError('Inactive user.', 403)
        return func(*args, **kwargs) 
    return wrapper


@auth_api.route('/signup', methods=['POST'])
@Request.json(['username', 'password', 'email'])
def signup(username, password, email):
    try:
        user = User.signup(username, password, email)
    except ValidationError as ve:
        return HTTPError('Signup failed.', 400, data=ve.to_dict())
    except NotUniqueError as ne:
        return HTTPError('User exists.', 400)
    verify_link = f'https://noj.tw/email_verify?token={user.jwt}'
    send_noreply([email], '[N-OJ] Varify Your Email', verify_link)
    return HTTPResponse('Signup success')


@auth_api.route('/check_username', methods=['POST'])
@Request.json(['username'])
def check_username(username):
    if User(username).obj != None:
        return HTTPResponse('User exists.', data={'valid': 0})
    return HTTPResponse('Username can be used.', data={'valid': 1})


@auth_api.route('/check_email', methods=['POST'])
@Request.json(['email'])
def check_email(email):
    if User.get_username_by_email(email) != None:
        return HTTPResponse('Email has been used.', data={'valid': 0})
    return HTTPResponse('Email can be used.', data={'valid': 1})


@auth_api.route('/login', methods=['POST'])
@Request.json(['username', 'password'])
def login(username, password):
    if not all([username, password]):
        return HTTPError('Incomplete data.', 400)
    user = User.login(username, password)
    if user == None:
        return HTTPError('Login failed.', 403)
    if not user.is_valid:
        return HTTPError('Invalid user.', 403)
    cookies = {'jwt': user.jwt}
    return HTTPResponse('Login success.', cookies=cookies)


@auth_api.route('/logout', methods=['POST'])
@login_required
def logout():
    return HTTPResponse('Logout success.', cookies={'jwt': None})


@auth_api.route('/active', methods=['POST'])
@Request.json(['profile', 'agreement'])
@Request.cookies(vars_dict={ 'token': 'jwt' })
def active(profile, agreement, token):
    if not all([type(profile) == dict, agreement]):
        return HTTPError('Invalid data.', 400)
    if agreement is not True:
        return HTTPError('You should confirm the agreement.', 403)
    try:
        json = jwt.decode(token or '', JWT_SECRET, issuer=JWT_ISS)
    except:
        return HTTPError('Invalid token.', 403)
    user = User(json['data']['username'])
    if user.obj == None:
        return HTTPError('User not exists.', 400)
    try:
        user.obj.update(active=True, profile={
            'displayed_name': profile.get('displayed_name'),
            'bio': profile.get('bio'),
            'avatar_url': profile.get('avatar_url')
        })
    except ValidationError as ve:
        return HTTPError('Failed.', 400, data=ve.to_dict())
    return HTTPResponse('User is now active.')
