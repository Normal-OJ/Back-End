from flask import Blueprint

from .auth import login_required
from .utils import HTTPResponse

test_api = Blueprint('test_api', __name__)

@test_api.route('/')
@login_required
def test():
    return HTTPResponse('test')
