from mongo import engine
from mongo.course import *
from datetime import datetime
from .user import *
from .utils import *
__all__ = ['Announcement','found_announcement','add_announcement','edit_announcement','delete_announcement']

class Announcement:
    @staticmethod
    def get_all_announcement():
        return engine.announcement.object

def found_announcement(course):
    try:
        target_course = engine.Course.objects.get(course_name=course)
    except:
        raise FileNotFoundError
    try:
        target = engine.Announcement.objects.get(course_id=target_course.id)
    except:
        raise FileNotFoundError
    return target

def add_announcement(user,course,title,content):# course=course_id
    try:
        target_course = engine.Course.objects.get(course_name=course)
    except:
        return "Course not found."
    created_time = datetime.now() # local time use utc+8
    created_time.timestamp()
    updated_time = created_time
    new_announcement = engine.Announcement(announcement_name=title,
                        course_id=target_course,
                        author=user,
                        created=created_time,
                        updated=updated_time,
                        markdown=content)
    new_announcement.save()

def edit_announcement(user,course,title,content,targetAnnouncementId):
    try:
        target = engine.Announcement.objects.get(id=targetAnnouncementId)
    except:
        return "Announcement not found."
    #if user.username != target.author:
    #    return "Forbidden, Only author can edit."
    # DBRef bug #
    target.announcement_name = title
    target.markdown = content
    updated_time = datetime.now()
    updated_time.timestamp()
    target.updated = updated_time
    target.save()

def delete_announcement(user,targetAnnouncementId):
    try:
        target = engine.Announcement.objects.get(id=targetAnnouncementId)
    except:
        return "Announcement not found."
    #if user.username != target.author:
    #    return "Forbidden, Only author can delete."
    # DBRef bug #
    target.delete()
