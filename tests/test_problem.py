import pytest
from tests.base_tester import BaseTester
from mongo import *
import io


def get_file(file):
    with open("./tests/problem_test_case/" + file, 'rb') as f:
        return {'case': (io.BytesIO(f.read()), "test_case.zip")}


class ProblemData:
    def __init__(
        self,
        name,
        status=1,
        type=0,
        description='',
        tags=[],
        test_case_info={
            'language':
            1,
            'fillInTemplate':
            '',
            'cases': [{
                'caseCount': 1,
                'caseScore': 100,
                'memoryLimit': 1000,
                'timeLimit': 1000
            }]
        }):
        self.name = name
        self.status = status
        self.type = type
        self.description = description
        self.tags = tags
        self.test_case = get_file(test_case)
        self.test_case_info = test_case_info


# First problem (offline)
@pytest.fixture(params=[{'name': 'Hello World!'}])
def problem_data(request, client_admin):
    BaseTester.setup_class()
    pd = ProblemData(**request.param)
    # add problem
    rv = client_admin.post('/problem/manage',
                           json={
                               'status': pd.status,
                               'type': pd.type,
                               'problemName': pd.name,
                               'description': pd.description,
                               'tags': pd.tags,
                               'testCaseInfo': pd.test_case_info
                           })
    id = rv.get_json()['data']['problemId']
    rv = client_admin.put(f'/problem/manage/{id}',
                          data=get_file('test_case.zip'))
    yield pd
    BaseTester.teardown_class()


# Online problem
@pytest.fixture(params=[{'name': 'Goodbye health~', 'status': 0}])
def another_problem(request, problem_data):
    return problem_data(request)


class TestProblem(BaseTester):
    # add a problem which status value is invalid (POST /problem/manage)
    def test_add_with_invalid_value(self, client_admin):

        # create a course
        client_admin.post('/course',
                          json={
                              'course': 'math',
                              'teacher': 'admin'
                          })
        client_admin.put('/course/math',
                         json={
                             'TAs': ['admin'],
                             'studentNicknames': {
                                 'student': 'noobs'
                             }
                         })

        request_json_with_invalid_json = {
            'courses': ['math'],
            'status': 2,  # Invalid value
            'type': 0,
            'problemName': 'Test problem name',
            'description': 'Test description.',
            'tags': [],
            'testCaseInfo': {
                'language':
                1,
                'fillInTemplate':
                '',
                'cases': [{
                    'caseCount': 1,
                    'caseScore': 100,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            }
        }
        rv = client_admin.post('/problem/manage',
                               json=request_json_with_invalid_json)
        json = rv.get_json()
        assert rv.status_code == 400
        assert json['status'] == 'err'
        assert json['message'] == 'Invalid or missing arguments.'

    # add a problem which problem name is misssing (POST /problem/manage)
    def test_add_with_missing_argument(self, client_admin):
        request_json_with_missing_argument = {
            'courses': ['math'],
            'status': 1,
            'type': 0,
            #  'problem_name': 'Test problem name',	# missing argument
            'description': 'Test description.',
            'tags': [],
            'testCaseInfo': {
                'language':
                1,
                'fillInTemplate':
                '',
                'cases': [{
                    'caseCount': 1,
                    'caseScore': 100,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            }
        }
        rv = client_admin.post('/problem/manage',
                               json=request_json_with_missing_argument)
        json = rv.get_json()
        assert rv.status_code == 400
        assert json['status'] == 'err'
        assert json['message'] == 'Invalid or missing arguments.'

    # add a offline problem which problem_id = 1 (POST /problem/manage)
    def test_add_offline_problem(self, client_admin):
        request_json = {
            'courses': ['math'],
            'status': 1,
            'type': 0,
            'problemName': 'Offline problem',
            'description': 'Test description.',
            'tags': [],
            'testCaseInfo': {
                'language':
                1,
                'fillInTemplate':
                '',
                'cases': [{
                    'caseCount': 1,
                    'caseScore': 100,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            }
        }
        rv = client_admin.post('/problem/manage', json=request_json)
        json = rv.get_json()
        id = json['data']['problemId']

        rv = client_admin.put(f'/problem/manage/{id}',
                              data=get_file('test_case.zip'))
        json = rv.get_json()

        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Success.'

    # add a online problem which problem_id = 2 (POST /problem/manage)
    def test_add_online_problem(self, client_admin):
        request_json = {
            'courses': ['math'],
            'status': 0,
            'type': 0,
            'problemName': 'Online problem',
            'description': 'Test description.',
            'tags': [],
            'testCaseInfo': {
                'language':
                1,
                'fillInTemplate':
                '',
                'cases': [{
                    'caseCount': 1,
                    'caseScore': 100,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            }
        }
        rv = client_admin.post('/problem/manage', json=request_json)
        json = rv.get_json()
        id = json['data']['problemId']

        rv = client_admin.put(f'/problem/manage/{id}',
                              data=get_file('test_case.zip'))
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Success.'

    # admin get problem list (GET /problem)
    def test_admin_get_problem_list(self, client_admin):
        rv = client_admin.get('/problem?offset=0&count=5')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Success.'
        assert json['data'] == [{
            'problemId': 1,
            'type': 0,
            'problemName': 'Offline problem',
            'tags': [],
            'ACUser': 0,
            'submitter': 0
        }, {
            'problemId': 2,
            'type': 0,
            'problemName': 'Online problem',
            'tags': [],
            'ACUser': 0,
            'submitter': 0
        }]

    # student get problem list (GET /problem)
    def test_student_get_problem_list(self, client_student):
        rv = client_student.get('/problem?offset=0&count=5')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Success.'
        assert json['data'] == [{
            'problemId': 2,
            'type': 0,
            'problemName': 'Online problem',
            'tags': [],
            'ACUser': 0,
            'submitter': 0
        }]

    # admin view offline problem (GET /problem/view/<problem_id>)
    def test_admin_view_offline_problem(self, client_admin):
        rv = client_admin.get('/problem/view/1')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Problem can view.'
        assert json['data'] == {
            'status': 1,
            'type': 0,
            'problemName': 'Offline problem',
            'description': 'Test description.',
            'owner': 'admin',
            'tags': []
        }

    # student view offline problem (GET /problem/view/<problem_id>)
    def test_student_view_offline_problem(self, client_student):
        rv = client_student.get('/problem/view/1')
        json = rv.get_json()
        assert rv.status_code == 403
        assert json['status'] == 'err'
        assert json['message'] == 'Problem cannot view.'

    # student view online problem (GET /problem/view/<problem_id>)
    def test_student_view_online_problem(self, client_student):
        rv = client_student.get('/problem/view/2')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Problem can view.'
        assert json['data'] == {
            'status': 0,
            'type': 0,
            'problemName': 'Online problem',
            'description': 'Test description.',
            'owner': 'admin',
            'tags': []
        }

    # student view problem not exist (GET /problem/view/<problem_id>)
    def test_student_view_problem_not_exist(self, client_student):
        rv = client_student.get('/problem/view/0')
        json = rv.get_json()
        assert rv.status_code == 404
        assert json['status'] == 'err'
        assert json['message'] == 'Problem not exist.'

    # student change the name of a problem (PUT /problem/manage/<problem_id>)
    def test_student_edit_problem(self, client_student):
        request_json = {
            'courses': [],
            'status': 1,
            'type': 0,
            'problemName': 'Offline problem (edit)',
            'description': 'Test description.',
            'tags': [],
            'testCaseInfo': {
                'language':
                1,
                'fillInTemplate':
                '',
                'cases': [{
                    'caseCount': 1,
                    'caseScore': 100,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            }
        }
        rv = client_student.put('/problem/manage/1', json=request_json)
        json = rv.get_json()
        assert rv.status_code == 403
        assert json['status'] == 'err'
        assert json['message'] == 'Insufficient Permissions'

    # non-owner teacher change the name of a problem (PUT /problem/manage/<problem_id>)
    def test_teacher_not_owner_edit_problem(self, client_teacher):
        request_json = {
            'courses': [],
            'status': 1,
            'type': 0,
            'problemName': 'Offline problem (edit)',
            'description': 'Test description.',
            'tags': [],
            'testCaseInfo': {
                'language':
                1,
                'fillInTemplate':
                '',
                'cases': [{
                    'caseCount': 1,
                    'caseScore': 100,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            }
        }
        rv = client_teacher.put('/problem/manage/1', json=request_json)
        json = rv.get_json()
        assert rv.status_code == 403
        assert json['status'] == 'err'
        assert json['message'] == 'Not the owner.'

    # admin change the name of a problem (PUT /problem/manage/<problem_id>)
    def test_admin_edit_problem(self, client_admin):
        request_json = {
            'courses': [],
            'status': 1,
            'type': 0,
            'problemName': 'Offline problem (edit)',
            'description': 'Test description.',
            'tags': [],
            'testCaseInfo': {
                'language':
                1,
                'fillInTemplate':
                '',
                'cases': [{
                    'caseCount': 1,
                    'caseScore': 100,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            }
        }
        rv = client_admin.put('/problem/manage/1', json=request_json)
        json = rv.get_json()
        print(json['data'])
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Success.'

    # admin get information of a problem (GET /problem/manage/<problem_id>)
    def test_admin_manage_problem(self, client_admin):
        rv = client_admin.get('/problem/manage/1')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Success.'
        assert json['data'] == {
            'courses': [],
            'status': 1,
            'type': 0,
            'problemName': 'Offline problem (edit)',
            'description': 'Test description.',
            'tags': [],
            'testCase': {
                'language':
                1,
                'fillInTemplate':
                '',
                'cases': [{
                    'input': ['aaaa\n'],
                    'output': ['bbbb\n'],
                    'caseScore': 100,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            },
            'ACUser': 0,
            'submitter': 0
        }

    # non-owner teacher get information of a problem (GET /problem/manage/<problem_id>)
    def test_teacher_not_owner_manage_problem(self, client_teacher):
        rv = client_teacher.get('/problem/manage/1')
        json = rv.get_json()
        assert rv.status_code == 403
        assert json['status'] == 'err'
        assert json['message'] == 'Not the owner.'

    # student get information of a problem (GET /problem/manage/<problem_id>)
    def test_student_manage_problem(self, client_student):
        rv = client_student.get('/problem/manage/1')
        json = rv.get_json()
        assert rv.status_code == 403
        assert json['status'] == 'err'
        assert json['message'] == 'Insufficient Permissions'

    # student delete problem (DELETE /problem/manage/<problem_id>)
    def test_student_delete_problem(self, client_student):
        rv = client_student.delete('/problem/manage/1')
        json = rv.get_json()
        assert rv.status_code == 403
        assert json['status'] == 'err'
        assert json['message'] == 'Insufficient Permissions'

    # non-owner teacher delete problem (DELETE /problem/manage/<problem_id>)
    def test_teacher_not_owner_delete_problem(self, client_teacher):
        rv = client_teacher.delete('/problem/manage/1')
        json = rv.get_json()
        assert rv.status_code == 403
        assert json['status'] == 'err'
        assert json['message'] == 'Not the owner.'

    # admin delete problem (DELETE /problem/manage/<problem_id>)
    def test_admin_delete_problem(self, client_admin):
        rv = client_admin.delete('/problem/manage/1')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Success.'

    def test_check_delete_successfully(self, client_admin):
        rv = client_admin.get('/problem/view/1')
        json = rv.get_json()
        assert rv.status_code == 404
        assert json['status'] == 'err'
        assert json['message'] == 'Problem not exist.'
