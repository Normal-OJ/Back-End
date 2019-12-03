from flask import Blueprint
from functools import wraps
from mongo import User, NotUniqueError, ValidationError

from .utils import HTTPResponse, HTTPError, Request, send_noreply

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
def edit_profile(user):
	@Request.json(['displayedName', 'bio'])
	def edit(displayedName = "", bio = ""):
		try:
			if displayedName != "":
				user.obj.update(profile={
					'displayed_name': displayedName,
					'bio': user.profile.get('bio')
				})
			if bio != "":
				user.obj.update(profile={
					'displayed_name': user.profile.get('displayed_name'),
					'bio': bio
				})
		except:
			return HTTPError('Upload fail.', 403)
		return HTTPResponse('Uploaded.')
	return edit
