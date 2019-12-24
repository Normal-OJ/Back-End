from . import engine
from mongo.course import perm
from mongoengine import DoesNotExist, NotUniqueError
from datetime import datetime
__all__ = ['Contest', 'AuthorityError']


class AuthorityError(Exception):
    '''check whether the user is teacher/ta/admin in this course'''
    pass


class Contest:
    @staticmethod
    def add_contest(user, course_name, contest_name, start, end, problem_ids,
                    scoreboard_status, contest_mode):
        #check the contest name won't repeat
        course = engine.Course.objects.get(course_name=course_name)
        for x in course.contest:
            if x.name == contest_name:
                raise NotUniqueError
        #verify user's roles(teacher/admin)
        role = perm(course, user)
        if role != 4 and role != 3 and role != 2:
            raise AuthorityError

        students = course.student_nicknames
        contest = engine.Contest(name=contest_name,
                                 course_id=str(course.id),
                                 problem_ids=problem_ids)
        contest.duration.start = datetime.now() if start is None else start
        contest.duration.end = datetime.now() if end is None else end
        contest.contest_mode = 0 if contest_mode is None else contest_mode
        contest.scoreboard_status = 0 if scoreboard_status is None else scoreboard_status
        #init participants status
        user_ids = {}
        user_problems = {}
        if problem_ids is not None:
            for problem_id in problem_ids:
                user_problems[str(problem_id)] = {
                    "score": 0,
                    "problemStatus": 1,
                    "submissonIds": []
                }
        for key in students:
            user_ids[key] = user_problems
        contest.participants = user_ids
        contest.save()
        #get contestId then store in the correspond course
        course.contest.append(contest.id)
        course.save()
        return contest

    @staticmethod
    def update(user, course_name, contest_name, new_contest_name, start, end,
               problem_ids, scoreboard_status, contest_mode):
        course = engine.Course.objects(course_name=course_name).first()

        #verify user's roles(teacher/admin)
        role = perm(course, user)
        if role != 4 and role != 3 and role != 2:
            raise AuthorityError

        students = course.student_nicknames
        contest = engine.Contest.objects.get(name=contest_name,
                                             course_id=str(course.id))
        if contest is None:
            raise DoesNotExist
        #check the new_name hasn't been use in this course
        if new_contest_name is not None:
            result = engine.Contest.objects(name=new_contest_name)
            if len(result) != 0:
                raise NotUniqueError
            else:
                contest.name = new_contest_name

        #update fields
        if start is not None:
            contest.duration.start = start
        if end is not None:
            contest.duration.end = end
        if scoreboard_status is not None:
            contest.scoreboard_status = scoreboard_status
        if contest_mode is not None:
            contest.contest_mode = contest_mode
        #if problemid exist then delete ,else add it in list
        user_problems = {}
        user_ids = {}
        #傳進來的problem_ids應該只有要新增/刪除的
        if problem_ids is not None:
            for id in problem_ids:
                if (id in contest.problem_ids):
                    contest.problem_ids.remove(id)
                    for userId in contest.participants:
                        contest.participants[userId].pop(id)
                else:
                    contest.problem_ids.append(id)
                    for key in students:
                        contest.participants[key][id] = {
                            "score": 0,
                            "problemStatus": 1,
                            "submissonIds": []
                        }
        contest.save()
        return contest

    @staticmethod
    def delete(user, course_name, contest_name):
        course = engine.Course.objects.get(course_name=course_name)
        contest = engine.Contest.objects.get(name=contest_name,
                                             course_id=str(course.id))
        #verify user's roles(teacher/admin)
        role = perm(course, user)
        if role != 4 and role != 3 and role != 2:
            raise AuthorityError

        if contest is None:
            raise DoesNotExist
        contest.delete()
        course.save()
        return contest

    @staticmethod
    def get_course_contests(course_name):
        course = engine.Course.objects(course_name=course_name).first()
        if course is None:
            raise DoesNotExist
        course_id = str(course.id)
        contests = course.contest
        if contests is None:
            contests = {}
        return contests

    @staticmethod
    def get_single_contest(id):
        contest = engine.Contest.objects.get(id=id)
        if contest is None:
            raise DoesNotExist
        return contest
