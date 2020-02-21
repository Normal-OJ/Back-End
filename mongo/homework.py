from mongo import *
from mongo import engine
from mongo.course import perm, Course
from mongo.problem import Problem
from datetime import datetime

__all__ = ['Homework']


class Homework:
    @staticmethod
    def add_hw(
        user,
        course_name,
        hw_name,
        problem_ids=[],
        markdown='',
        scoreboard_status=0,
        start=None,
        end=None,
    ):
        # query db check the hw doesn't exist
        course = Course(course_name).obj
        if course is None:
            raise engine.DoesNotExist('course not exist')
        course_id = course.id
        students = course.student_nicknames
        homework = engine.Homework.objects(
            course_id=str(course_id),
            homework_name=hw_name,
        )
        # check user is teacher or ta
        if perm(course, user) <= 1:
            raise PermissionError('user is not teacher or ta')
        if len(homework) != 0:
            raise engine.NotUniqueError('homework exist')

        homework = engine.Homework(
            homework_name=hw_name,
            course_id=str(course_id),
            problem_ids=problem_ids,
            scoreboard_status=scoreboard_status,
            markdown=markdown,
        )
        if start:
            homework.duration.start = datetime.fromtimestamp(start)
        if end:
            homework.duration.end = datetime.fromtimestamp(end)

        problems = []
        for problem_id in problem_ids:
            problem = Problem(problem_id).obj
            if problem is None:
                raise engine.DoesNotExist(f'problem {problem_id} not found!')
            problems.append(problem)
        homework.save()

        # init student status
        user_ids = {}
        user_problems = {}
        for problem in problems:
            user_problems[str(problem.problem_id)] = {
                'score': 0,
                'problemStatus': None,
                'submissionIds': []
            }
            problem.homeworks.append(homework)
            problem.save()

        for key in students:
            user_ids[key] = user_problems
        homework.student_status = user_ids
        homework.save()

        # get homeworkId then store in the correspond course
        course.homeworks.append(homework.id)
        course.save()

        return homework

    @staticmethod
    def update(user, homework_id, markdown, new_hw_name, start, end,
               problem_ids, scoreboard_status):
        homework = engine.Homework.objects.get(id=homework_id)
        course = engine.Course.objects.get(id=homework.course_id)

        # check user is teacher or ta
        if perm(course, user) <= 1:
            raise PermissionError('user is not tacher or ta')

        course_id = course.id
        students = course.student_nicknames
        # check the new_name hasn't been use in this course
        if new_hw_name is not None:
            result = engine.Homework.objects(course_id=str(course_id),
                                             homework_name=new_hw_name)
            if len(result) != 0:
                raise engine.NotUniqueError('homework exist')
            else:
                homework.homework_name = new_hw_name
                homework.save()

        # update fields
        if start is not None:
            homework.duration.start = datetime.fromtimestamp(start)
        if end is not None:
            homework.duration.end = datetime.fromtimestamp(end)
        if scoreboard_status is not None:
            homework.scoreboard_status = scoreboard_status
        drop_ids = set(homework.problem_ids) - set(problem_ids)
        new_ids = set(problem_ids) - set(homework.problem_ids)
        # add
        for pid in new_ids:
            if pid not in homework.problem_ids:
                problem = Problem(problem_id=pid).obj
                if problem is None:
                    continue
                homework.problem_ids.append(pid)
                problem.homeworks.append(homework)
                problem.save()
                for key in students:
                    homework.student_status[key][str(pid)] = {
                        'score': 0,
                        'problemStatus': 1,
                        'submissionIds': []
                    }
        # delete
        for pid in drop_ids:
            problem = Problem(problem_id=pid).obj
            if problem is None:
                continue
            homework.problem_ids.remove(pid)
            problem.homeworks.remove(homework)
            problem.save()
            for status in homework.student_status.values():
                del status[str(pid)]
        if markdown is not None:
            homework.markdown = markdown

        homework.save()
        return homework

    # delete  problems/paticipants in hw
    @staticmethod
    def delete_problems(user, homework_id):
        homework = engine.Homework.objects.get(id=homework_id)
        if homework is None:
            raise engine.DoesNotExist('homework not exist')

        course = engine.Course.objects.get(id=homework.course_id)
        # check user is teacher or ta
        if perm(course, user) <= 1:
            raise PermissionError('user is not teacher or ta')

        for pid in homework.problem_ids:
            problem = Problem(problem_id=pid).obj
            if problem is None:
                continue
            problem.homeworks.remove(homework)
            problem.save()

        homework.delete()
        course.save()

        return homework

    @staticmethod
    def get_homeworks(course_name):
        course = Course(course_name).obj
        if course is None:
            raise engine.DoesNotExist('course not exist')
        homeworks = course.homeworks or []
        homeworks = sorted(homeworks, key=lambda h: h.duration.start)
        return homeworks

    @staticmethod
    def get_by_id(homework_id):
        try:
            homework = engine.Homework.objects.get(id=homework_id)
        except engine.DoesNotExist:
            raise engine.DoesNotExist('homework not exist')
        return homework

    @staticmethod
    def get_by_name(course_name, homework_name):
        try:
            homework = engine.Homework.objects.get(
                course_id=Course(course_name).id, homework_name=homework_name)
        except engine.DoesNotExist:
            raise engine.DoesNotExist('homework not exist')
        return homework
