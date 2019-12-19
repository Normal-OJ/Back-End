from mongo import engine

class Announcement:

    def get_all_announcement():
        return engine.announcement.object

    def get_announcement(course):
        #target = get_obj(engineAnnouncement, course_id=courseId)
        target = Announcement.objects(course_id=course)
        if target == None:
            return "Announcement not found"
        return target

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
