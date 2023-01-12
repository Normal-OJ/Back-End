from . import engine
from mongo.utils import perm, doc_required
from .course import Course
from .user import User
from mongoengine import DoesNotExist, NotUniqueError
from datetime import datetime
from mongo.problem.problem import Problem
from .base import MongoBase

__all__ = [
    'Contest', 'AuthorityError', 'UserIsNotInCourse', 'ExistError',
    'UserIsNotInContest', 'CourseNotExist', 'ProblemNotExist'
]


class AuthorityError(Exception):
    '''check whether the user is teacher/ta/admin in this course'''
    pass


class UserIsNotInCourse(Exception):
    '''check whether the user is in this course when they want to join in the contest'''
    pass


class UserIsNotInContest(Exception):
    '''check whether the user is in this course when they want to join in the contest'''
    pass


class ExistError(Exception):
    '''if user is already in contest , then throw this exception'''
    pass


class CourseNotExist(Exception):
    '''check whether the course exists'''
    pass


class ProblemNotExist(Exception):
    '''check whether the problem exists'''
    pass


class Contest(MongoBase, engine=engine.Contest):

    @classmethod
    @doc_required('course_name', 'course', Course)
    def add_contest(cls,
                    user,
                    contest_name,
                    problem_ids,
                    scoreboard_status,
                    contest_mode,
                    course: Course,
                    start=None,
                    end=None):
        #check the contest name won't repeat
        for x in course.contests:
            if x.name == contest_name:
                raise NotUniqueError
        # verify user's roles(teacher/admin)
        role = perm(course, user)
        if role < 2:
            raise AuthorityError

        students = course.student_nicknames
        contest = engine.Contest(name=contest_name,
                                 course_id=str(course.id),
                                 problem_ids=problem_ids)
        if start:
            contest.duration.start = datetime.fromtimestamp(start)
        if end:
            contest.duration.end = datetime.fromtimestamp(end)
        contest.contest_mode = 0 if contest_mode is None else contest_mode
        contest.scoreboard_status = 0 if scoreboard_status is None else scoreboard_status

        if problem_ids is not None:
            for problem_id in problem_ids:
                problem = Problem(problem_id=problem_id).obj
                if problem is None:
                    raise ProblemNotExist
                problem.contests.append(contest)
                problem.save()

        # get contestId then store in the correspond course
        contest.save()
        course.contests.append(contest.id)
        course.save()
        return contest

    @classmethod
    @doc_required('course_name', 'course', Course)
    def update(cls, user, contest_name, new_contest_name, start, end,
               problem_ids, scoreboard_status, contest_mode, course: Course):
        # verify user's roles(teacher/admin)
        role = perm(course, user)
        if role < 2:
            raise AuthorityError

        students = course.student_nicknames
        contest = engine.Contest.objects.get(name=contest_name,
                                             course_id=str(course.id))
        if contest is None:
            raise DoesNotExist
        # check the new_name hasn't been use in this course
        if new_contest_name is not None:
            result = engine.Contest.objects(name=new_contest_name)
            if len(result) != 0:
                raise NotUniqueError
            else:
                contest.name = new_contest_name

        # update fields
        if start is not None:
            contest.duration.start = datetime.fromtimestamp(start)
        if end is not None:
            contest.duration.end = datetime.fromtimestamp(end)
        if scoreboard_status is not None:
            contest.scoreboard_status = scoreboard_status
        if contest_mode is not None:
            contest.contest_mode = contest_mode
        # if problemid exist then delete ,else add it in list
        user_problems = {}
        user_ids = {}
        # 傳進來的problem_ids應該只有要新增/刪除的
        if problem_ids is not None:
            for id in problem_ids:
                if (id in contest.problem_ids):
                    contest.problem_ids.remove(id)
                    for userId in contest.participants:
                        contest.participants[userId].pop(id)

                    problem = Problem(problem_id=id).obj
                    if problem is None:
                        raise ProblemNotExist
                    problem.contests.remove(contest)
                    problem.save()
                else:
                    contest.problem_ids.append(id)
                    for key in contest.participants:
                        contest.participants[key][id] = {
                            "score": 0,
                            "problemStatus": 1,
                            "submissonIds": []
                        }

                    problem = Problem(problem_id=id).obj
                    if problem is None:
                        raise ProblemNotExist
                    problem.contests.append(contest)
                    problem.save()
        contest.save()
        return contest

    @classmethod
    @doc_required('course_name', 'course', Course)
    def delete(cls, user, contest_name, course: Course):
        '''
        course = engine.Course.objects(course_name=course_name).first()
        if course is None:
            raise CourseNotExist
        '''
        contest = engine.Contest.objects(name=contest_name,
                                         course_id=str(course.id)).first()
        if contest is None:
            raise DoesNotExist
        # verify user's roles(teacher/admin)
        role = perm(course, user)
        if role < 2:
            raise AuthorityError

        if contest is None:
            raise DoesNotExist

        for problem_id in contest.problem_ids:
            problem = Problem(problem_id=problem_id).obj
            if problem is not None:
                problem.contests.remove(contest)
                problem.save()

        contest.delete()
        course.save()
        return contest

    @classmethod
    @doc_required('course_name', 'course', Course)
    def get_course_contests(cls, course: Course):
        contests = course.contests
        if contests is None:
            contests = {}
        return contests

    def get_single_contest(self, user):
        return self._get_single_contest(user, course=self.course_id)

    @doc_required('course', Course)
    def _get_single_contest(self, user, course: Course):
        data = {
            "name": self.name,
            "start": self.duration.start,
            "end": self.duration.end,
            "contestMode": self.contest_mode,
            "scoreboard_status": self.scoreboard_status,
            "courseName": course.course_name
        }
        role = perm(course, user)
        if role > 1 or datetime.now() > self.duration.start:
            data["problemIds"] = self.problem_ids
        if self.scoreboard_status == 0:
            data["participants"] = self.participants
        return data

    @classmethod
    def get_user_contest(cls, user):
        if user.contest_id is None:
            raise DoesNotExist
        return user.contest_id

    @doc_required('user', 'db_user', User)
    def add_user_in_contest(self, db_user: User):
        self._add_user_in_contest(db_user, course=self.course_id)

    @doc_required('course', 'course_of_contest', Course)
    def _add_user_in_contest(self, db_user, course_of_contest: Course):
        #check if user is student in the contest's course
        role = perm(course_of_contest, db_user)
        if role < 1:
            raise UserIsNotInCourse

        #check if user already is in this contest
        if db_user.contest is not None:
            raise ExistError

        #add this user in contest
        user_ids = {}
        user_problems = {}
        if self.problem_ids is not None:
            for problem_id in self.problem_ids:
                user_problems[str(problem_id)] = {
                    "score": 0,
                    "problemStatus": 1,
                    "submissonIds": []
                }
        self.participants[db_user.username] = user_problems
        db_user.contest = self.obj
        self.save()
        db_user.save()

    def user_leave_contest(self, user):
        #get course of this contest
        self._user_leave_contest(user=user, course=self.course_id)

    @doc_required('user', 'db_user', User)
    @doc_required('course', 'course_of_contest', Course)
    def _user_leave_contest(self, db_user: User, course_of_contest: Course):
        #check if user is in the contest
        if db_user.username not in self.participants:
            raise UserIsNotInContest

        #pop student from participants and remove contest
        self.participants.pop(db_user.username)
        db_user.contest = None
        db_user.save()
        self.save()
