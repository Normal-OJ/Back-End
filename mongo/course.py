from . import engine
from .user import *
from .utils import *
import re
from typing import Dict
from .base import MongoBase

__all__ = [
    'Course',
]


class Course(MongoBase, engine=engine.Course):
    def __new__(cls, course_name, *args, **kwargs):
        try:
            new = super().__new__(cls, course_name)
        except engine.ValidationError:
            try:
                pk = Course.engine.objects(course_name=course_name).get()
                new = super().__new__(cls, pk)
            except engine.DoesNotExist:
                new = super().__new__(cls, '0' * 24)
        return new

    def update_student_namelist(
        self,
        student_nicknames: Dict[str, str],
    ):
        from .homework import Homework
        if not all(User(name) for name in student_nicknames):
            raise engine.DoesNotExist(f'User not found')
        drop_user = set(self.student_nicknames) - set(student_nicknames)
        for user in drop_user:
            self.remove_user(User(user).obj)
        new_user = set(student_nicknames) - set(self.student_nicknames)
        for user in new_user:
            self.add_user(User(user).obj)
        self.student_nicknames = student_nicknames
        # TODO: use event to update homework data
        for homework in self.homeworks:
            for user in drop_user:
                del homework.student_status[user]
            user_problems = {}
            for pid in homework.problem_ids:
                user_problems[str(pid)] = Homework.default_problem_status()
            for user in new_user:
                homework.student_status[user] = user_problems
            homework.save()
        self.save()

    def add_user(self, user: User):
        obj = self.obj
        if obj is None:
            raise engine.DoesNotExist(f'Course [{self.course_name}]')
        user.update(add_to_set__courses=self.id)
        user.reload()

    def remove_user(self, user: User):
        user.update(pull__courses=self.id)
        user.reload()

    @classmethod
    def get_all(cls):
        return engine.Course.objects

    @classmethod
    def get_user_courses(cls, user):
        if user.role != 0:
            return user.courses
        else:
            return cls.get_all()

    def edit_course(self, user, new_course, teacher):
        if re.match(r'^[a-zA-Z0-9._\- ]+$', new_course) is None:
            raise ValueError

        if not self:
            raise engine.DoesNotExist('Course')
        if not perm(self, user):
            raise PermissionError
        te = User(teacher)
        if not te:
            raise engine.DoesNotExist('User')

        self.course_name = new_course
        if te.obj != self.teacher:
            self.remove_user(self.teacher)
            self.add_user(te.obj)
        self.teacher = te.obj
        self.save()
        return True

    def delete_course(self, user):
        if not self:
            # course not found
            raise engine.DoesNotExist('Course')
        if not perm(self, user):
            # user is not the TA or teacher in course
            raise PermissionError

        self.remove_user(self.teacher)
        self.delete()
        return True

    @classmethod
    def add_course(cls, course, teacher):
        if re.match(r'^[a-zA-Z0-9._\- ]+$', course) is None:
            raise ValueError
        teacher = User(teacher)
        if not teacher:
            raise engine.DoesNotExist('User')
        if teacher.role >= 2:
            raise PermissionError(
                f'{teacher} is not permitted to create a course')
        co = cls.engine(
            course_name=course,
            teacher=teacher.obj,
        ).save()
        cls(co).add_user(teacher.obj)
        return True

    @classmethod
    def get_public(cls):
        if not cls('Public'):
            cls.add_course('Public', 'first_admin')
        return cls('Public')
