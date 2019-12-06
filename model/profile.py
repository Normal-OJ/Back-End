from flask import Blueprint, request

from mongo import User

from .utils import HTTPResponse, HTTPError, Request
from .auth import login_required

import jwt
import os

JWT_ISS = os.environ.get('JWT_ISS')
JWT_SECRET = os.environ.get('JWT_SECRET')

profile_api = Blueprint('profile_api', __name__)


@profile_api.route('/<username>', methods=['GET'])
@login_required
def view_others_profile(user, username):
    try:
        user = User(username)
        data = {
            'username': user.username,
            'email': user.obj.email,
            'displayed_name': user.obj.profile.displayed_name,
            'bio': user.obj.profile.bio
        }
    except:
        return HTTPError('Profile not exist.', 404)

    return HTTPResponse('Profile exist.', data=data)


@profile_api.route('', methods=['GET', 'POST'])
@login_required
def view_or_edit_profile(user):
    @Request.json(['displayedName', 'bio'])
    def edit_profile(displayedName, bio):
        try:
            profile = user.obj.profile

            if displayedName != None:
                profile['displayed_name'] = displayedName
            if bio != None:
                profile['bio'] = bio

            user.obj.update(profile=profile)
        except:
            return HTTPError('Upload fail.', 403)

        return HTTPResponse('Uploaded.')

    if request.method == 'GET':
        try:
            data = {
                'username': user.username,
                'email': user.obj.email,
                'displayed_name': user.obj.profile.displayed_name,
                'bio': user.obj.profile.bio
            }
        except:
            return HTTPError('Profile not exist.', 404)

        return HTTPResponse('Profile exist.', data=data)

    else:
        return view_or_edit_profile()
