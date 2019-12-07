from flask import Blueprint
import jwt
from .auth import login_required
from mongo import HomeWork,User
from .utils import HTTPResponse, HTTPRedirect, HTTPError, Request
import os

JWT_ISS = os.environ.get('JWT_ISS')
JWT_SECRET = os.environ.get('JWT_SECRET')
hw_api = Blueprint('homework_api', __name__)

@hw_api.route('/admin/course/<id>/homework/post',methods=['POST'])
@login_required
@identity_verify
@Request.json(['name', 'start', 'end','problemIds','participants'])
def add_hw(id,name,start,end,problemIds,participants):
    try:
        homework = HomeWork.add_hw_in_course(id,name,start,end,problemIds);
    except Exception as ex:
        return HTTPError(ex,500)
    return HTTPResponse('Add homework Success',200,'ok',homework)

@hw_api.route('/admin/course/<id>/homework/update',methods=['UPDATE'])
@login_required
@identity_verify
@Request.json(['name', 'start', 'end','problemIds','participants'])
def update_hw_in_course(id,name,start,end,problemIds,participants):
    try:
        homework = HomeWork.update_hw_in_course(id,name,start,end,problemIds);
    except Exception as ex:
        return HTTPError(ex,500)
    return HTTPResponse('Update homework Success',200,'ok',homework)

@hw_api.route('/admin/course/<id>/homework/delete',methods=['DELETE'])
@login_required
@identity_verify
@Request.json(['name', 'start', 'end','problemIds','participants'])
def delete_hw(id,name,start,end,problemIds,participants):
    try:
        homework = HomeWork.delete_hw_in_course(id,name,start,end,problemIds);
    except Exception as ex:
        return HTTPError(ex,500)    
    return HTTPResponse('Delete homework Success',200,'ok',homework)

def identity_verify(func):
    #use to verify user role , if user role is not admin return 403

    @Request.cookies(vars_dict={'token': 'jwt'})
    def wrapper(token, *args, **kwargs):
            json = jwt.decode(token, JWT_SECRET, issuer=JWT_ISS)
            user = User.objects(username = json['data']['username']).first()
            if(user.role!=0):
                return HTTPError('Inactive User', 403)
            return func(*args, **kwargs)
    return  wrapper
