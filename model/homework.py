from flask import Blueprint, request
import jwt
from .auth import login_required
from mongo import User, HomeWork
from .utils import HTTPResponse, HTTPRedirect, HTTPError, Request
import os

JWT_ISS = os.environ.get('JWT_ISS')
JWT_SECRET = os.environ.get('JWT_SECRET')

__all__ = ['hw_api']

hw_api = Blueprint('hw_api', __name__)

@hw_api.route('/admin/course/<course_name>/homework', methods=['POST','PUT','DELETE'])
@Request.json('name','markdown', 'start', 'end', 'problemIds','scoreboardStatus')
@login_required
def add_hw(user,course_name, markdown, name, start, end, problemIds,scoreboardStatus=0):
    if request.method=='POST':
        try:
            homework = HomeWork.add_hw(course_name, name, start, end, problemIds,
                                       scoreboardStatus)
        except Exception as ex:
            return HTTPError(ex, 500)
        return HTTPResponse('Add homework Success', 200, 'ok', data = 
                        {'name':homework.homeworkName,
                         "start":homework.duration.start,
                         "end":homework.duration.end,
                         "problemIds":homework.problemIds})
    if request.method=='PUT':
        try:
            homework = HomeWork.update(course_name, name, start, end, problemIds,
                                       scoreboardStatus)
        except Exception as ex:
            return HTTPError(ex, 500)
        return HTTPResponse('Update homework Success', 200, 'ok',data = 
                        {'name':homework.homeworkName,
                         "start":homework.duration.start,
                         "end":homework.duration.end,
                         "problemIds":homework.problemIds})
    if request.method=='DELETE':
        try:
            homework = HomeWork.deleteProblems(course_name, name)
        except Exception as ex:
            return HTTPError(ex, 500)
        return HTTPResponse('Delete homework Success', 200, 'ok', data = 
                        {'name':homework.homeworkName,
                         "start":homework.duration.start,
                         "end":homework.duration.end,
                         "problemIds":homework.problemIds})
    

@hw_api.route('/<course_name>/homework',methods = ['GET'])
@login_required
def get_hw_in_course(user,course_name):
    try:
        homeworks = HomeWork.getHomeworks(course_name)
        data = []
        homework = {}                        
        for i in range(0,len(homeworks)):
            homework={"name":homeworks[i].homeworkName,
                         "markdown":homeworks[i].markdown,
                         "start":homeworks[i].duration.start,
                         "end":homeworks[i].duration.end,
                         "problemIds":homeworks[i].problemIds,
                         "scoreboardStatus":homeworks[i].scoreboardStatus}
            if(user.role==1):
                homework["studentStatus"] = homeworks[i].studentStatus
            data.append(homework)
    except Exception as ex:
        return HTTPError(ex, 500)
    return HTTPResponse('get homeworks', 200, 'ok',  data)

@hw_api.route('/<id>')
@login_required
def get_homework(user,id):
    try:
        homework = HomeWork.getSignalHomework(id)
    except Exception as ex:
        return HTTPError(ex, 500)
    return HTTPResponse('get homeworks', 200, 'ok', data = 
                        {"name":homework.homeworkName,
                         "start":homework.duration.start,
                         "end":homework.duration.end,
                         "problemIds":homework.problemIds})



