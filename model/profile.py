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
	try:
		data = {
			'username': user.username,
			'email': user.email,
			'displayedName': user.profile.get('displayed_name'),
			'bio': user.profile.get('bio'),
		}
	except:
		return HTTPError('Profile not exist.', 404)
	return HTTPResponse('Profile exist.', data=data)


@profile_api.route('', methods=['POST'])
@login_required
@Request.json(['displayedName', 'bio'])
def edit_profile(user, displayedName, bio):
	if bio != "":
		user.obj.update(profile={
			'displayed_name': 'aisu_0911',
			'bio': 'hello'
		})
	"""except:
		return HTTPError('Upload fail (bio).', 403)"""
	return HTTPResponse('Uploaded.')
