from . import engine
from .course import Course

__all__ = ['HomeWork']


class HomeWork:
    @staticmethod
    def add_hw(course_name, hw_name, start, end, problemIds, scoreboardStatus):
        course = engine.Course.objects(course_name=course_name).first()
        courseId = course.id
        students = course.students
        homework = engine.Homework(homeworkName=hw_name,
                                   courseId=str(courseId),
                                   problemIds=problemIds)
        homework.duration.start = start
        homework.duration.end = end
        homework.scoreboardStatus = scoreboardStatus
        #init student status
        userIds = {}
        userProblems = {}
        for problemId in problemIds:
            userProblems[str(problemId)] = {
                "score": 0,
                "problemStatus": 1,
                "submissonIds": []
            }

        for key in students:
            userIds[key] = userProblems

        homework.studentStatus = userIds
        homework.save()
        #get homeworkId then store in the correspond course
        homework = engine.Homework.objects(
            homeworkName=hw_name,
            courseId=str(courseId),
        ).first()
        homeworkId = homework.id
        course = engine.Course.objects.get(id=courseId)
        course.homework.append(homeworkId)
        course.save()
        return homework

    @staticmethod
    def update(course_name, hw_name, start, end, problemIds, scoreboardStatus):
        course = engine.Course.objects(course_name=course_name).first()
        courseId = course.id
        students = course.students
        homework = engine.Homework.objects.get(courseId=str(courseId),
                                               homeworkName=hw_name)
        if (start != 0):
            homework.duration.start = start
        if (end != 0):
            homework.duration.end = end
        homework.scoreboardStatus = scoreboardStatus
        #if problemIds exist then delete ,else add it in list
        userProblems = {}
        userIds = {}
        #傳進來的problemIds應該只有要新增/刪除的
        for x in problemIds:
            if (x in homework.problemIds):
                homework.problemIds.remove(x)
                for userId in homework.studentStatus:
                    homework.studentStatus[userId].pop(x)
            else:
                homework.problemIds.append(x)
                for key in students:
                    homework.studentStatus[key][x] = {
                        "score": 0,
                        "problemStatus": 1,
                        "submissonIds": []
                    }

        homework.save()
        return homework

    #delete  problems/paticipants in hw
    @staticmethod
    def deleteProblems(course_name, hw_name):
        course = engine.Course.objects(course_name=course_name).first()
        courseId = course.id
        homework = engine.Homework.objects(
            courseId=str(courseId),
            homeworkName=hw_name,
        ).first()
        homeworkId = homework.id
        #course.homework.remove(homeworkId)
        homework.delete()
        course.save()
        return homework

    @staticmethod
    def getHomeworks(course_name):
        course = engine.Course.objects(course_name=course_name).first()
        courseId = str(course.id)
        homeworks = engine.Homework.objects(courseId=courseId)
        return homeworks

    @staticmethod
    def getSignalHomework(id):
        homework = engine.Homework.objects(id=id).first()
        return homework
