# Standard library
from functools import wraps
# Related third party imports
from flask import Blueprint, request
# Local application
from mongo import *
from .utils import *

import jwt
import os

__all__ = ['auth_api', 'login_required', 'identity_verify']

auth_api = Blueprint('auth_api', __name__)


def login_required(func):
    '''Check if the user is login

    Returns:
        - A wrapped function
        - 403 Not Logged In
        - 403 Invalid Token
        - 403 Inactive User
    '''
    @wraps(func)
    @Request.cookies(vars_dict={'token': 'piann'})
    def wrapper(token, *args, **kwargs):
        if token is None:
            return HTTPError('Not Logged In', 403)
        json = jwt_decode(token)
        if json is None:
            return HTTPError('Invalid Token', 403)
        user = User(json['data']['username'])
        if not user.active:
            return HTTPError('Inactive User', 403)
        kwargs['user'] = user
        return func(*args, **kwargs)

    return wrapper


def identity_verify(*roles):
    '''Verify a logged in user's identity

    You can find an example in `model/test.py`
    '''
    def verify(func):
        @wraps(func)
        @login_required
        def wrapper(user, *args, **kwargs):
            if user.role not in roles:
                return HTTPError('Insufficient Permissions', 403)
            kwargs['user'] = user
            return func(*args, **kwargs)

        return wrapper

    return verify


@auth_api.route('/session', methods=['GET', 'POST'])
def session():
    '''Create a session or remove a session.
    Request methods:
        GET: Logout
        POST: Login
    '''
    @login_required
    def logout(user):
        '''Logout a user.
        Returns:
            - 200 Logout Success
        '''
        cookies = {'jwt': None, 'piann': None}
        return HTTPResponse(f'Goodbye {user.username}', cookies=cookies)

    @Request.json('username', 'password')
    def login(username, password):
        '''Login a user.
        Returns:
            - 400 Incomplete Data
            - 403 Login Failed
        '''
        if not all([username, password]):
            return HTTPError('Incomplete Data', 400)
        user = User.login(username, password)
        if user is None:
            return HTTPError('Login Failed', 403)
        if not user.active:
            return HTTPError('Invalid User', 403)
        cookies = {'piann_httponly': user.jwt, 'jwt': user.info}
        return HTTPResponse('Login Success', cookies=cookies)

    methods = {'GET': logout, 'POST': login}

    return methods[request.method]()


@auth_api.route('/signup', methods=['POST'])
@Request.json('username', 'password', 'email')
def signup(username, password, email):
    if password is None:
        return HTTPError('Signup Failed',
                         400,
                         data={'password': 'Field is required'})
    try:
        user = User.signup(username, password, email)
    except ValidationError as ve:
        return HTTPError('Signup Failed', 400, data=ve.to_dict())
    except NotUniqueError as ne:
        return HTTPError('User Exists', 400)
    verify_link = f'https://noj.tw/api/auth/active/{user.jwt}'
    send_noreply([email], '[N-OJ] Varify Your Email', verify_link)
    return HTTPResponse('Signup Success')


@auth_api.route('/change-password', methods=['POST'])
@login_required
@Request.json('old_password', 'new_password')
def change_password(user, old_password, new_password):
    if new_password is None:
        return HTTPError('Signup Failed',
                         400,
                         data={'newPassword': 'Field is required'})
    if User.login(user.username, old_password) is None:
        return HTTPError('Wrong Password', 403)
    user.change_password(new_password)
    cookies = {'piann': None, 'jwt': None}
    return HTTPResponse('Password Has Been Changed', cookies=cookies)


@auth_api.route('/check/<item>', methods=['POST'])
def check(item):
    '''Checking when the user is registing.
    '''
    @Request.json('username')
    def check_username(username):
        if User(username).user_id is not None:
            return HTTPResponse('User Exists', data={'valid': 0})
        return HTTPResponse('Username Can Be Used', data={'valid': 1})

    @Request.json('email')
    def check_email(email):
        if User.get_username_by_email(email) is not None:
            return HTTPResponse('Email Has Been Used', data={'valid': 0})
        return HTTPResponse('Email Can Be Used', data={'valid': 1})

    method = {'username': check_username, 'email': check_email}.get(item)
    return method() if method else HTTPError('Ivalid Checking Type', 400)


@auth_api.route('/resend-email', methods=['POST'])
@Request.json('email')
def resend_email(email):
    username = User.get_username_by_email(email)
    if username is None:
        return HTTPError('User Not Exists', 400)
    user = User(username)
    if user.active:
        return HTTPError('User Has Been Actived', 400)
    verify_link = f'https://noj.tw/api/auth/active/{user.jwt}'
    send_noreply([email], '[N-OJ] Varify Your Email', verify_link)
    return HTTPResponse('Email Has Been Resent')


@auth_api.route('/active', methods=['POST'])
@auth_api.route('/active/<token>', methods=['GET'])
def active(token=None):
    '''Activate a user.
    '''
    @Request.json('profile', 'agreement')
    @Request.cookies(vars_dict={'token': 'piann'})
    def update(profile, agreement, token):
        '''User: active: flase -> true
        '''
        if not all([type(profile) == dict, agreement]):
            return HTTPError('Invalid Data', 400)
        if agreement is not True:
            return HTTPError('Not Confirm the Agreement', 403)
        json = jwt_decode(token)
        if json is None:
            return HTTPError('Invalid Token.', 403)
        user = User(json['data']['username'])
        if user.user_id is None:
            return HTTPError('User Not Exists', 400)
        if user.active:
            return HTTPError('User Has Been Actived', 400)
        try:
            user.update(active=True,
                        profile={
                            'displayed_name': profile.get('displayedName'),
                            'bio': profile.get('bio'),
                        })
        except ValidationError as ve:
            return HTTPError('Failed', 400, data=ve.to_dict())
        cookies = {'piann': None, 'jwt': None}
        return HTTPResponse('User Is Now Active', cookies=cookies)

    def redir():
        '''Redirect user to active page.
        '''
        json = jwt_decode(token)
        if json is None:
            return HTTPError('Invalid Token', 403)
        user = User(json['data']['username'])
        cookies = {'piann_httponly': token, 'jwt': user.info}
        return HTTPRedirect('/email_verify', cookies=cookies)

    methods = {'GET': redir, 'POST': update}
    return methods[request.method]()
