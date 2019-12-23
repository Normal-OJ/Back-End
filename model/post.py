from flask import Blueprint
from mongo import *
from .auth import *
from .utils import *
from mongo.post import *
from mongo.course import *

__all__ = ['post_api']

post_api = Blueprint('post_api', __name__)


@post.route('/', methods=['POST'])
@Request.json('course', 'title', 'content', 'targetPostId')
@login_required
def modify_post(user, course, title, content, targetPostId):
    permission = perm(Course(course).obj, user)
    if not permission:
        return HTTPError('You are not in this course.', 403)
    if request.method == 'POST':
        #add reply
        if course is None:
            r = add_reply(targetPostId, user, content)
        #add course post
        else:
            r = add_post(course, user, content, title)
        if r is not None:
            return HTTPError(r, 404)
