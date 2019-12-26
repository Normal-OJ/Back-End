from . import engine
from mongo.course import *
from datetime import datetime
__all__ = ['HomeWork']


class HomeWork:
    @staticmethod
    def add_hw(user, course_name, markdown, hw_name, start, end, problem_ids,
               scoreboard_status):
        #query db check the hw doesn't exist
        course = engine.Course.objects(course_name=course_name).first()
        course_id = course.id
        students = course.student_nicknames
        homework = engine.Homework.objects(
            course_id=str(course_id), name=hw_name)
        #check user is teacher or ta
        role = perm(course, user)
        is_ta_match = 0
        if (len(course.tas) != 0):
            for ta in tas:
                if (course.ta.username == user.name):
                    is_ta_match = 1
                    break
        if (is_ta_match != 1 and course.teacher.username != user.username
                and user.role != 0):
            raise NameError
        if (len(homework) != 0):
            raise FileExistsError

        homework = engine.Homework(
            name=hw_name, course_id=str(course_id), problem_ids=problem_ids)
        homework.duration.start = datetime.now() if start is None else start
        homework.duration.end = datetime.now() if end is None else end
        homework.markdown = '' if markdown is None else markdown
        homework.scoreboard_status = 0 if scoreboard_status is None else scoreboard_status
        #init student status
        user_ids = {}
        user_problems = {}
        if (problem_ids is not None):
            for problem_id in problem_ids:
                user_problems[str(problem_id)] = {
                    "score": 0,
                    "problemStatus": 1,
                    "submissonIds": []
                }
        for key in students:
            user_ids[key] = user_problems
        homework.student_status = user_ids
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
    def update(user, course_name, markdown, hw_name, new_hw_name, start, end,
               problem_ids, scoreboard_status):
        #check course exist
        course = engine.Course.objects(course_name=course_name).first()
        if (course is None):
            raise FileNotFoundError

        #check user is teacher or ta
        is_ta_match = 0
        if (len(course.tas) != 0):
            for ta in tas:
                if (course.ta.username == user.name):
                    is_ta_match = 1
                    break
        if (is_ta_match != 1 and course.teacher.username != user.username
                and user.role != 0):
            raise NameError

        course_id = course.id
        students = course.student_nicknames
        #get the homework
        homework = engine.Homework.objects.get(
            course_id=str(course_id), name=hw_name)
        #check the new_name hasn't been use in this course
        if new_hw_name is not None:
            result = engine.Homework.objects(
                course_id=str(course_id), name=new_hw_name)
            if (len(result) != 0):
                raise FileExistsError
            else:
                homework.name = new_hw_name

        #update fields
        if (start is not None):
            homework.duration.start = start
        if (end is not None):
            homework.duration.end = end
        if (scoreboard_status is not None):
            homework.scoreboard_status = scoreboard_status
        #if problemid exist then delete ,else add it in list
        user_problems = {}
        user_ids = {}
        #傳進來的problem_ids應該只有要新增/刪除的
        if (problem_ids is not None):
            for id in problem_ids:
                if (id in homework.problem_ids):
                    homework.problem_ids.remove(id)
                    for userId in homework.student_status:
                        homework.student_status[userId].pop(id)
                else:
                    homework.problem_ids.append(id)
                    for key in students:
                        homework.student_status[key][id] = {
                            "score": 0,
                            "problemStatus": 1,
                            "submissonIds": []
                        }

        if markdown is not None:
            homework.markdown = markdown
        homework.save()
        return homework

    #delete  problems/paticipants in hw
    @staticmethod
    def delete_problems(user, course_name, hw_name):
        course = engine.Course.objects(course_name=course_name).first()
        course_id = course.id
        homework = engine.Homework.objects(
            course_id=str(course_id),
            name=hw_name,
        ).first()

        #check user is teacher or ta
        is_ta_match = 0
        if (len(course.tas) != 0):
            for ta in tas:
                if (course.ta.username == user.name):
                    is_ta_match = 1
                    break
        if (is_ta_match != 1 and course.teacher.username != user.username
                and user.role != 0):
            raise NameError

        if (homework is None):
            raise FileNotFoundError
        homework.delete()
        course.save()
        return homework

    @staticmethod
    def get_homeworks(course_name):
        course = engine.Course.objects(course_name=course_name).first()
        if (course is None):
            raise FileNotFoundError
        course_id = str(course.id)
        homeworks = engine.Homework.objects(course_id=course_id)
        if (homeworks is None):
            homeworks = {}
        return homeworks

    @staticmethod
    def get_signal_homework(id):
        homework = engine.Homework.objects(id=id).first()
        if (homework is None):
            raise FileNotFoundError
        return homework
