from mongo import engine
from datetime import datetime
from .user import *
from .utils import *
__all__ = ['Announcement']

class Announcement:
    @staticmethod
    def get_all_announcement():
        return engine.announcement.object
    @staticmethod
    def get_announcement(course):
        #target = get_obj(engineAnnouncement, course_id=courseId)
        target = Announcement.objects(course_id=course)
        if target == None:
            return "Announcement not found"
        return target
    @staticmethod
    def add_announcement(user,course,title,content):# course=course_id
        target = User(user).obj
        if target is None:
            return "User not found."
        created_time = timestamp_now() # local time use utc+8
        updated_time = created_time
        new_announcement = engine.Announcement(announcement_name=title,
                            course_id=course,
                            author=user,
                            created=created_time,
                            updated=updated_time,
                            markdown=content)
        new_announcement.save()
    @staticmethod
    def edit_announcement(course,title,content):
        courseExist = get_obj(engine.Course, course_name=course)
        if courseExist == None:
            return "Course not found."
        target = engine.Announcement.objects.get(course_id=course)
        target.announcement_name = title
        target.markdown = content
        target.update = timestamp_now()
        target.save()
    @staticmethod
    def delete_announcement(course):
        courseExist = get_obj(engine.Course, course_name=course)
        if courseExist == None:
            return "Course not found."
        target = engine.Announcement.objects.get(course_id=course)
        target.delete()
