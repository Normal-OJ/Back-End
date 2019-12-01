from flask import Blueprint

from .auth import login_required
from .utils import HTTPResponse

homework_api = Blueprint('homework_api', __name__)

@test_api.route('/admin/course/<id>/homework/post',methods=['POST'])
@login_required
def CreateHw(id):
    course = Course.get
    return HTTPResponse('test')

@test_api.route('/admin/course/<id>/homework/update',methods=['UPDATE'])
@login_required
def CreateHw(id):
    course = Course.get
    return HTTPResponse('test')

@test_api.route('/admin/course/<id>/homework/post',methods=['POST'])
@login_required
def CreateHw(id):
    course = Course.get
    return HTTPResponse('test')