from . import engine
from .course import *

__all__ = [
    'Number', 'Problem', 'get_problem_list', 'add_problem', 'edit_problem',
    'delete_problem', 'copy_problem', 'release_problem', 'can_view'
]


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


def add_problem(user, courses, status, type, problem_name, description, tags,
                test_case, can_view_stdout):
    serial_number = Number("serial_number").obj

    problem_id = serial_number.number
    engine.Problem(problem_id=problem_id,
                   courses=list(Course(name).obj for name in courses),
                   problem_status=status,
                   problem_type=type,
                   problem_name=problem_name,
                   description=description,
                   owner=user.username,
                   tags=tags,
                   test_case=test_case,
                   can_view_stdout=can_view_stdout).save()

    serial_number.number += 1
    serial_number.save()

    return problem_id


def edit_problem(user, problem_id, courses, status, type, problem_name,
                 description, tags, test_case):
    problem = Problem(problem_id).obj

    problem.courses = list(
        engine.Course.objects.get(course_name=name) for name in courses)
    problem.problem_status = status
    problem.problem_type = type
    problem.problem_name = problem_name
    problem.description = description
    problem.owner = user.username
    problem.tags = tags
    problem.test_case['language'] = test_case['language']
    problem.test_case['fill_in_template'] = test_case['fillInTemplate']
    problem.test_case['cases'].clear()
    for case in test_case['cases']:
        case['case_score'] = case['caseScore']
        del case['caseScore']
        case['memory_limit'] = case['memoryLimit']
        del case['memoryLimit']
        case['time_limit'] = case['timeLimit']
        del case['timeLimit']

        case = engine.ProblemCase(**case)
        problem.test_case['cases'].append(case)

    problem.save()

    return problem


def delete_problem(problem_id):
    problem = Problem(problem_id).obj
    problem.delete()


def copy_problem(user, problem_id):
    serial_number = Number("serial_number").obj
    problem = Problem(problem_id).obj

    engine.Problem(problem_id=serial_number.number,
                   problem_status=problem.problem_status,
                   problem_type=problem.problem_type,
                   problem_name=problem.problem_name,
                   description=problem.description,
                   owner=user.username,
                   tags=problem.tags,
                   test_case=problem.test_case).save()

    serial_number.number += 1
    serial_number.save()


def release_problem(problem_id):
    course = Course("Public").obj
    problem = Problem(problem_id).obj
    problem.courses = [course]
    problem.owner = "first_admin"
    problem.save()
