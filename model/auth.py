from flask import Blueprint, request
from functools import wraps
from mongo import User, NotUniqueError, ValidationError

from .utils import HTTPResponse, HTTPRedirect, HTTPError, Request, send_noreply

import jwt
import os

JWT_ISS = os.environ.get('JWT_ISS', 'test.test')
JWT_SECRET = os.environ.get('JWT_SECRET', 'SuperSecretString')

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
    @Request.cookies(vars_dict={'token': 'jwt'})
    def wrapper(token, *args, **kwargs):
        if token == None:
            return HTTPError('Not Logged In', 403)
        try:
            json = jwt.decode(token,
                              JWT_SECRET,
                              issuer=JWT_ISS,
                              algorithms='HS256')
        except:
            return HTTPError('Invalid Token', 403)
        user = User(json['data']['username'])
        if not user.is_valid:
            return HTTPError('Inactive User', 403)
        kwargs['user'] = user
        return func(*args, **kwargs)

    return wrapper


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
        return HTTPResponse(f'Goodbye {user.username}', cookies={'jwt': None})

    @Request.json(['username', 'password'])
    def login(username, password):
        '''Login a user.
        Returns:
            - 400 Incomplete Data
            - 403 Login Failed
        '''
        if not all([username, password]):
            return HTTPError('Incomplete Data', 400)
        user = User.login(username, password)
        if user == None:
            return HTTPError('Login Failed', 403)
        if not user.is_valid:
            return HTTPError('Invalid User', 403)
        cookies = {'jwt': user.jwt}
        return HTTPResponse('Login Success', cookies=cookies)

    methods = {'GET': logout, 'POST': login}

    return methods[request.method]()


@auth_api.route('/signup', methods=['POST'])
@Request.json(['username', 'password', 'email'])
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
    verify_link = f'https://noj.tw/email_verify/{user.jwt}'
    send_noreply([email], '[N-OJ] Varify Your Email', verify_link)
    return HTTPResponse('Signup Success')


@auth_api.route('/check/<item>', methods=['POST'])
def check(item):
    '''Checking when the user is registing.
    '''
    @Request.json(['username'])
    def check_username(username):
        if User(username).obj != None:
            return HTTPResponse('User exists.', data={'valid': 0})
        return HTTPResponse('Username can be used.', data={'valid': 1})

    @Request.json(['email'])
    def check_email(email):
        if User.get_username_by_email(email) != None:
            return HTTPResponse('Email has been used.', data={'valid': 0})
        return HTTPResponse('Email can be used.', data={'valid': 1})

    method = {'username': check_username, 'email': check_email}.get(item)
    return method() if method else HTTPError('Ivalid Checking Type', 400)


@auth_api.route('/active', methods=['POST'])
@auth_api.route('/active/<token>', methods=['GET'])
def active(token=None):
    '''Activate a user.
    '''
    @Request.json(['profile', 'agreement'])
    @Request.cookies(vars_dict={'token': 'jwt'})
    def update(profile, agreement, token):
        '''User: active: flase -> true
        '''
        if not all([type(profile) == dict, agreement]):
            return HTTPError('Invalid Data', 400)
        if agreement is not True:
            return HTTPError('Not Confirm the Agreement', 403)
        try:
            json = jwt.decode(token or '',
                              JWT_SECRET,
                              issuer=JWT_ISS,
                              algorithms='HS256')
        except:
            return HTTPError('Invalid token.', 403)
        user = User(json['data']['username'])
        if user.obj == None:
            return HTTPError('User not exists.', 400)
        try:
            user.obj.update(active=True,
                            profile={
                                'displayed_name': profile.get('displayedName'),
                                'bio': profile.get('bio'),
                            })
        except ValidationError as ve:
            return HTTPError('Failed.', 400, data=ve.to_dict())
        return HTTPResponse('User Is Now Active')

    def redir():
        '''Redirect user to active page.
        '''
        try:
            json = jwt.decode(token,
                              JWT_SECRET,
                              issuer=JWT_ISS,
                              algorithms='HS256')
        except:
            return HTTPError('Invalid Token', 403)
        return HTTPRedirect('/active', cookies={'jwt': token})

    methods = {'GET': redir, 'POST': update}
    return methods[request.method]()