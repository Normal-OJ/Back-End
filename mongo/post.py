from mongo import engine
from mongo.course import *
from datetime import datetime
from .user import *
from .utils import *
__all__ = [
    'add_post', 'add_reply', 'edit_post', 'delete_post', 'found_post',
    'found_thread'
]


def found_thread(target_thread):
    reply_thread = []
    if target_thread.reply:
        for reply in target_thread.reply:
            reply_thread.append(found_thread(reply))
    thread = {
        'id': str(target_thread.id),
        'content': target_thread.markdown,
        'author': target_thread.author.info,
        'status': target_thread.status,
        'created': target_thread.created.timestamp(),
        'updated': target_thread.updated.timestamp(),
        'reply': reply_thread
    }
    return thread


def found_post(course_obj, target_id=None):
    data = []
    for x in course_obj.posts:  #target_threads
        if (target_id is not None and str(x.thread.id) != target_id):
            continue
        post = {
            'thread': found_thread(x.thread),
            'title': x.post_name,
        }
        data.append(post)
    return data


def add_post(course, user, content, title):
    course_obj = Course(course).obj
    created_time = datetime.now()
    created_time.timestamp()
    updated_time = created_time
    new_thread = engine.PostThread(markdown=content,
                                   course_id=course_obj,
                                   author=user.obj,
                                   created=created_time,
                                   updated=updated_time)
    new_thread.save()
    new_post = engine.Post(post_name=title, thread=new_thread)
    new_post.save()
    course_obj.posts.append(new_post)
    course_obj.save()


def add_reply(target_thread, user, content):
    created_time = datetime.now()
    created_time.timestamp()
    updated_time = created_time
    new_depth = target_thread.depth + 1
    ''' not open this feature ,reply to reply'''
    if new_depth > 2:
        return 'Forbidden,you can not reply too deap (not open).'
    origin_course = target_thread.course_id
    new_thread = engine.PostThread(markdown=content,
                                   course_id=origin_course,
                                   depth=new_depth,
                                   created=created_time,
                                   updated=updated_time,
                                   author=user.obj)
    new_thread.save()
    target_thread.reply.append(new_thread)
    target_thread.save()


def edit_post(target_thread, user, content, title, permission, delete=0):
    # permission
    author = target_thread.author
    ''' Authority check (use by edit or delete) '''
    if delete == 1:  # deete
        if permission == 1 and user != author:  # teacher,ta,author can delete
            return 'Forbidden,you donˊt have enough Authority to delete it.'
        target_thread.status = 1
    else:  #  edit
        author = target_thread.author
        if user != author and permission < 4:  #only author or admin can edit
            return 'Forbidden,you donˊt have enough Authority to edit it.'
    ''' update thread '''
    updated_time = datetime.now()
    updated_time.timestamp()
    target_thread.updated = updated_time
    target_thread.markdown = content
    target_thread.save()
    ''' check it is post,true to update'''
    try:
        target_post = engine.Post.objects.get(thread=target_thread)
    except engine.DoesNotExist:
        target_post = None
    if target_post is not None:  # edit post
        target_post.post_name = title
        target_post.save()


def delete_post(target_thread, user, permission):
    content = '*Content was deleted.*'
    title = '*The Post was deleted*'
    return edit_post(target_thread, user, content, title, permission, 1)
