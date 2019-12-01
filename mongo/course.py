from mongo import engine

class Course:
    pass


def get_all_courses():
    return engine.Course.objects


def delete_course(course):
    co = engine.Course.objects.get(coure_name=course)
    if co == None:
        return -1
    co.delete()


def add_course(course, teacher):
    if engine.Course.objects.get(course_name=course) != None:
        return -1

    te = engine.User.objects.get(username=teacher)
    if te == None:
        return -2

    engine.Course(**{'course_name': course, 'teacher_id': te}).save()


def edit_course(course, new_course, teacher):
    co = engine.Course.objects.get(coure_name=course)
    if co == None:
        return -1

    te = engine.User.objects.get(username=teacher)
    if te == None:
        return -2

    co.course_name = new_course
    co.teacher = te
