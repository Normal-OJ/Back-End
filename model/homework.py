from flask import Blueprint
from .auth import login_required
from mongo import HomeWork
from .utils import HTTPResponse, HTTPRedirect, HTTPError, Request

hw_api = Blueprint('homework_api', __name__)

@hw_api.route('/admin/course/<id>/homework/post',methods=['POST'])
@login_required
@Request.json(['name', 'start', 'end','problemIds','participants'])
def add_hw(id,name,start,end,problemIds,participants):
    try:
        homework = HomeWork.add_hw_in_course(id,name,start,end,problemIds);
    except Exception as ex:
        return HTTPError(ex,500)
    return HTTPResponse('Add homework Success',200,'ok',homework)

@hw_api.route('/admin/course/<id>/homework/update',methods=['UPDATE'])
@login_required
@Request.json(['name', 'start', 'end','problemIds','participants'])
def update_hw_in_course(id,name,start,end,problemIds,participants):
    try:
        homework = HomeWork.update_hw_in_course(id,name,start,end,problemIds);
    except Exception as ex:
        return HTTPError(ex,500)
    return HTTPResponse('Update homework Success',200,'ok',homework)

@hw_api.route('/admin/course/<id>/homework/delete',methods=['DELETE'])
@login_required
@Request.json(['name', 'start', 'end','problemIds','participants'])
def add_hw(id,name,start,end,problemIds,participants):
    try:
        homework = HomeWork.update_hw_in_course(id,name,start,end,problemIds);
    except Exception as ex:
        return HTTPError(ex,500)    
    return HTTPResponse('Delete homework Success',200,'ok',homework)