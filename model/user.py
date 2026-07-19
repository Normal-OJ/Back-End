import logging
from urllib import parse
from typing import Optional
from fastapi import APIRouter, Depends
from mongo import engine
from mongo.utils import drop_none
from mongo import *
from .utils import *
from .auth import identity_verify, login_required
from .schemas import AddUserBody, UpdateUserBody, GetUserListQuery

__all__ = ['user_router', 'user_options_router']

logger = logging.getLogger(__name__)

# Handles CORS preflight (OPTIONS) without authentication, matching original Flask before_request behavior
user_options_router = APIRouter()


@user_options_router.options('/{path:path}')
@user_options_router.options('')
def _user_options_handler():
    from fastapi.responses import Response
    return Response(status_code=200)


# All user-management endpoints require admin access
user_router = APIRouter(dependencies=[identity_verify(0)])


@user_router.get('')
def get_user_list(query: GetUserListQuery = Depends()):
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
        return HTTPError('offset, count and role must be integer', 400)
    if course is not None:
        course = parse.unquote(course)

    filter_query = drop_none({'courses': course, 'role': role})
    user_list = engine.User.objects(**filter_query)
    if offset is not None:
        user_list = user_list[offset:]
    if count is not None:
        user_list = user_list[:count]

    user_list = [User(u).info for u in user_list]
    return HTTPResponse(data=user_list)


@user_router.get('/summary')
def get_user_summary():
    user_count = engine.User.objects.count()
    breakdown = [{
        "role": role.name.lower(),
        "count": engine.User.objects(role=role.value).count()
    } for role in engine.User.Role]
    return HTTPResponse(data={"userCount": user_count, "breakdown": breakdown})


@user_router.post('')
def add_user(body: AddUserBody):
    '''Directly add a user without activation required. Admin only.'''
    try:
        User.signup(body.username, body.password, body.email).activate()
    except ValidationError as ve:
        return HTTPError('Signup Failed', 400, data=ve.to_dict())
    except NotUniqueError:
        return HTTPError('User Exists', 400)
    except ValueError:
        return HTTPError('Not Allowed Name', 400)
    return HTTPResponse()


@user_router.patch('/{username}')
def update_user(
        body: UpdateUserBody,
        user: User = Depends(login_required),
        target_user: User = get_doc('username', User),
):
    if body.password is not None:
        target_user.change_password(body.password)
        logger.info('admin changed user password '
                    f'[actor={user.username}, user={target_user.username}]')
    payload = drop_none({
        'profile__displayed_name': body.displayed_name,
        'role': body.role,
    })
    if len(payload):
        fields = [*payload.keys()]
        target_user.update(**payload)
        logger.info(
            'admin changed user info '
            f'[actor={user.username}, user={target_user.username}, fields={fields}]'
        )
    return HTTPResponse()
