from flask import Blueprint, request
import jwt
from .auth import login_required
from mongo import User, HomeWork
from .utils import HTTPResponse, HTTPRedirect, HTTPError, Request
import os

JWT_ISS = os.environ.get('JWT_ISS')
JWT_SECRET = os.environ.get('JWT_SECRET')
hw_api = Blueprint('hw_api', __name__)

@hw_api.route('/admin/course/<course_name>/homework', methods=['POST','PUT','DELETE'])
@Request.json(['name', 'start', 'end', 'problemIds', 'participants'])
@login_required
def add_hw(user,course_name, name, start, end, problemIds, participants):
    if request.method=='POST':
        try:
            homework = HomeWork.add_hw(course_name, name, start, end, problemIds,
            participants)
        except Exception as ex:
            return HTTPError(ex, 500)
        return HTTPResponse('Add homework Success', 200, 'ok', homework)
    if request.method=='PUT':
        try:
            homework = HomeWork.update(course_name, name, start, end, problemIds,
            participants)
        except Exception as ex:
            return HTTPError(ex, 500)
        return HTTPResponse('Update homework Success', 200, 'ok', homework)
    if request.method=='DELETE':
        try:
            homework = HomeWork.delete_problems(course_name, name, start, end,problemIds)
        except Exception as ex:
            return HTTPError(ex, 500)
        return HTTPResponse('Delete homework Success', 200, 'ok', homework)
    
    
    
    


# @hw_api.route('/admin/course/<course_name>/homework/update',
#               methods=['PUT'])
# @login_required
# @identity_verify
# @Request.json(['name', 'start', 'end', 'problemIds', 'participants'])
# def update_hw_in_course(course_name, name, start, end, problemIds,
#                         participants):
#     try:
#         homework = HomeWork.update(course_name, name, start, end, problemIds,
#                                    participants)
#     except Exception as ex:
#         return HTTPError(ex, 500)
#     return HTTPResponse('Update homework Success', 200, 'ok', homework)


# @hw_api.route('/admin/course/<course_name>/homework/delete',
#               methods=['DELETE'])
# @login_required
# @identity_verify
# @Request.json(['name', 'start', 'end', 'problemIds', 'participants'])
# def delete_problems_in_hw(course_name, name, start, end, problemIds,
#                           participants):
#     try:
#         homework = HomeWork.delete_problems(course_name, name, start, end,
#                                             problemIds)
#     except Exception as ex:
#         return HTTPError(ex, 500)
#     return HTTPResponse('Delete homework Success', 200, 'ok', homework)

@hw_api.route('/<course_name>/homework',methods = ['GET'])
@login_required
def get_hw_in_course(user,course_name):
    try:
        homeworks = HomeWork.get_homeworks(course_name)
    except Exception as ex:
        return HTTPError(ex, 500)
    return HTTPResponse('get homeworks', 200, 'ok', homeworks)

@hw_api.route('/<id>')
@login_required
def get_homework(user,id):
    try:
        homework = HomeWork.get_signal_homework(id)
    except Exception as ex:
        return HTTPError(ex, 500)
    return HTTPResponse('get homeworks', 200, 'ok', homework)


@hw_api.route('/<id>/test',methods = ['GET'])
@Request.json(['name'])
def test(id,name):
    try:
        a=[]
        a.append(id)
        a.append(name)
    except Exception as ex:
        return HTTPError(ex, 500)
    return HTTPResponse('get homeworks', 200, 'ok', a)



