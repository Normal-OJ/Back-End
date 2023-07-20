from mongo import engine
from mongo.course import *
from datetime import datetime
from .user import *
from .utils import *

__all__ = ['Post']


class Post():

    @classmethod
    def found_thread(cls, target_thread):
        reply_thread = []
        if target_thread.reply:
            for reply in target_thread.reply:
                reply_thread.append(Post.found_thread(reply))
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

    @classmethod
    def found_post(cls, course_obj, target_id=None):
        data = []
        for x in course_obj.posts:  # target_threads
            if (target_id is not None and str(x.thread.id) != target_id):
                continue
            post = {
                'thread': Post.found_thread(x.thread),
                'title': x.post_name,
            }
            data.append(post)
        return data

    @classmethod
    def add_post(cls, course, user, content, title):
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

    @classmethod
    def add_reply(cls, target_thread, user, content):
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

    @classmethod
    def edit_post(cls,
                  target_thread,
                  user,
                  content,
                  title,
                  capability,
                  delete=0):
        # permission
        author = target_thread.author
        # Permission check (use by edit or delete)
        if delete == 1:  # delete
            # teacher, ta, author can delete
            if user != author and not (capability & Course.Permission.GRADE):
                return 'Forbidden, you don\'t have enough permission to delete it.'
            target_thread.status = 1
        else:  #  edit
            # only author or admin can edit
            if user != author and not (capability & Course.Permission.MODIFY):
                return 'Forbidden, you don\'t have enough permission to edit it.'
        # update thread
        updated_time = datetime.now()
        updated_time.timestamp()
        target_thread.updated = updated_time
        target_thread.markdown = content
        target_thread.save()
        # check it is post, true to update
        try:
            target_post = engine.Post.objects.get(thread=target_thread)
        except engine.DoesNotExist:
            target_post = None
        if target_post is not None:  # edit post
            target_post.post_name = title
            target_post.save()

    @classmethod
    def delete_post(cls, target_thread, user, capability):
        content = '*Content was deleted.*'
        title = '*The Post was deleted*'
        return Post.edit_post(target_thread, user, content, title, capability,
                              1)
