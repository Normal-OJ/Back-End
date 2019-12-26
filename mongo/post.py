from mongo import engine
from mongo.course import *
from datetime import datetime
from .user import *
from .utils import *
__all__ = [
    'Post', 'add_post', 'add_reply', 'edit_post', 'delete_post', 'found_post',
    'found_reply'
]


class Post:
    @staticmethod
    def get_all_announcement():
        return engine.announcement.object


def found_reply(target_thread):  #recursive
    all_data = []
    for x in target_thread.reply:
        all_data.append(found_reply(x))
    if target_thread.depth == 0:
        return all_data
    thread_data = {
        "id": str(target_thread.id),
        "content": target_thread.markdown,
        "author": target_thread.author.username,
        "created": target_thread.created.timestamp(),
        "updated": target_thread.updated.timestamp()
    }
    all_data.append(thread_data)
    ''' Only two layer to use '''
    if len(all_data) == 1:
        return thread_data
    ''' Only two layer to use '''
    return all_data


def found_post(course_obj):
    data = []
    for x in course_obj.post_ids:  #target_threads
        x_thread = x.thread
        thread = {
            "title": x.post_name,
            "id": str(x_thread.id),
            "content": x_thread.markdown,
            "author": x_thread.author.username,
            "created": x_thread.created.timestamp(),
            "updated": x_thread.updated.timestamp()
        }
        data.append(thread)
        replys = found_reply(x_thread)
        if replys:
            data.append(replys)
    return data


def add_post(course, user, content, title):
    course_obj = Course(course).obj
    created_time = datetime.utcnow()  # local time use utc
    created_time.timestamp()
    updated_time = created_time
    new_thread = engine.PostThread(markdown=content,
                                   course_id=course_obj,
                                   author=user.obj,
                                   created=created_time,
                                   updated=updated_time,
                                   reply=list())
    new_thread.save()
    new_post = engine.Post(post_name=title, thread=new_thread)
    new_post.save()
    course_obj.post_ids.append(new_post)
    course_obj.save()


def add_reply(target_thread, user, content):
    created_time = datetime.utcnow()  #  time use utc
    created_time.timestamp()
    updated_time = created_time
    new_depth = target_thread.depth + 1
    ''' not open this feature ,reply to reply'''
    if new_depth >= 2:
        return "Forbidden,you can not reply to reply (not open)."
    origin_course = target_thread.course_id
    new_thread = engine.PostThread(markdown=content,
                                   course_id=origin_course,
                                   depth=new_depth,
                                   created=created_time,
                                   updated=updated_time,
                                   author=user.obj,
                                   reply=list())
    new_thread.save()
    target_thread.reply.append(new_thread)
    target_thread.save()


def edit_post(target_thread, user, content, title, permission):
    # permission
    author = target_thread.author
    if permission == 0 or (permission == 1
                           and user != author):  #if is student and not author
        return "Forbidden,you donˊt have enough Authority to edit/delete it."
    try:
        target_post = engine.Post.objects.get(thread=target_thread)
    except engine.DoesNotExist:
        target_post = None
    updated_time = datetime.now()  # local time use utc
    updated_time.timestamp()
    target_thread.updated = updated_time
    target_thread.markdown = content
    target_thread.save()
    if target_post is not None:  # edit post
        target_post.post_name = title
        target_post.save()


def delete_post(target_thread, user, permission):
    content = "Content is deleted."
    title = "The Post is deleted."
    return edit_post(target_thread, user, content, title, permission)
