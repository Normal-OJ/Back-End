from mongo import engine
from mongo.course import *
from .user import *
from .utils import *
__all__ = ['Post', 'add_post', 'add_reply']


class Post:
    @staticmethod
    def get_all_announcement():
        return engine.announcement.object


def add_post(course, user, content, title):
    try:
        target_course = engine.Course.objects.get(course_name=course)
    except engine.DoesNotExist:
        return "Course not found."
    new_thread = engine.Post(markdown=content, author=user.obj, reply=null)
    new_post = engine.Post(post_name=title,
                           course_id=target_course,
                           thread=new_thread)
    new_post.save()


def add_reply(targetPostId, user, content):
    try:
        target_post = engine.Post.objects.get(id=targetPostId)
    except engine.DoesNotExist:
        try:
            target_post = engine.PostThread.objects.get(id=targetPostId)
        except engine.DoesNotExist:
            return "Post/reply not found."
    new_thread = engine.Post(markdown=content, author=user.obj, reply=null)
    target_post.reply.append(new_thread)
    target_post.save()
