from mongo import engine
from mongo.course import *
from datetime import datetime
from .user import *
from .utils import *
__all__ = [
    'Announcement', 'found_announcement', 'add_announcement',
    'edit_announcement', 'delete_announcement'
]


class Announcement:
    @staticmethod
    def get_all_announcement():
        return engine.announcement.object


def found_announcement(course):
    try:
        target_course = engine.Course.objects.get(course_name=course)
    except FileNotFoundError as e:
        raise FileNotFoundError
    except FileExistsError:
        raise FileExistsError
    except engine.DoesNotExist:
        raise engine.DoesNotExist
    course_id = str(target_course.id)
    try:
        target = engine.Announcement.objects(course_id=course_id)
    except FileNotFoundError as e:
        raise FileNotFoundError
    return target


def add_announcement(user, course, title, content):  # course=course_id
    try:
        target_course = engine.Course.objects.get(course_name=course)
    except FileNotFoundError:
        return "Course not found."
    except FileExistsError:
        return "Course not found."
    except engine.DoesNotExist:
        return "Course not found."
    created_time = datetime.now()  # local time use utc+8
    created_time.timestamp()
    updated_time = created_time
    new_announcement = engine.Announcement(announcement_name=title,
                                           course_id=target_course,
                                           author=user.obj,
                                           created=created_time,
                                           updated=updated_time,
                                           markdown=content)
    new_announcement.save()


def edit_announcement(user, course, title, content, targetAnnouncementId):
    try:
        target = engine.Announcement.objects.get(id=targetAnnouncementId)
    except FileNotFoundError:
        return "Announcement not found."
    except FileExistsError:
        return "Announcement not found."
    except engine.DoesNotExist:
        return "Announcement not found."
    if user.username != target.author.username:
        return "Forbidden, Only author can edit."
    updated_time = datetime.now()
    updated_time.timestamp()
    target.announcement_name = title
    target.markdown = content
    target.updated = updated_time
    target.save()


def delete_announcement(user, targetAnnouncementId):
    try:
        target = engine.Announcement.objects.get(id=targetAnnouncementId)
    except FileNotFoundError:
        return "Announcement not found."
    except FileExistsError:
        return "Announcement not found."
    except engine.DoesNotExist:
        return "Announcement not found."
    if user.username != target.author.username:
        return "Forbidden, Only author can delete."
    target.delete()
