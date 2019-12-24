from mongo import engine
from mongo.course import *
from .user import *
from .utils import *
__all__ = ['Post', 'add_post', 'add_reply','edit_post','delete_post']


class Post:
    @staticmethod
    def get_all_announcement():
        return engine.announcement.object


def add_post(course, user, content, title):
    try:
        target_course = engine.Course.objects.get(course_name=course)
    except engine.DoesNotExist:
        return "Course not found."
    new_thread = engine.PostThread(markdown=content,course_id=target_course, author=user.obj, reply=null)
    new_post = engine.Post(post_name=title,
                           thread=new_thread)
    new_post.save()


def add_reply(targetThreadId, user, content):
    try:
        target_thread = engine.PostThread.objects.get(id=targetThreadId)
    except engine.DoesNotExist:
        return "Post/reply not found."
    origin_course = target_thread.course_id
    new_thread = engine.PostThread(markdown=content,course_id=origin_course, author=user.obj, reply=null)
    target_post.reply.append(new_thread)
    target_post.save()

def edit_post(targetThreadId, user, content, title):
    try:
        target_thread = engine.PostThread.objects.get(id=targetThreadId)
    except engine.DoesNotExist:
        return "Post/reply not found."
    origin_course = target_thread.course_id
    author = target_thread.author
    permission = perm(origin_course,user)
    if permission <= 1 and user != author:
        return "Forbidden"
    target_post = None
    try:
        target_post = engine.Post.objects.get(thread=target_thread)
    target_thread.markdown = content
    target_thread.save()
    if target_post is not None: # edit post
        target_post.post_name = title
        target_post.save()
def delete_post(targetThreadId, user):
    content = "Content is deleted."
    title = "The Post is deleted."
    edit_post(targetThreadId,user,content,title)
