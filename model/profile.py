from flask import Blueprint

from mongo import *
from .auth import *
from .utils import *

__all__ = ['profile_api']

profile_api = Blueprint('profile_api', __name__)


@profile_api.route('/', methods=['GET'])
@profile_api.route('/<username>', methods=['GET'])
@login_required
def view_profile(user, username=None):
    try:
        user = user if username is None else User(username)
        data = {
            'username': user.username,
            'email': user.obj.email,
            'displayedName': user.obj.profile.displayed_name,
            'bio': user.obj.profile.bio
        }
    except:
        return HTTPError('Profile not exist.', 404)

    return HTTPResponse('Profile exist.', data=data)


@profile_api.route('/', methods=['POST'])
@login_required
@Request.json('bio', vars_dict={'displayed_name': 'displayedName'})
def edit_profile(user, displayed_name, bio):
    try:
        profile = user.obj.profile or {}

        if displayed_name is not None:
            profile[
                'displayed_name'] = displayed_name if displayed_name != "" else user.username
        if bio is not None:
            profile['bio'] = bio

        user.obj.update(profile=profile)
    except:
        return HTTPError('Upload fail.', 400)

    cookies = {'jwt': user.cookie}
    return HTTPResponse('Uploaded.', cookies=cookies)


@profile_api.route('/config', methods=['PUT'])
@login_required
@Request.json('font_size', 'theme', 'indent_type', 'tab_size', 'language')
def edit_config(user, font_size, theme, indent_type, tab_size, language):
    try:
        config = {
            'font_size': font_size,
            'theme': theme,
            'indent_type': indent_type,
            'tab_size': tab_size,
            'language': language
        }

        user.obj.update(editor_config=config)
    except ValidationError as ve:
        return HTTPError('Update fail.', 400, data=ve.to_dict())

    user.reload()
    cookies = {'jwt': user.cookie}
    return HTTPResponse('Uploaded.', cookies=cookies)
