from urllib import parse
from typing import Optional
from flask import Blueprint, current_app, request
from mongo import engine
from mongo.utils import drop_none
from mongo import *
from .utils import *
from .auth import identity_verify, login_required

__all__ = ['user_api']

user_api = Blueprint('user_api', __name__)


@user_api.get('/')
@identity_verify(0)
@Request.args('offset', 'count', 'course', 'role')
def get_user_list(
    user,
    offset: Optional[str],
    count: Optional[str],
    course: Optional[str],
    role: Optional[str],
):
    try:
        if offset is not None:
            offset = int(offset)
        if count is not None:
            count = int(count)
        if role is not None:
            role = int(role)
    except (TypeError, ValueError):
        return HTTPError(
            'offset, count and role must be integer',
            400,
        )
    if course is not None:
        course = parse.unquote(course)

    # filter
    query = drop_none({
        'courses': course,
        'role': role,
    })
    user_list = engine.User.objects(**query)
    # truncate
    if offset is not None:
        user_list = user_list[offset:]
    if count is not None:
        user_list = user_list[:count]

    user_list = [User(u).info for u in user_list]
    return HTTPResponse(data=user_list)


@user_api.post('/')
@identity_verify(0)
@Request.json('username: str', 'password: str', 'email: str')
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
    except ValueError as ve:
        return HTTPError('Not Allowed Name', 400)
    return HTTPResponse()


@user_api.patch('/<username>')
@identity_verify(0)
@Request.doc('username', 'target_user', User)
@Request.json('password', 'displayed_name', 'role')
def update_user(
    user: User,
    target_user: User,
    password,
    displayed_name,
    role,
):
    # TODO: notify admin & user (by email, SMS, etc.)
    if password is not None:
        target_user.change_password(password)
        current_app.logger.info(
            'admin changed user password '
            f'[actor={user.username}, user={target_user.username}]', )
    payload = drop_none({
        'profile__displayed_name': displayed_name,
        'role': role,
    })
    if len(payload):
        fields = [*payload.keys()]
        target_user.update(**payload)
        current_app.logger.info(
            'admin changed user info '
            f'[actor={user.username}, user={target_user.username}, fields={fields}]',
        )
    return HTTPResponse()
