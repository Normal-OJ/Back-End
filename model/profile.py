from flask import Blueprint

from mongo import *
from .auth import *
from .utils import *

__all__ = ['profile_api']

profile_api = Blueprint('profile_api', __name__)


@profile_api.route('/', methods=['GET'])
@profile_api.route('/<username>', methods=['GET'])
@login_required
def view_others_profile(user, username=None):
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
@Request.json('bio', 'displayed_name')
def edit_profile(user, displayed_name, bio):
    try:
        profile = user.obj.profile

        if displayed_name is not None:
            profile['displayed_name'] = displayed_name
        elif displayed_name == "":
            profile['displayed_name'] = user.username
        if bio is not None:
            profile['bio'] = bio

        user.obj.update(profile=profile)
    except:
        return HTTPError('Upload fail.', 400)

    cookies = {'jwt': user.cookie}
    return HTTPResponse('Uploaded.', cookies=cookies)
