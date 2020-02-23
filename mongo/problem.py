from . import engine
from .course import *
from zipfile import ZipFile, is_zipfile
from pathlib import Path
from random import randint
import json

__all__ = [
    'Number', 'Problem', 'get_problem_list', 'add_problem', 'edit_problem',
    'edit_problem_test_case', 'delete_problem', 'copy_problem',
    'release_problem', 'can_view'
]

number = 1


class Number:
    def __init__(self, name):
        self.name = name

    @property
    def obj(self):
        try:
            obj = engine.Number.objects.get(name=self.name)
        except:
            return None
        return obj


class Problem:
    def __init__(self, problem_id):
        self.problem_id = problem_id

    @property
    def obj(self):
        try:
            obj = engine.Problem.objects.get(problem_id=self.problem_id)
        except:
            return None
        return obj

    @property
    def detailed_info(self):
        p_obj = self.obj
        if p_obj is None:
            return None
        # get tasks info
        tasks = []
        with ZipFile(p_obj.test_case.case_zip) as zf:
            for i, task in enumerate(p_obj.test_case.tasks):
                tasks.append({
                    'input': [
                        zf.open(f'{i:02d}{j:02d}.in').read()
                        for j in range(task.case_count)
                    ],
                    'output': [
                        zf.open(f'{i:02d}{j:02d}.out').read()
                        for j in range(task.case_count)
                    ],
                    'caseScore':
                    task.case_score,
                    'memoryLimit':
                    task.memory_limit,
                    'timeLimit':
                    task.time_limit
                })
        ret = json.loads(p_obj.to_json())
        ret['course'] = [course.course_name for course in p_obj.courses]
        ret['testCase']['tasks'] = tasks
        return ret

    def allowed(self, language):
        if language >= 3 or language < 0:
            return False
        return bool((1 << language) & self.obj.allowed_language)


def increased_number():
    global number
    number += 1

    serial_number = Number("serial_number").obj
    serial_number.number = number
    serial_number.save()


def can_view(user, problem):
    '''cheeck if a user can view the problem'''
    if user.role == 0:
        return True
    if user.contest:
        if user.contest in problem.contests:
            return True
        return False
    if user.username == problem.owner:
        return True
    for course in problem.courses:
        permission = 1 if course.course_name == "Public" else perm(
            course, user)
        if permission and (problem.problem_status == 0 or permission >= 2):
            return True
    return False


def get_problem_list(
    user,
    offset: int,
    count: int,
    problem_id,
    name,
    tags: list,
):
    '''
    get a list of problems
    '''
    ks = {'problem_id': problem_id, 'problem_name': name}
    ks = {k: v for k, v in ks.items() if v is not None}
    problems = engine.Problem.objects.filter(**ks).order_by('problemId')
    problems = [p for p in problems if can_view(user, p)]
    if tags:
        tags = set(tags)
        problems = [p for p in problems if len(set(p.tags) & tags)]

    if offset >= len(problems) and len(problems):
        raise IndexError

    right = len(problems) if count == -1 else offset + count
    right = min(len(problems), right)
    problems = problems[offset:right]

    return problems


def add_written_problem(user, courses, status, problem_name, description,
                        tags):
    problem_id = number
    engine.Problem(
        problem_id=problem_id,
        courses=list(Course(name).obj for name in courses),
        problem_status=status,
        problem_type=2,
        problem_name=problem_name,
        description=description,
        owner=user.username,
        tags=tags,
    ).save()
    increased_number()

    return problem_id


def add_problem(user, courses, status, type, problem_name, description, tags,
                test_case_info, can_view_stdout, allowed_language):
    problem_id = number
    engine.Problem(
        problem_id=problem_id,
        courses=[Course(name).obj for name in courses],
        problem_status=status,
        problem_type=type,
        problem_name=problem_name,
        description=description,
        owner=user.username,
        tags=tags,
        test_case=test_case_info,
        can_view_stdout=can_view_stdout,
        allowed_language=allowed_language or 7,
    ).save()
    increased_number()

    return problem_id


def edit_written_problem(user, problem_id, courses, status, problem_name,
                         description, tags):
    problem = Problem(problem_id).obj

    problem.courses = list(
        engine.Course.objects.get(course_name=name) for name in courses)
    problem.problem_status = status
    problem.problem_type = 2
    problem.problem_name = problem_name
    problem.description = description
    problem.owner = user.username
    problem.tags = tags

    problem.save()


def edit_problem(
    user,
    problem_id,
    courses,
    status,
    type,
    problem_name,
    description,
    tags,
    test_case_info,
    allowed_language,
    can_view_stdout,
):
    problem = Problem(problem_id).obj
    problem.update(
        courses=[Course(name).obj for name in courses],
        problem_status=status,
        problem_type=type,
        problem_name=problem_name,
        description=description,
        owner=user.username,
        tags=tags,
        allowed_language=allowed_language,
        test_case=test_case_info,
        can_view_stdout=can_view_stdout,
    ).save()


def edit_problem_test_case(problem_id, test_case):
    '''
    edit problem's testcase

    Args:
        problem_id: target problem's id
        test_case: testcase zip file
    Exceptions:
        zipfile.BadZipFile: if `test_case` is not a zip file
    Return:
        a bool denote whether the update is successful
    '''
    problem = Problem(problem_id).obj

    # check file structure
    # create set of excepted filenames
    excepted_names = set()
    for i, task in enumerate(problem.test_case.tasks):
        for j in range(task.case_count):
            excepted_names.add(f'{i:02d}{j:02d}.in')
            excepted_names.add(f'{i:02d}{j:02d}.out')
    # input/output filenames
    in_out = {*ZipFile(test_case).namelist()}
    # check diff
    if len(excepted_names - in_out) != 0:
        return False
    # save zip file
    test_case.seek(0)
    problem.test_case.case_zip.put(
        test_case,
        content_type='application/zip',
    )
    # update problem obj
    problem.save()
    return True


def delete_problem(problem_id):
    problem = Problem(problem_id).obj
    problem.delete()


def copy_problem(user, problem_id):
    problem = Problem(problem_id).obj
    engine.Problem(problem_id=number,
                   problem_status=problem.problem_status,
                   problem_type=problem.problem_type,
                   problem_name=problem.problem_name,
                   description=problem.description,
                   owner=user.username,
                   tags=problem.tags,
                   test_case=problem.test_case).save()
    increased_number()


def release_problem(problem_id):
    course = Course("Public").obj
    problem = Problem(problem_id).obj
    problem.courses = [course]
    problem.owner = "first_admin"
    problem.save()
