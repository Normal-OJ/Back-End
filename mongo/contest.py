from . import engine
from mongo.course import perm
from mongoengine import DoesNotExist, NotUniqueError
from datetime import datetime
from mongo.problem import Problem
__all__ = [
    'Contest', 'AuthorityError', 'UserIsNotInCourse', 'ExistError',
    'UserIsNotInContest'
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


class Contest:
    @staticmethod
    def add_contest(user,
                    course_name,
                    contest_name,
                    problem_ids,
                    scoreboard_status,
                    contest_mode,
                    start=None,
                    end=None):
        #check the contest name won't repeat
        course = engine.Course.objects.get(course_name=course_name)
        for x in course.contest:
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
        contest.save()

        if problem_ids is not None:
            for problem_id in problem_ids:
                problem = Problem(problem_id=problem_id).obj
                problem.contests.append(contest)
                problem.save()

        # get contestId then store in the correspond course
        course.contest.append(contest.id)
        course.save()
        return contest

    @staticmethod
    def update(user, course_name, contest_name, new_contest_name, start, end,
               problem_ids, scoreboard_status, contest_mode):
        course = engine.Course.objects(course_name=course_name).first()

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
                    problem.contests.append(contest)
                    problem.save()
        contest.save()
        return contest

    @staticmethod
    def delete(user, course_name, contest_name):
        course = engine.Course.objects.get(course_name=course_name)
        contest = engine.Contest.objects.get(name=contest_name,
                                             course_id=str(course.id))
        # verify user's roles(teacher/admin)
        role = perm(course, user)
        if role < 2:
            raise AuthorityError

        if contest is None:
            raise DoesNotExist

        for problem_id in contest.problem_ids:
            problem = Problem(problem_id=problem_id).obj
            problem.contests.remove(contest)
            problem.save()

        contest.delete()
        course.save()
        return contest

    @staticmethod
    def get_course_contests(course_name):
        course = engine.Course.objects(course_name=course_name).first()
        if course is None:
            raise DoesNotExist
        contests = course.contest
        if contests is None:
            contests = {}
        return contests

    @staticmethod
    def get_single_contest(user, id):
        contest = engine.Contest.objects.get(id=id)
        if contest is None:
            raise DoesNotExist
        course = engine.Course.objects.get(id=contest.course_id)
        data = {
            "name": contest.name,
            "start": contest.duration.start,
            "end": contest.duration.end,
            "contestMode": contest.contest_mode,
            "scoreboard_status": contest.scoreboard_status,
            "courseName": course.course_name
        }
        role = perm(course, user)
        if role > 1 or datetime.now() > contest.duration.start:
            data["problemIds"] = contest.problem_ids
        if contest.scoreboard_status == 0:
            data["participants"] = contest.participants
        return data

    @staticmethod
    def get_user_contest(user):
        if user.contest_id is None:
            raise DoesNotExist
        return user.contest_id

    @staticmethod
    def add_user_in_contest(user, contest_id):
        #get course of this contest
        contest = engine.Contest.objects.get(id=contest_id)
        db_user = engine.User.objects.get(username=user.username)
        course_of_contest = engine.Course.objects.get(id=contest.course_id)
        if contest is None:
            raise DoesNotExist

        #check if user is student in the contest's course
        role = perm(course_of_contest, user)
        if role < 1:
            raise UserIsNotInCourse

        #check if user already is in this contest
        if user.contest is not None:
            raise ExistError

        #add this user in contest
        user_ids = {}
        user_problems = {}
        if contest.problem_ids is not None:
            for problem_id in contest.problem_ids:
                user_problems[str(problem_id)] = {
                    "score": 0,
                    "problemStatus": 1,
                    "submissonIds": []
                }
        contest.participants[user.username] = user_problems
        db_user.contest = contest
        contest.save()
        db_user.save()

    @staticmethod
    def user_leave_contest(user):
        #get course of this contest
        contest = engine.Contest.objects.get(id=user.contest.id)
        db_user = engine.User.objects.get(username=user.id)
        course_of_contest = engine.Course.objects.get(id=contest.course_id)

        #check if user is in the contest
        if user.username not in contest.participants:
            raise UserIsNotInContest

        #pop student from participants and remove contest
        contest.participants.pop(user.username)
        db_user.contest = None
        db_user.save()
        contest.save()
