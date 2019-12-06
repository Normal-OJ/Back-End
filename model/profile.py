from flask import Blueprint

from mongo import User

from .utils import HTTPResponse, HTTPError, Request
from .auth import login_required

import jwt
import os

JWT_ISS = os.environ.get('JWT_ISS')
JWT_SECRET = os.environ.get('JWT_SECRET')

profile_api = Blueprint('profile_api', __name__)


@profile_api.route('/<id>', methods=['GET'])
@login_required
def view_profile(user, id):
    """try:
	
	except:
		return HTTPError('Profile not exist.', 404)"""
    data = {
        'username': user.username,
        'email': user.obj.email,
        'displayed_name': user.obj.profile.displayed_name,
        'bio': user.obj.profile.bio
    }
    return HTTPResponse('Profile exist.', data=data)


@profile_api.route('', methods=['POST'])
@login_required
@Request.json(['displayedName', 'bio'])
def edit_profile(user, displayedName, bio):
    try:
        if displayedName != "":
            user.obj.update(profile={
                'displayed_name': displayedName,
                'bio': user.obj.profile.bio
            })
        if bio != "":
            user.obj.update(profile={
                'displayed_name': user.obj.profile.displayed_name,
                'bio': bio
            })
    except:
        return HTTPError('Upload fail.', 403)
    return HTTPResponse('Uploaded.')
