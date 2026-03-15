from urllib import parse
from typing import Optional
from flask import Blueprint, current_app, request
from mongo import engine
from mongo.utils import drop_none
from mongo import *
from .utils import *
from .auth import identity_verify, login_required
from .schemas import AddUserBody, UpdateUserBody, GetUserListQuery

__all__ = ['user_api']

user_api = Blueprint('user_api', __name__)


@identity_verify(0)
def check_admin(user):
    '''
    an empty wrapper to check whether client is admin
    '''
    return None


@user_api.before_request
def before_request():
    '''
    we only allow admins to call user APIs, but the CORS preflight
    request won't contain credentials, so we skip the check for that.
    '''
    if request.method.lower() == 'options':
        return None
    return check_admin()


@user_api.get('/')
@parse_query(GetUserListQuery)
def get_user_list(query: GetUserListQuery):
    offset = query.offset
    count = query.count
    course = query.course
    role = query.role
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


@user_api.get('/summary')
def get_user_summary():
    user_count = engine.User.objects.count()
    breakdown = [{
        "role": role.name.lower(),
        "count": engine.User.objects(role=role.value).count()
    } for role in engine.User.Role]
    return HTTPResponse(data={
        "userCount": user_count,
        "breakdown": breakdown,
    })


@user_api.post('/')
@parse_body(AddUserBody)
def add_user(body: AddUserBody):
    '''
    Directly add a user without activation required.
    This operation only allow admin to use.
    '''
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
    except ValueError as ve:
        return HTTPError('Not Allowed Name', 400)
    return HTTPResponse()


@user_api.patch('/<username>')
@login_required
@Request.doc('username', 'target_user', User)
@parse_body(UpdateUserBody)
def update_user(user: User, target_user: User, body: UpdateUserBody):
    # TODO: notify admin & user (by email, SMS, etc.)
    if body.password is not None:
        target_user.change_password(body.password)
        current_app.logger.info(
            'admin changed user password '
            f'[actor={user.username}, user={target_user.username}]', )
    payload = drop_none({
        'profile__displayed_name': body.displayed_name,
        'role': body.role,
    })
    if len(payload):
        fields = [*payload.keys()]
        target_user.update(**payload)
        current_app.logger.info(
            'admin changed user info '
            f'[actor={user.username}, user={target_user.username}, fields={fields}]',
        )
    return HTTPResponse()
