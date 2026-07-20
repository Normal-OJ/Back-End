# Standard library
from random import SystemRandom
from typing import Optional
import csv
import io
import logging
# Related third party imports
from fastapi import APIRouter, Cookie, Depends, Request
from .utils.request import get_ip
# Local application
from mongo import *
from mongo import engine
from mongo.utils import hash_id
from .utils import *
from .schemas import (
    LoginBody,
    SignupBody,
    ChangePasswordBody,
    CheckUsernameBody,
    CheckEmailBody,
    ResendEmailBody,
    ActivateUserBody,
    PasswordRecoveryBody,
    AuthAddUserBody,
    BatchSignupBody,
    GetMeQuery,
)

import string

__all__ = (
    'auth_router',
    'login_required',
    'identity_verify',
    'get_verify_link',
)

logger = logging.getLogger(__name__)

auth_router = APIRouter()

VERIFY_TEXT = '''\
Welcome! you've signed up successfully!
Enter Normal OJ to active your account via this link:
{url}
'''

VERIFY_HTML = '''\
<!DOCTYPE html><html lang="en"><head><title>template</title><meta http-equiv="Content-Type" content="text/html; charset=utf-8"><meta http-equiv="X-UA-Compatible" content="IE=edge"><meta name="viewport" content="width=device-width, initial-scale=1.0 "><meta name="format-detection" content="telephone=no"><link href="https://fonts.googleapis.com/css?family=Lato:300,400,600,700,800" rel="stylesheet"><style>.em_body {{margin: 0px;padding: 0px;background-color: #efefef;}}.em_full_wrap {{vertical-align: top;width: 100%;border-spacing: 0px;border-collapse: separate;border: 0px;background-color: #efefef;margin-left: auto; margin-right: auto;}}.em_main_table {{width: 700px;border-spacing: 0px;border-collapse: separate;align-self: center;margin-left:auto; margin-right:auto;}}.em_full_wrap td, .em_main_table td {{padding: 0px;vertical-align: top;text-align: center;}}</style></head><body class="em_body"><table class="em_full_wrap"><tbody><tr><td><table class="em_main_table"><tr><td style="padding:35px 70px 30px; background-color: #003865"><table style="width: 100%; border-spacing: 0px; border-collapse: separate; border: 0px; margin-left: auto; margin-right: auto;"><tbody><tr><td style="font-family:'Lato', Arial, sans-serif; font-size:16px; line-height:30px; color:#fff; vertical-align: top; text-align: center;">Normal Online Judge Email Verification</td></tr><tr><td><hr></td></tr><tr><td style="font-family:'Lato', Arial, sans-serif; font-size:20px; line-height:22px; color:#fff; padding:12px; vertical-align: top; text-align: center;">Welcome! you've signed up successfully!<br><br>Enter Normal OJ to active your account via this link.</td></tr><tr><td class="em_h20" style="font-size:0px; line-height:0px; height:25px;">&nbsp;</td></tr><tr><td style="vertical-align: top; text-align: center;"><form target="_blank" action="{url}"><button type="submit" style="background:#A6DAEF; border-color: #fff; border-radius: 5px; font-family:'Lato', Arial, sans-serif; font-size:16px; line-height:22px; box-shadow: 0 8px 16px 0 rgba(0,0,0,0.2), 0 6px 20px 0 rgba(0,0,0,0.19); cursor: pointer;">Active Account</button></form></td></tr></tbody></table></td></tr><tr><td style="padding:18px 30px; background-color: #f6f7f8"><table style="width: 100%; border-spacing: 0px; border-collapse: separate; border: 0px; margin-left: auto; margin-right: auto;"><tbody><tr><td style="font-family:'Lato', Arial, sans-serif; font-size:11px; line-height:18px; color:#999999; vertical-align: top; text-align: center;">© 2020 Normal Online Judge. All Rights Reserved.</td></tr></tbody></table></td></tr></table></td></tr></tbody></table></body></html>
'''


def login_required(piann: str | None = Cookie(default=None)) -> User:
    '''Check if the user is logged in.

    Raises:
        - 403 Not Logged In
        - 403 Invalid Token
        - 403 Authorization Expired
        - 403 Inactive User
    '''
    if piann is None:
        raise NOJException('Not Logged In', 403)
    json = jwt_decode(piann)
    if json is None or not json.get('secret'):
        raise NOJException('Invalid Token', 403)
    user = User(json['data']['username'])
    if json['data'].get('userId') != user.user_id:
        raise NOJException('Authorization Expired', 403)
    if not user.active:
        raise NOJException('Inactive User', 403)
    return user


def identity_verify(*roles):
    '''Verify a logged-in user's identity against allowed roles.'''

    def dependency(user: User = Depends(login_required)) -> User:
        if user.role not in roles:
            raise NOJException('Insufficient Permissions', 403)
        return user

    return Depends(dependency)


def get_verify_link(user: User, request: Request) -> str:
    return str(request.url_for('active_redirect', token=user.cookie))


@auth_router.get('/session')
def logout():
    '''Logout a user.'''
    cookies = {'jwt': None, 'piann': None}
    return HTTPResponse('Goodbye', cookies=cookies)


@auth_router.post('/session')
def login(body: LoginBody, ip_addr: str = Depends(get_ip)):
    '''Login a user.'''
    try:
        user = User.login(body.username, body.password, ip_addr)
    except DoesNotExist:
        return HTTPError('Login Failed', 403)
    if not user.active:
        return HTTPError('Invalid User', 403)
    cookies = {'piann_httponly': user.secret, 'jwt': user.cookie}
    return HTTPResponse('Login Success', cookies=cookies)


@auth_router.post('/signup')
def signup(body: SignupBody, request: Request):
    try:
        user = User.signup(body.username, body.password, body.email)
    except ValidationError as ve:
        return HTTPError('Signup Failed', 400, data=ve.to_dict())
    except NotUniqueError:
        return HTTPError('User Exists', 400)
    except ValueError:
        return HTTPError('Not Allowed Name', 400)
    verify_link = get_verify_link(user, request)
    text = VERIFY_TEXT.format(url=verify_link)
    html = VERIFY_HTML.format(url=verify_link)
    send_noreply([body.email], '[N-OJ] Varify Your Email', text, html)
    return HTTPResponse('Signup Success')


@auth_router.post('/change-password')
def change_password(
        body: ChangePasswordBody,
        user: User = Depends(login_required),
        ip_addr: str = Depends(get_ip),
):
    try:
        User.login(user.username, body.old_password, ip_addr)
    except DoesNotExist:
        return HTTPError('Wrong Password', 403)
    user.change_password(body.new_password)
    cookies = {'piann_httponly': user.secret}
    return HTTPResponse('Password Has Been Changed', cookies=cookies)


@auth_router.post('/check/username')
def check_username(body: CheckUsernameBody):
    try:
        User.get_by_username(body.username)
    except DoesNotExist:
        return HTTPResponse('Username Can Be Used', data={'valid': 1})
    return HTTPResponse('User Exists', data={'valid': 0})


@auth_router.post('/check/email')
def check_email(body: CheckEmailBody):
    try:
        User.get_by_email(body.email)
    except DoesNotExist:
        return HTTPResponse('Email Can Be Used', data={'valid': 1})
    return HTTPResponse('Email Has Been Used', data={'valid': 0})


@auth_router.post('/check/{item}')
def check_invalid(item: str):
    return HTTPError('Ivalid Checking Type', 400)


@auth_router.post('/resend-email')
def resend_email(body: ResendEmailBody, request: Request):
    try:
        user = User.get_by_email(body.email)
    except DoesNotExist:
        return HTTPError('User Not Exists', 400)
    if user.active:
        return HTTPError('User Has Been Actived', 400)
    verify_link = get_verify_link(user, request)
    send_noreply([body.email], '[N-OJ] Varify Your Email', verify_link)
    return HTTPResponse('Email Has Been Resent')


@auth_router.get('/active/{token}', name='active_redirect')
def active_redirect(token: str):
    '''Redirect user to active page.'''
    json = jwt_decode(token)
    if json is None:
        return HTTPError('Invalid Token', 403)
    user = User(json['data']['username'])
    cookies = {'piann_httponly': user.secret, 'jwt': user.cookie}
    return HTTPRedirect('/email_verify', cookies=cookies)


@auth_router.post('/active')
def activate_user(
        body: ActivateUserBody,
        piann: str | None = Cookie(default=None),
):
    '''User: active: false -> true'''
    if body.agreement is not True:
        return HTTPError('Not Confirm the Agreement', 403)
    json = jwt_decode(piann)
    if json is None or not json.get('secret'):
        return HTTPError('Invalid Token.', 403)
    user = User(json['data']['username'])
    if not user:
        return HTTPError('User Not Exists', 400)
    if user.active:
        return HTTPError('User Has Been Actived', 400)
    try:
        user.activate(body.profile)
    except engine.DoesNotExist as e:
        return HTTPError(str(e), 404)
    cookies = {'jwt': user.cookie}
    return HTTPResponse('User Is Now Active', cookies=cookies)


@auth_router.post('/password-recovery')
def password_recovery(body: PasswordRecoveryBody):
    email = body.email
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


@auth_router.post('/user')
def add_user(
        body: AuthAddUserBody,
        user: User = identity_verify(0),
):
    '''Directly add a user without activation. Admin only.'''
    try:
        User.signup(
            body.username,
            body.password,
            body.email,
        ).activate()
    except ValidationError as ve:
        return HTTPError('Signup Failed', 400, data=ve.to_dict())
    except NotUniqueError:
        return HTTPError('User Exists', 400)
    except ValueError:
        return HTTPError('Not Allowed Name', 400)
    return HTTPResponse()


@auth_router.post('/batch-signup')
def batch_signup(
        body: BatchSignupBody,
        user: User = identity_verify(0),
):
    course = None
    if body.course is not None:
        try:
            course = Course(body.course)
            if not course:
                return HTTPError(f'Course not found', 404)
        except engine.DoesNotExist as e:
            return HTTPError(str(e), 404)
    try:
        new_users = [*csv.DictReader(io.StringIO(body.new_users))]
    except csv.Error as e:
        logger.info(f'Error parse csv file [err={e}]')
        return HTTPError('Invalid file content', 400)
    force = body.force if body.force is not None else False
    try:
        new_users = User.batch_signup(
            new_users=new_users,
            course=course,
            force=force,
        )
    except ValueError as e:
        return HTTPError(str(e), 400)
    return HTTPResponse()


@auth_router.get('/me')
def get_me(
        query: GetMeQuery = Depends(),
        user: User = Depends(login_required),
):
    fields = query.fields
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
