from . import engine

__all__ = ['Problem', 'get_problem_list', 'edit_problem', 'delete_problem']


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

    index = offset - 1
    while True:
        if index > (offset + count - 2):
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


def edit_problem(user, problem_id, status, type, problem_name, description,
                 tags, test_case):
    engine.Problem(
        problem_id=problem_id,
        problem_status=status,
        problem_type=type,
        problem_name=problem_name,
        description=description,
        owner=user.username,
        tags=tags,
        test_case=test_case).save()
    #engine.Problem.objects.order_by('problemName')


def delete_problem(problem_id):
    problem = Problem(problem_id).obj
    problem.delete()
