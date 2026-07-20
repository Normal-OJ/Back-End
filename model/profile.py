from fastapi import APIRouter, Depends
from typing import Optional

from mongo import *
from .auth import login_required
from .utils import *
from .schemas import EditProfileBody, EditConfigBody

__all__ = ['profile_router']

profile_router = APIRouter()


@profile_router.get('')
@profile_router.get('/{username}')
def view_profile(user=Depends(login_required), username: Optional[str] = None):
    user = user if username is None else User(username)
    if not user:
        return HTTPError('Profile not exist.', 404)

    data = {
        'email': user.obj.email,
        'displayedName': user.obj.profile.displayed_name,
        'bio': user.obj.profile.bio,
    }
    data.update(user.info)

    return HTTPResponse('Profile exist.', data=data)


@profile_router.post('')
def edit_profile(body: EditProfileBody, user=Depends(login_required)):
    profile = user.obj.profile or {}
    displayed_name = body.displayed_name
    bio = body.bio

    if displayed_name is not None:
        profile[
            'displayed_name'] = displayed_name if displayed_name != "" else user.username
    if bio is not None:
        profile['bio'] = bio

    user.obj.update(profile=profile)

    cookies = {'jwt': user.cookie}
    return HTTPResponse('Uploaded.', cookies=cookies)


@profile_router.put('/config')
def edit_config(body: EditConfigBody, user=Depends(login_required)):
    try:
        config = {
            'font_size': body.font_size,
            'theme': body.theme,
            'indent_type': body.indent_type,
            'tab_size': body.tab_size,
            'language': body.language,
        }
        user.obj.update(editor_config=config)
    except ValidationError as ve:
        return HTTPError('Update fail.', 400, data=ve.to_dict())
    user.reload()
    cookies = {'jwt': user.cookie}
    return HTTPResponse('Uploaded.', cookies=cookies)
