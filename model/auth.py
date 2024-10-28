# Standard library
from functools import wraps
from random import SystemRandom
from typing import Optional
import csv
import io
# Related third party imports
from flask import Blueprint, request, current_app, url_for
# Local application
from mongo import *
from mongo import engine
from mongo.utils import hash_id
from .utils import *

import string

__all__ = (
    'auth_api',
    'login_required',
    'identity_verify',
    'get_verify_link',
)

auth_api = Blueprint('auth_api', __name__)

VERIFY_TEXT = '''\
Welcome! you've signed up successfully!
Enter Normal OJ to active your account via this link:
{url}
'''

VERIFY_HTML = '''\
<!DOCTYPE html><html lang="en"><head><title>template</title><meta http-equiv="Content-Type" content="text/html; charset=utf-8"><meta http-equiv="X-UA-Compatible" content="IE=edge"><meta name="viewport" content="width=device-width, initial-scale=1.0 "><meta name="format-detection" content="telephone=no"><link href="https://fonts.googleapis.com/css?family=Lato:300,400,600,700,800" rel="stylesheet"><style>.em_body {{margin: 0px;padding: 0px;background-color: #efefef;}}.em_full_wrap {{vertical-align: top;width: 100%;border-spacing: 0px;border-collapse: separate;border: 0px;background-color: #efefef;margin-left: auto; margin-right: auto;}}.em_main_table {{width: 700px;border-spacing: 0px;border-collapse: separate;align-self: center;margin-left:auto; margin-right:auto;}}.em_full_wrap td, .em_main_table td {{padding: 0px;vertical-align: top;text-align: center;}}</style></head><body class="em_body"><table class="em_full_wrap"><tbody><tr><td><table class="em_main_table"><tr><td style="padding:35px 70px 30px; background-color: #003865"><table style="width: 100%; border-spacing: 0px; border-collapse: separate; border: 0px; margin-left: auto; margin-right: auto;"><tbody><tr><td style="font-family:'Lato', Arial, sans-serif; font-size:16px; line-height:30px; color:#fff; vertical-align: top; text-align: center;">Normal Online Judge Email Verification</td></tr><tr><td><hr></td></tr><tr><td style="font-family:'Lato', Arial, sans-serif; font-size:20px; line-height:22px; color:#fff; padding:12px; vertical-align: top; text-align: center;">Welcome! you've signed up successfully!<br><br>Enter Normal OJ to active your account via this link.</td></tr><tr><td class="em_h20" style="font-size:0px; line-height:0px; height:25px;">&nbsp;</td></tr><tr><td style="vertical-align: top; text-align: center;"><form target="_blank" action="{url}"><button type="submit" style="background:#A6DAEF; border-color: #fff; border-radius: 5px; font-family:'Lato', Arial, sans-serif; font-size:16px; line-height:22px; box-shadow: 0 8px 16px 0 rgba(0,0,0,0.2), 0 6px 20px 0 rgba(0,0,0,0.19); cursor: pointer;">Active Account</button></form></td></tr></tbody></table></td></tr><tr><td style="padding:18px 30px; background-color: #f6f7f8"><table style="width: 100%; border-spacing: 0px; border-collapse: separate; border: 0px; margin-left: auto; margin-right: auto;"><tbody><tr><td style="font-family:'Lato', Arial, sans-serif; font-size:11px; line-height:18px; color:#999999; vertical-align: top; text-align: center;">© 2020 Normal Online Judge. All Rights Reserved.</td></tr></tbody></table></td></tr></table></td></tr></tbody></table></body></html>
'''


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
        if json is None or not json.get('secret'):
            return HTTPError('Invalid Token', 403)
        user = User(json['data']['username'])
        if json['data'].get('userId') != user.user_id:
            return HTTPError('Authorization Expired', 403)
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


def get_verify_link(user: User) -> str:
    return url_for(
        'auth_api.active',
        _external=True,
        token=user.cookie,
    )


@auth_api.route('/session', methods=['GET', 'POST'])
def session():
    '''Create a session or remove a session.
    Request methods:
        GET: Logout
        POST: Login
    '''

    def logout():
        '''Logout a user.
        Returns:
            - 200 Logout Success
        '''
        cookies = {'jwt': None, 'piann': None}
        return HTTPResponse('Goodbye', cookies=cookies)

    @Request.json('username: str', 'password: str')
    def login(username, password):
        '''Login a user.
        Returns:
            - 400 Incomplete Data
            - 403 Login Failed
        '''
        try:
            user = User.login(username, password, request.remote_addr)
        except DoesNotExist:
            return HTTPError('Login Failed', 403)
        if not user.active:
            return HTTPError('Invalid User', 403)
        cookies = {'piann_httponly': user.secret, 'jwt': user.cookie}
        return HTTPResponse('Login Success', cookies=cookies)

    methods = {'GET': logout, 'POST': login}

    return methods[request.method]()


@auth_api.route('/signup', methods=['POST'])
@Request.json('username: str', 'password: str', 'email: str')
def signup(username, password, email):
    try:
        user = User.signup(username, password, email)
    except ValidationError as ve:
        return HTTPError('Signup Failed', 400, data=ve.to_dict())
    except NotUniqueError:
        return HTTPError('User Exists', 400)
    except ValueError:
        return HTTPError('Not Allowed Name', 400)
    verify_link = get_verify_link(user)
    text = VERIFY_TEXT.format(url=verify_link)
    html = VERIFY_HTML.format(url=verify_link)
    send_noreply([email], '[N-OJ] Varify Your Email', text, html)
    return HTTPResponse('Signup Success')


@auth_api.route('/change-password', methods=['POST'])
@login_required
@Request.json('old_password: str', 'new_password: str')
def change_password(user, old_password, new_password):
    try:
        User.login(user.username, old_password, request.remote_addr)
    except DoesNotExist:
        return HTTPError('Wrong Password', 403)
    user.change_password(new_password)
    cookies = {'piann_httponly': user.secret}
    return HTTPResponse('Password Has Been Changed', cookies=cookies)


@auth_api.route('/check/<item>', methods=['POST'])
def check(item):
    '''Checking when the user is registing.
    '''

    @Request.json('username: str')
    def check_username(username):
        try:
            User.get_by_username(username)
        except DoesNotExist:
            return HTTPResponse('Username Can Be Used', data={'valid': 1})
        return HTTPResponse('User Exists', data={'valid': 0})

    @Request.json('email: str')
    def check_email(email):
        try:
            User.get_by_email(email)
        except DoesNotExist:
            return HTTPResponse('Email Can Be Used', data={'valid': 1})
        return HTTPResponse('Email Has Been Used', data={'valid': 0})

    method = {'username': check_username, 'email': check_email}.get(item)
    return method() if method else HTTPError('Ivalid Checking Type', 400)


@auth_api.route('/resend-email', methods=['POST'])
@Request.json('email: str')
def resend_email(email):
    try:
        user = User.get_by_email(email)
    except DoesNotExist:
        return HTTPError('User Not Exists', 400)
    if user.active:
        return HTTPError('User Has Been Actived', 400)
    verify_link = get_verify_link(user)
    send_noreply([email], '[N-OJ] Varify Your Email', verify_link)
    return HTTPResponse('Email Has Been Resent')


@auth_api.route('/active', methods=['POST'])
@auth_api.route('/active/<token>', methods=['GET'])
def active(token=None):
    '''Activate a user.
    '''

    @Request.json('profile: dict', 'agreement: bool')
    @Request.cookies(vars_dict={'token': 'piann'})
    def update(profile, agreement, token):
        '''User: active: false -> true
        '''
        if agreement is not True:
            return HTTPError('Not Confirm the Agreement', 403)
        json = jwt_decode(token)
        if json is None or not json.get('secret'):
            return HTTPError('Invalid Token.', 403)
        user = User(json['data']['username'])
        if not user:
            return HTTPError('User Not Exists', 400)
        if user.active:
            return HTTPError('User Has Been Actived', 400)
        try:
            user.activate(profile)
        except engine.DoesNotExist as e:
            return HTTPError(str(e), 404)
        cookies = {'jwt': user.cookie}
        return HTTPResponse('User Is Now Active', cookies=cookies)

    def redir():
        '''Redirect user to active page.
        '''
        json = jwt_decode(token)
        if json is None:
            return HTTPError('Invalid Token', 403)
        user = User(json['data']['username'])
        cookies = {'piann_httponly': user.secret, 'jwt': user.cookie}
        return HTTPRedirect('/email_verify', cookies=cookies)

    methods = {'GET': redir, 'POST': update}
    return methods[request.method]()


@auth_api.route('/password-recovery', methods=['POST'])
@Request.json('email: str')
def password_recovery(email):
    try:
        user = User.get_by_email(email)
    except DoesNotExist:
        return HTTPError('User Not Exists', 400)
    new_password = (lambda r: ''.join(
        r.choice(string.hexdigits)
        for i in range(r.randint(12, 24))))(SystemRandom())
    user_id2 = hash_id(user.username, new_password)
    user.update(user_id2=user_id2)
    send_noreply(
        [email], '[N-OJ] Password Recovery',
        f'Your alternative password is {new_password}.\nPlease login and change your password.'
    )
    return HTTPResponse('Recovery Email Has Been Sent')


@auth_api.route('/user', methods=['POST'])
@Request.json('username: str', 'password: str', 'email: str')
@identity_verify(0)
def add_user(
    user,
    username: str,
    password: str,
    email: str,
):
    '''
    Directly add a user without activation required.
    This operation only allow admin to use.
    '''
    try:
        User.signup(
            username,
            password,
            email,
        ).activate()
    except ValidationError as ve:
        return HTTPError('Signup Failed', 400, data=ve.to_dict())
    except NotUniqueError:
        return HTTPError('User Exists', 400)
    except ValueError:
        return HTTPError('Not Allowed Name', 400)
    return HTTPResponse()


@auth_api.route('/batch-signup', methods=['POST'])
@Request.json('new_users: str', 'course', 'force')
@Request.doc('course', 'course', Course, src_none_allowed=True)
@identity_verify(0)
def batch_signup(
    user,
    new_users: str,
    course: Optional[Course],
    force: Optional[bool],
):
    try:
        new_users = [*csv.DictReader(io.StringIO(new_users))]
    except csv.Error as e:
        current_app.logger.info(f'Error parse csv file [err={e}]')
        return HTTPError('Invalid file content', 400)
    if force is None:
        force = False
    try:
        new_users = User.batch_signup(
            new_users=new_users,
            course=course,
            force=force,
        )
    except ValueError as e:
        return HTTPError(str(e), 400)
    return HTTPResponse()


@auth_api.route('/me', methods=['GET'])
@Request.args('fields')
@login_required
def get_me(user: User, fields: Optional[str]):
    default = [
        'username',
        'email',
        'md5',
        'active',
        'role',
        'editorConfig',
        'displayedName',
        'bio',
    ]
    if fields is None:
        fields = default
    else:
        fields = fields.split(',')
    try:
        return HTTPResponse(data=user.properties(*fields))
    except ValueError as e:
        return HTTPError(str(e), 400)
