from mongo import engine
from datetime import datetime
__all__ = ['Announcement']

class Announcement:

    def get_all_announcement():
        return engine.announcement.object

    def get_announcement(course):
        #target = get_obj(engineAnnouncement, course_id=courseId)
        target = Announcement.objects(course_id=course)
        if target == None:
            return "Announcement not found"
        return target

    def add_announcement(user,course,title,content):# course=course_id
        target = User(user).obj
        if target is None:
            return "User not found."
        created_time = timestamp_now() # local time utc+8
        updated_time = created_time
        engine.Announcement(announcement_name=title,
                            course_id=course,
                            author=user,
                            created=created_time,
                            updated=updated_time,
                            markdown=content)

    def edit_announcement(course,title,content):
        courseExist = get_obj(engine.Course, course_name=course)
        if courseExist == None:
            return "Course not found."
        new_announcement = Announcement()
        new_announcement.annocement_name=title
        new_announcement.course_id = course
        target_course = Course.objects(course_id=course).first()
        new_announcement.author = target_course.teacher_id
        new_announcement.markdown = content
        new_announcement.save()
        return new_announcement
