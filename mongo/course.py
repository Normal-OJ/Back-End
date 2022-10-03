from . import engine
from .user import *
from .utils import *
import re
from typing import Dict, List, Optional
from .base import MongoBase
from datetime import datetime

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
        drop_user = [*map(User, drop_user)]
        new_user = [*map(User, new_user)]
        for homework in map(Homework, self.homeworks):
            homework.remove_student(drop_user)
            homework.add_student(new_user)
        self.save()

    def add_user(self, user: User):
        if not self:
            raise engine.DoesNotExist(f'Course [{self.course_name}]')
        user.update(add_to_set__courses=self.id)
        user.reload('courses')

    def remove_user(self, user: User):
        user.update(pull__courses=self.id)
        user.reload('courses')

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

    def get_scoreboard(
        self,
        problem_ids: List[int],
        start: Optional[float] = None,
        end: Optional[float] = None,
    ) -> List[Dict]:
        scoreboard = []
        usernames = [User(u).id for u in self.student_nicknames.keys()]
        matching = {
            "user": {
                "$in": usernames
            },
            "problem": {
                "$in": problem_ids
            },
            "timestamp": {},
        }
        if start:
            matching['timestamp']['$gte'] = datetime.fromtimestamp(start)
        if end:
            matching['timestamp']['$lte'] = datetime.fromtimestamp(end)
        if not matching["timestamp"]:
            del matching["timestamp"]
        pipeline = [
            {
                "$match": matching
            },
            {
                "$group": {
                    "_id": {
                        "user": "$user",
                        "problem": "$problem",
                    },
                    "count": {
                        "$sum": 1
                    },
                    "max": {
                        "$max": "$score"
                    },
                    "min": {
                        "$min": "$score"
                    },
                    "avg": {
                        "$avg": "$score"
                    },
                }
            },
            {
                "$group": {
                    "_id": "$_id.user",
                    "scores": {
                        "$push": {
                            "pid": "$_id.problem",
                            "count": "$count",
                            "max": "$max",
                            "min": "$min",
                            "avg": "$avg",
                        },
                    },
                }
            },
        ]
        cursor = engine.Submission.objects().aggregate(pipeline)
        unrecorded_users = set(usernames)
        for item in cursor:
            sum_of_score = sum(s['max'] for s in item['scores'])
            scoreboard.append({
                'user': User(item['_id']).info,
                'sum': sum_of_score,
                'avg': sum_of_score / len(problem_ids),
                **{f'{score["pid"]}': score
                   for score in item['scores']},
            })
            unrecorded_users.remove(item['_id'])
        for u in unrecorded_users:
            scoreboard.append({
                'user': User(u).info,
                'sum': 0,
                'avg': 0,
            })

        return scoreboard

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
