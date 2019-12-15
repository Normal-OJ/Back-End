from . import engine
from .course import Course

__all__ = ['HomeWork']


class HomeWork:
    @staticmethod
    def add_hw(course_name,markdown , hw_name, start, end, problem_ids, scoreboard_status):
       #query db check the hw doesn't exist       
        course = engine.Course.objects(course_name=course_name).first()
        course_id = course.id
        students = course.students
        homework = engine.Homework.objects.get(course_id=str(course_id),
                                               name=hw_name)
        if (homework is not none):
            raise FileExistsError

        homework = engine.Homework(name=hw_name,
                                   course_id=str(course_id),
                                   problem_ids=problem_ids)
        homework.duration.start = start
        homework.duration.end = end
        homework.markdown = markdown
        homework.scoreboard_status = scoreboard_status
        #init student status
        userIds = {}
        userProblems = {}
        for problem_id in problem_ids:
            userProblems[str(problem_id)] = {
                "score": 0,
                "problemStatus": 1,
                "submissonIds": []
            }

        for key in students:
            userIds[key] = userProblems

        homework.student_status = userIds
        homework.save()
        #get homeworkId then store in the correspond course
        homework = engine.Homework.objects(
            name=hw_name,
            course_id=str(course_id),
        ).first()
        homeworkid = homework.id
        course = engine.Course.objects.get(id=course_id)
        course.homework.append(homeworkid)
        course.save()
        return homework

    @staticmethod
    def update(course_name, markdown, hw_name, new_hw_name, start, end, problem_ids, scoreboard_status):
        #check course exist
        course = engine.Course.objects(course_name=course_name).first()
        if (course is none):
            raise FileNotFoundError
        course_id = course.id
        students = course.students
        #check the new_name hasn't been use in this course
        homework = engine.Homework.objects.get(course_id=str(course_id),
                                               name=new_hw_name)
        if (homework is not none):
            raise FileExistsError

        #get the homework and update it's field
        homework = engine.Homework.objects.get(course_id=str(course_id),
                                               name=hw_name)
        if (start != 0):
            homework.duration.start = start
        if (end != 0):
            homework.duration.end = end
        homework.scoreboard_status = scoreboard_status
        #if problemid exist then delete ,else add it in list
        userProblems = {}
        userIds = {}
        #傳進來的problem_ids應該只有要新增/刪除的
        for x in problem_ids:
            if (x in homework.problem_ids):
                homework.problem_ids.remove(x)
                for userId in homework.student_status:
                    homework.student_status[userId].pop(x)
            else:
                homework.problem_ids.append(x)
                for key in students:
                    homework.student_status[key][x] = {
                        "score": 0,
                        "problemStatus": 1,
                        "submissonIds": []
                    }
        homework.markdown = markdown
        homework.name = new_hw_name
        homework.save()
        return homework

    #delete  problems/paticipants in hw
    @staticmethod
    def delete_problems(course_name, hw_name):
        course = engine.Course.objects(course_name=course_name).first()
        course_id = course.id
        homework = engine.Homework.objects(
            course_id=str(course_id),
            homewor_name=hw_name,
        ).first()        
        homework.delete()
        course.save()
        return homework

    @staticmethod
    def getHomeworks(course_name):
        course = engine.Course.objects(course_name=course_name).first()
        course_id = str(course.id)
        homeworks = engine.Homework.objects(course_id=course_id)
        return homeworks

    @staticmethod
    def getSignalHomework(id):
        homework = engine.Homework.objects(id=id).first()
        return homework
