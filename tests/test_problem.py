import pytest
from tests.base_tester import BaseTester
from mongo import *


class ProblemData:
    def __init__(self,
                 name,
                 status=1,
                 type=0,
                 description='',
                 tags=[],
                 test_case={}):
        self.name = name
        self.status = status
        self.type = type
        self.description = description
        self.tags = tags
        self.test_case = test_case


@pytest.fixture(params={'name': 'Hello World!'})
def problem_data(request, client_admin):
    BaseTester.setup_class()
    pd = ProblemData(**request.param)
    # add problem
    add_problem(user=client_admin,
                status=pd.status,
                type=pd.type,
                problem_name=pd.name,
                description=pd.description,
                tags=pd.tags,
                test_case=pd.test_case)
    yield pd
    BaseTester.teardown_class()


@pytest.fixture(params={'name': 'Goodbye health~'})
def another_problem(request, problem_data, client_admin):
    return problem_data(request, client_admin)


class TestAddProblem(BaseTester):
    def test_add_with_invalid_value(self, client_admin):
        request_json_with_invalid_json = {
            'status': 2,  # Invalid value
            'type': 0,
            'problem_name': 'Test problem name',
            'description': 'Test description',
            'tags': ['TestTag01', 'TestTag02'],
            'test_case': {}
        }
        rv = client_admin.post('/problem/manage',
                               json=request_json_with_invalid_json)
        json = rv.get_json()
        assert rv.status_code == 400
        assert json['status'] == 'err'
        assert json['message'] == 'Invalid or missing arguments.'

    def test_add_with_missing_argument(self, client_admin):
        request_json_with_missing_argument = {
            'status': 1,
            'type': 0,
            #  'problem_name': 'Test problem name',	# missing argument
            'description': 'Test description',
            'tags': ['TestTag01', 'TestTag02'],
            'test_case': {}
        }
        rv = client_admin.post('/problem/manage',
                               json=request_json_with_missing_argument)
        json = rv.get_json()
        assert rv.status_code == 400
        assert json['status'] == 'err'
        assert json['message'] == 'Invalid or missing arguments.'
