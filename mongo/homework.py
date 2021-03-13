from typing import List, Optional
from . import engine
from .base import MongoBase
from .course import Course
from .utils import perm
from .problem import Problem
from datetime import datetime

__all__ = ['Homework']


class Homework(MongoBase, engine=engine.Homework):
    @classmethod
    def add(
        cls,
        user,
        course_name: str,
        hw_name: str,
        problem_ids: List[int] = [],
        markdown: str = '',
        scoreboard_status: int = 0,
        start=None,
        end=None,
    ):
        # query db check the hw doesn't exist
        course = Course(course_name).obj
        if course is None:
            raise engine.DoesNotExist('course not exist')
        # check user is teacher or ta
        if perm(course, user) <= 1:
            raise PermissionError('user is not teacher or ta')
        course_id = course.id
        if cls.engine.objects(
                course_id=str(course_id),
                homework_name=hw_name,
        ):
            raise engine.NotUniqueError('homework exist')
        # check problems exist
        problems = [*map(Problem, problem_ids)]
        if not all(problems):
            raise engine.DoesNotExist(f'some problems not found!')
        homework = cls.engine(
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
        homework.save()
        # init student status
        user_problems = {}
        for problem in problems:
            problem_id = str(problem.problem_id)
            user_problems[problem_id] = cls.default_problem_status()
            problem.update(push__homeworks=homework)
        homework.update(student_status={
            s: user_problems
            for s in course.student_nicknames
        })
        # add homework to course
        course.update(push__homeworks=homework.id)
        return homework

    @classmethod
    def update(
        cls,
        user,
        homework_id: str,
        markdown: str,
        new_hw_name: str,
        problem_ids: List[int],
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        scoreboard_status: Optional[int] = None,
    ):
        homework = cls.engine.objects.get(id=homework_id)
        course = engine.Course.objects.get(id=homework.course_id)
        # check user is teacher or ta
        if perm(course, user) <= 1:
            raise PermissionError('user is not tacher or ta')
        # check the new_name hasn't been use in this course
        if new_hw_name is not None:
            if cls.engine.objects(
                    course_id=str(course.id),
                    homework_name=new_hw_name,
            ):
                raise engine.NotUniqueError('homework exist')
            else:
                homework.update(homework_name=new_hw_name)
        # update fields
        if start is not None:
            homework.duration.start = datetime.fromtimestamp(start)
        if end is not None:
            homework.duration.end = datetime.fromtimestamp(end)
        if scoreboard_status is not None:
            homework.scoreboard_status = scoreboard_status
        if markdown is not None:
            homework.markdown = markdown
        homework.save()
        drop_ids = set(homework.problem_ids) - set(problem_ids)
        new_ids = set(problem_ids) - set(homework.problem_ids)
        # add
        for pid in new_ids:
            problem = Problem(pid).obj
            if problem is None:
                continue
            homework.update(push__problem_ids=pid)
            problem.update(push__homeworks=homework)
            for key in course.student_nicknames:
                homework.student_status[key][str(
                    pid)] = Homework.default_problem_status()
        # delete
        for pid in drop_ids:
            problem = Problem(pid).obj
            if problem is None:
                continue
            homework.update(pull__problem_ids=pid)
            problem.update(pull__homeworks=homework)
            for status in homework.student_status.values():
                del status[str(pid)]
        return homework

    # delete problems/paticipants in hw
    @classmethod
    def delete_problems(
        cls,
        user,
        homework_id,
    ):
        homework = cls.engine.objects.get(id=homework_id)
        if homework is None:
            raise engine.DoesNotExist('homework not exist')
        course = engine.Course.objects.get(id=homework.course_id)
        # check user is teacher or ta
        if perm(course, user) <= 1:
            raise PermissionError('user is not teacher or ta')
        for pid in homework.problem_ids:
            problem = Problem(pid).obj
            if problem is None:
                continue
            problem.update(pull__homeworks=homework)
        homework.delete()
        return homework

    @staticmethod
    def get_homeworks(course_name):
        course = Course(course_name).obj
        if course is None:
            raise engine.DoesNotExist('course not exist')
        homeworks = course.homeworks or []
        homeworks = sorted(homeworks, key=lambda h: h.duration.start)
        return homeworks

    @classmethod
    def get_by_id(cls, homework_id):
        try:
            homework = cls.engine.objects.get(id=homework_id)
        except engine.DoesNotExist:
            raise engine.DoesNotExist('homework not exist')
        return homework

    @classmethod
    def get_by_name(cls, course_name, homework_name):
        try:
            homework = cls.engine.objects.get(
                course_id=Course(course_name).id,
                homework_name=homework_name,
            )
        except engine.DoesNotExist:
            raise engine.DoesNotExist('homework not exist')
        return homework

    @staticmethod
    def default_problem_status():
        return {
            'score': 0,
            'problemStatus': None,
            'submissionIds': [],
        }
