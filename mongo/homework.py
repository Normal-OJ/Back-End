from typing import List, Optional
from . import engine
from .user import User
from .base import MongoBase
from .course import Course
from .utils import perm, doc_required
from .problem.problem import Problem
from .ip_filter import IPFilter
from datetime import datetime

__all__ = ['Homework']


class Error():
    Illegal_penalty = 1
    Invalid_penalty = 2


def check_penalty(penalty: Optional[str]) -> int:
    if penalty is None:
        return 0
    allowed_chars = ["+", "-", "*", "/", "=", ".", "(", ")", ":", ">", "<"]
    allowed_words = ["score", "overtime", "if", "else"]
    checkstring = ""
    for i in penalty:
        checkstring += (" " if i in allowed_chars else i)
    for i in checkstring.split():
        if i not in allowed_words:
            try:
                int(i)
            except:
                return Error.Illegal_penalty
    try:
        score = 0
        overtime = 0
        exec(penalty)
    except:
        return Error.Invalid_penalty
    return 0


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
        penalty: Optional[str] = '',
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

        penalty_stat = check_penalty(penalty)
        if penalty_stat == Error.Illegal_penalty:
            raise ValueError("Illegal penalty")
        elif penalty_stat == Error.Invalid_penalty:
            raise ValueError("Invalid penalty")

        problems = [*map(Problem, problem_ids)]
        if not all(problems):
            raise engine.DoesNotExist('some problems not found!')
        homework = cls.engine(
            homework_name=hw_name,
            course_id=str(course_id),
            problem_ids=problem_ids,
            scoreboard_status=scoreboard_status,
            markdown=markdown,
        )
        if penalty:
            homework.penalty = penalty
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
        penalty: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        scoreboard_status: Optional[int] = None,
    ):
        homework = cls.engine.objects.get(id=homework_id)
        course = engine.Course.objects.get(id=homework.course_id)
        # check user is teacher or ta
        if perm(course, user) <= 1:
            raise PermissionError('user is not teacher or ta')
        # check the new_name hasn't been use in this course

        if penalty is not None:
            penalty_stat = check_penalty(penalty)
            if penalty_stat == Error.Illegal_penalty:
                raise ValueError("Illegal penalty")
            elif penalty_stat == Error.Invalid_penalty:
                raise ValueError("Invalid penalty")
            else:
                homework.penalty = penalty

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
            problem = Problem(pid)
            if not problem:
                continue
            homework.update(push__problem_ids=pid)
            problem.update(push__homeworks=homework)
            for key in course.student_nicknames:
                student_status[key][str(pid)] = cls.default_problem_status()
        # delete
        for pid in drop_ids:
            problem = Problem(pid)
            if not problem:
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
            problem = Problem(pid)
            if not problem:
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

    def do_penalty(self, submission, stat):
        d = {}

        d['score'] = submission.score - stat['rawScore']
        if d['score'] > 0:
            d['overtime'] = int((submission.timestamp.timestamp() -
                                 self.duration.end.timestamp()) / 86400)
            exec(self.penalty, d)
            d['score'] = int(d['score'])
            stat['score'] += d['score']
            stat['rawScore'] = submission.score

        return [stat['score'], stat['rawScore']]
