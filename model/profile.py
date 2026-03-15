from flask import Blueprint

from mongo import *
from .auth import *
from .utils import *
from .schemas import EditProfileBody, EditConfigBody

__all__ = ['profile_api']

profile_api = Blueprint('profile_api', __name__)


@profile_api.route('/', methods=['GET'])
@profile_api.route('/<username>', methods=['GET'])
@login_required
def view_profile(user, username=None):
    user = user if username is None else User(username)
    if not user:
        return HTTPError('Profile not exist.', 404)

    data = {
        'email': user.obj.email,
        'displayedName': user.obj.profile.displayed_name,
        'bio': user.obj.profile.bio
    }
    data.update(user.info)

    return HTTPResponse('Profile exist.', data=data)


@profile_api.post('/')
@login_required
@parse_body(EditProfileBody)
def edit_profile(user, body: EditProfileBody):
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


@profile_api.put('/config')
@login_required
@parse_body(EditConfigBody)
def edit_config(user, body: EditConfigBody):
    try:
        config = {
            'font_size': body.font_size,
            'theme': body.theme,
            'indent_type': body.indent_type,
            'tab_size': body.tab_size,
            'language': body.language
        }
        user.obj.update(editor_config=config)
    except ValidationError as ve:
        return HTTPError('Update fail.', 400, data=ve.to_dict())
    user.reload()
    cookies = {'jwt': user.cookie}
    return HTTPResponse('Uploaded.', cookies=cookies)
