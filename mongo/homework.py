from typing import List, Optional
from . import engine
from .user import User
from .base import MongoBase
from .course import Course
from .utils import perm, doc_required
from .problem import Problem
from .ip_filter import IPFilter
from datetime import datetime
from statistics import mean,stdev

__all__ = ['Homework']


# TODO: unittest for class `Homework`
class Homework(MongoBase, engine=engine.Homework):
    def is_valid_ip(self, ip: str) -> bool:
        # no restriction, always valid
        if not self.ip_filters:
            return True
        ip_filters = map(IPFilter, self.ip_filters)
        return any(_filter.match(ip) for _filter in ip_filters)

    @classmethod
    @doc_required('course_name', 'course', Course)
    def add(
        cls,
        user,
        course: Course,
        hw_name: str,
        problem_ids: List[int] = [],
        markdown: str = '',
        scoreboard_status: int = 0,
        start: Optional[float] = None,
        end: Optional[float] = None,
    ):
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
        student_status = homework.student_status
        # add
        for pid in new_ids:
            problem = Problem(pid).obj
            if problem is None:
                continue
            homework.update(push__problem_ids=pid)
            problem.update(push__homeworks=homework)
            for key in course.student_nicknames:
                student_status[key][str(pid)] = cls.default_problem_status()
        # delete
        for pid in drop_ids:
            problem = Problem(pid).obj
            if problem is None:
                continue
            homework.update(pull__problem_ids=pid)
            problem.update(pull__homeworks=homework)
            for status in student_status.values():
                del status[str(pid)]
        homework.update(student_status=student_status)
        return homework

    # delete problems/paticipants in hw
    @doc_required('course', 'course', Course)
    def delete_problems(
        self,
        user,
        course: Course,
    ):
        # check user is teacher or ta
        if perm(course, user) <= 1:
            raise PermissionError('user is not teacher or ta')
        for pid in self.problem_ids:
            problem = Problem(pid).obj
            if problem is None:
                continue
            problem.update(pull__homeworks=self.obj)
        self.delete()
        return self

    @classmethod
    @doc_required('course_name', 'course', Course)
    def get_homeworks(cls, course: Course):
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
                course_id=str(Course(course_name).obj.id),
                homework_name=homework_name,
            )
        except engine.DoesNotExist:
            raise engine.DoesNotExist('homework not exist')
        return homework

    @classmethod
    def default_problem_status(cls):
        return {
            'score': 0,
            'problemStatus': None,
            'submissionIds': [],
        }

    def add_student(self, students: List[User]):
        if any(u.username in self.student_status for u in students):
            raise ValueError('Student already in homework')
        user_status = {
            str(pid): self.default_problem_status()
            for pid in self.problem_ids
        }
        for student in students:
            self.student_status[student.username] = user_status
        self.save()

    def remove_student(self, students: List[User]):
        if any(u.username not in self.student_status for u in students):
            raise ValueError('Student not in homework')
        for student in students:
            del self.student_status[student.username]
        self.save()

    def get_homework_status(self, students: List[User]):
        problem_status = {}
        homework_status = {}
        homework_status["scoreSum"] = 0
        homework_status["homeworkMaxScore"] = 0
        homework_status["studentStatus"] = {}
        for pid in self.problem_ids:
            problem = Problem(pid)
            problem_status[pid] = {}
            problem_status[pid]["submissionStatus"] = problem.get_submission_status()
            problem_status[pid]["acceptedUserCount"] = problem.get_ac_user_count()
            problem_status[pid]["triedUserCount"] = problem.get_tried_user_count()
            weight = 1 # change to actual weight when homework problem has weight attribute
            student_status = {student.username:{} for student in students}
            score_sum = 0
            total_submit_count = 0
            student_count = len(students)
            scores = []
            for student in students:
                student_id = student.username
                high_score = (problem.get_high_score(user=student))
                student_score = high_score
                student_submit_count = problem.submit_count(student)
                total_submit_count += student_submit_count
                score_sum += high_score
                scores.append(high_score)
                student_status[str(student_id)]["sumbitCount"] = student_submit_count
                student_status[str(student_id)]["highScore"] = high_score

            homework_status["scoreSum"] += score_sum
            homework_status["homeworkMaxScore"] += 100 * weight * student_count
            homework_status["studentStatus"][pid] = student_status
            problem_status[pid]["problemWeight"] = weight 
            problem_status[pid]["scoreSum"] = score_sum
            problem_status[pid]["averageScore"] = mean(scores) if len(scores) > 0 else 0
            problem_status[pid]["standardDeviation"] = stdev(scores) if len(scores) > 1 else 0
            problem_status[pid]["maxScore"] = 100 * student_count
            problem_status[pid]["userSubmitCount"] = total_submit_count
            problem_status[pid]["acRate"] = problem_status[pid]["acceptedUserCount"] / problem_status[pid]["triedUserCount"] if problem_status[pid]["triedUserCount"] > 0 else 0 
            

              

        homework_status["problemStatus"] = problem_status
        return homework_status
