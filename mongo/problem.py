from . import engine


class Problem:
    def __init__(self, problem_name):
        self.problem_name = problem_name

    @property
    def obj(self):
        try:
            obj = engine.Problem.objects.get(problem_name=self.problem_name)
        except:
            return None
        return obj
