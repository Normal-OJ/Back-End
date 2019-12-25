from mongo import engine
from mongo.course import *
from .user import *
from .utils import *
__all__ = ['Post', 'add_post', 'add_reply', 'edit_post', 'delete_post']


class Post:
    @staticmethod
    def get_all_announcement():
        return engine.announcement.object


def add_post(course, user, content, title):
    new_thread = engine.PostThread(markdown=content,
                                   course_id=target_course,
                                   author=user.obj,
                                   reply=list())
    new_thread.save()
    new_post = engine.Post(post_name=title, thread=new_thread)
    new_post.save()


def add_reply(target_thread, user, content):
    origin_course = target_thread.course_id
    new_thread = engine.PostThread(markdown=content,
                                   course_id=origin_course,
                                   author=user.obj)
    new_thread.save()
    target_thread.reply.append(new_thread)
    target_thread.save()


def edit_post(target_thread, user, content, title, permission):
    # permission
    author = target_thread.author
    if permission == 0 or (permission == 1
                           and user != author):  #if is student and not author
        return "Forbidden"
    try:
        target_post = engine.Post.objects.get(thread=target_thread)
    except engine.DoesNotExist:
        target_post = None
    target_thread.markdown = content
    target_thread.save()
    if target_post is not None:  # edit post
        target_post.post_name = title
        target_post.save()


def delete_post(target_thread, user, permission):
    content = "Content is deleted."
    title = "The Post is deleted."
    edit_post(target_thread, user, content, title, permission)
