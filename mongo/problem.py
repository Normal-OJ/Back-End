from . import engine
from .course import *
from zipfile import ZipFile, is_zipfile
from pathlib import Path
from random import randint
import os

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
    engine.Problem(problem_id=problem_id,
                   courses=list(Course(name).obj for name in courses),
                   problem_status=status,
                   problem_type=type,
                   problem_name=problem_name,
                   description=description,
                   owner=user.username,
                   tags=tags,
                   test_case=test_case_info,
                   can_view_stdout=can_view_stdout,
                   allowed_language=allowed_language or 7).save()
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


def edit_problem(user, problem_id, courses, status, type, problem_name,
                 description, tags, test_case_info, allowed_language):
    problem = Problem(problem_id).obj
    old_case = problem.test_case['cases'][:]
    test_case = test_case_info

    problem.courses = list(
        engine.Course.objects.get(course_name=name) for name in courses)
    problem.problem_status = status
    problem.problem_type = type
    problem.problem_name = problem_name
    problem.description['description'] = description['description']
    problem.description['hint'] = description['hint']
    problem.description['input'] = description['input']
    problem.description['output'] = description['output']
    problem.description['sample_input'] = description['sampleInput']
    problem.description['sample_output'] = description['sampleOutput']
    problem.owner = user.username
    problem.tags = tags
    problem.allowed_language = allowed_language
    problem.test_case['language'] = test_case['language']
    problem.test_case['fill_in_template'] = test_case['fillInTemplate']

    i = 0
    problem.test_case['cases'].clear()
    for case in test_case['cases']:
        case = {
            'case_score': case['caseScore'],
            'case_count': case['caseCount'],
            'memory_limit': case['memoryLimit'],
            'time_limit': case['timeLimit'],
        }

        if i < len(old_case):
            case['input'] = old_case[i]['input']
            case['output'] = old_case[i]['output']
        i += 1

        case = engine.ProblemCase(**case)
        problem.test_case['cases'].append(case)

    problem.save()


def edit_problem_test_case(problem_id, test_case):
    problem = Problem(problem_id).obj

    file = f'/tmp/{randint(100000,999999)}'
    test_case.save(file + '.zip')

    for case in problem.test_case['cases']:
        case['input'] = [0] * case['case_count']
        case['output'] = [0] * case['case_count']

    with ZipFile(file + '.zip', 'r') as f:
        f.extractall(file)

    for p in Path(file).iterdir():
        subtest_index = int(p.name[:2])
        subtest_case_index = int(p.name[2:4])
        io = p.name[5:] + "put"

        problem.test_case['cases'][subtest_index][io][
            subtest_case_index] = p.read_text()
        os.remove(file + '/' + p.name)

    problem.save()
    os.remove(file + '.zip')
    os.rmdir(file)
    return problem.test_case['cases'][0]['input']


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
