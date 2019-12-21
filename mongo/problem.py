from . import engine
from .course import Course

__all__ = [
    'Number', 'Problem', 'get_problem_list', 'add_problem',
    'edit_problem', 'delete_problem', 'copy_problem', 'release_problem'
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


def get_problem_list(role, offset, count):
    problem_list = []
    obj_list = engine.Problem.objects.order_by('problem_name')

    index = offset
    while True:
        if index > (offset + count - 1):
            break
        if role != 2 or obj_list[index].problem_status == 0:
            obj = obj_list[index]
            problem_list.append({
                'problem_id': obj.problem_id,
                'type': obj.problem_type,
                'problem_name': obj.problem_name,
                'tags': obj.tags,
                'ACUser': obj.ac_user,
                'submitter': obj.submitter
            })
            index += 1

    return problem_list


def add_problem(user, status, type, problem_name, description, tags, test_case):
    serial_number = Number("serial_number").obj

    engine.Problem(
        problem_id=serial_number.number,
        problem_status=status,
        problem_type=type,
        problem_name=problem_name,
        description=description,
        owner=user.username,
        tags=tags,
        test_case=test_case).save()

    serial_number.number += 1
    serial_number.save()


def edit_problem(user, problem_id, status, type, problem_name, description,
                 tags, test_case):
    problem = Problem(problem_id).obj

    problem.problem_status = status
    problem.problem_type = type
    problem.problem_name = problem_name
    problem.description = description
    problem.owner = user.username
    problem.tags = tags
    problem.test_case['language'] = test_case['language']
    problem.test_case['fill_in_template'] = test_case['fillInTemplate']
    problem.test_case['cases'] = test_case['cases']

    problem.save()


def delete_problem(problem_id):
    problem = Problem(problem_id).obj
    problem.delete()


def copy_problem(user, problem_id):
    serial_number = Number("serial_number").obj
    problem = Problem(problem_id).obj

    engine.Problem(
        problem_id=serial_number.number,
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
    problem.course_ids.append(course)
    problem.save()
