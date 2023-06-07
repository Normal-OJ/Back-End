import io
import pytest
from zipfile import ZipFile
from tests.base_tester import BaseTester
from mongo import *
from tests import utils


def get_file(file):
    with open("./tests/problem_test_case/" + file, 'rb') as f:
        return {'case': (io.BytesIO(f.read()), "test_case.zip")}


def description_dict():
    return {
        'description': 'Test description.',
        'input': '',
        'output': '',
        'hint': '',
        'sampleInput': [],
        'sampleOutput': []
    }


class TestProblem(BaseTester):
    # add a problem which status value is invalid (POST /problem/manage)
    def test_add_with_invalid_value(self, client_admin):
        # create courses
        utils.course.create_course(teacher='admin', name='math')
        utils.course.create_course(teacher='admin', name='English')
        client_admin.put(
            '/course/math',
            json={
                'TAs': ['admin'],
                'studentNicknames': {
                    'student': 'noobs'
                }
            },
        )

        request_json_with_invalid_json = {
            'courses': ['math'],
            'status': 2,  # Invalid value
            'type': 0,
            'problemName': 'Test problem name',
            'description': description_dict(),
            'tags': [],
            'testCaseInfo': {
                'language':
                1,
                'fillInTemplate':
                '',
                'tasks': [{
                    'caseCount': 1,
                    'taskScore': 100,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            }
        }
        rv = client_admin.post(
            '/problem/manage',
            json=request_json_with_invalid_json,
        )
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
            'description': description_dict(),
            'tags': [],
            'testCaseInfo': {
                'language':
                1,
                'fillInTemplate':
                '',
                'tasks': [{
                    'caseCount': 1,
                    'taskScore': 100,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            }
        }
        rv = client_admin.post('/problem/manage',
                               json=request_json_with_missing_argument)
        json = rv.get_json()
        assert json['message'] == 'Invalid or missing arguments.'
        assert rv.status_code == 400
        assert json['status'] == 'err'

    # add a offline problem
    def test_add_offline_problem(self, client_admin):
        request_json = {
            'courses': ['English'],
            'status': 1,
            'type': 0,
            'problemName': 'Offline problem',
            'description': description_dict(),
            'tags': [],
            'testCaseInfo': {
                'language':
                1,
                'fillInTemplate':
                '',
                'tasks': [{
                    'caseCount': 1,
                    'taskScore': 100,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            }
        }
        rv = client_admin.post('/problem/manage', json=request_json)
        json = rv.get_json()
        id = json['data']['problemId']

        rv = client_admin.put(
            f'/problem/manage/{id}',
            data=get_file('default/test_case.zip'),
        )
        json = rv.get_json()
        assert rv.status_code == 200, json
        assert json['status'] == 'ok'
        assert json['message'] == 'Success.'

    # add a online problem
    def test_add_online_problem(self, client_admin):
        request_json = {
            'courses': ['math'],
            'status': 0,
            'type': 0,
            'problemName': 'Online problem',
            'description': description_dict(),
            'tags': [],
            'testCaseInfo': {
                'language':
                1,
                'fillInTemplate':
                '',
                'tasks': [{
                    'caseCount': 1,
                    'taskScore': 100,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            }
        }
        rv = client_admin.post('/problem/manage', json=request_json)
        json = rv.get_json()
        id = json['data']['problemId']

        rv = client_admin.put(
            f'/problem/manage/{id}',
            data=get_file('default/test_case.zip'),
        )
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Success.'

    def test_add_problem_with_empty_course_list(self, client_admin):
        request_json = {
            'courses': [],
        }
        rv = client_admin.post('/problem/manage', json=request_json)
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'No course provided'

    def test_add_problem_with_course_does_not_exist(self, client_admin):
        request_json = {
            'courses': ['CourseDoesNotExist'],
        }
        rv = client_admin.post('/problem/manage', json=request_json)
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'Course not found'

    def test_get_problem_list_with_nan_offest(self, client_admin):
        rv = client_admin.get('/problem?offset=BadOffset')
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'offset and count must be integer!'

    def test_get_problem_list_with_negtive_offest(self, client_admin):
        rv = client_admin.get('/problem?offset=-1')
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'invalid offset'

    # admin get problem list (GET /problem)
    def test_admin_get_problem_list(self, client_admin):
        rv = client_admin.get('/problem?offset=0&count=5')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Success.'
        assert json['data'] == [{
            'problemId': 3,
            'type': 0,
            'problemName': 'Offline problem',
            'status': 1,
            'tags': [],
            'ACUser': 0,
            'submitter': 0,
            'quota': -1,
            'submitCount': 0
        }, {
            'problemId': 4,
            'type': 0,
            'problemName': 'Online problem',
            'status': 0,
            'tags': [],
            'ACUser': 0,
            'submitter': 0,
            'quota': -1,
            'submitCount': 0
        }]

    # admin get problem list with a filter (GET /problem)
    def test_admin_get_problem_list_with_filter(self, client_admin):
        rv = client_admin.get('/problem?offset=0&count=5&course=English')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Success.'
        assert json['data'] == [{
            'problemId': 3,
            'type': 0,
            'problemName': 'Offline problem',
            'status': 1,
            'tags': [],
            'ACUser': 0,
            'submitter': 0,
            'quota': -1,
            'submitCount': 0
        }]

    def test_admin_get_problem_list_with_unexist_params(self, client_admin):
        # unexisted course
        rv, rv_json, rv_data = self.request(
            client_admin,
            'get',
            '/problem?offset=0&count=-1&course=Programming',
        )
        assert rv.status_code == 200
        assert len(rv_data) == 0
        # unexisted tags
        rv, rv_json, rv_data = self.request(
            client_admin,
            'get',
            '/problem?offset=0&count=-1&tags=yo',
        )
        assert rv.status_code == 200
        assert len(rv_data) == 0

    # student get problem list (GET /problem)
    def test_student_get_problem_list(self, client_student):
        rv = client_student.get('/problem?offset=0&count=5')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Success.'
        assert json['data'] == [{
            'problemId': 4,
            'type': 0,
            'problemName': 'Online problem',
            'status': 0,
            'tags': [],
            'ACUser': 0,
            'submitter': 0,
            'quota': -1,
            'submitCount': 0
        }]

    def test_view_problem_from_invalid_ip(self, client_student, monkeypatch):
        from model.problem import Problem
        monkeypatch.setattr(Problem, 'is_valid_ip', lambda *_: False)
        rv = client_student.get('/problem/4')
        assert rv.status_code == 403, rv.get_json()
        assert rv.get_json()['message'] == 'Invalid IP address.'

    def test_view_template_problem(self, client_admin):
        request_json = {
            'courses': ['math'],
            'status': 0,
            'type': 1,
            'problemName': 'Template problem',
            'description': description_dict(),
            'tags': [],
            'testCaseInfo': {
                'language':
                1,
                'fillInTemplate':
                'This is a fill in template.',
                'tasks': [{
                    'caseCount': 1,
                    'taskScore': 100,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            }
        }
        rv = client_admin.post('/problem/manage', json=request_json)
        assert rv.status_code == 200
        rv = client_admin.get('/problem/5')
        assert rv.status_code == 200, rv.get_json()
        assert rv.get_json()['data']['fillInTemplate'] == 'This is a fill in template.'

    # admin view offline problem (GET /problem/<problem_id>)
    def test_admin_view_offline_problem(self, client_admin):
        rv = client_admin.get('/problem/3')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Problem can view.'
        assert json['data'] == {
            'status':
            1,
            'type':
            0,
            'problemName':
            'Offline problem',
            'description':
            description_dict(),
            'owner':
            'admin',
            'tags': [],
            'courses': ['English'],
            'allowedLanguage':
            7,
            'testCase': [
                {
                    'caseCount': 1,
                    'memoryLimit': 1000,
                    'taskScore': 100,
                    'timeLimit': 1000,
                },
            ],
            'quota':
            -1,
            'submitCount':
            0,
            'defaultCode':
            '',
            'highScore':
            0,
        }

    # student view offline problem (GET /problem/<problem_id>)
    def test_student_view_offline_problem(self, client_student):
        rv = client_student.get('/problem/3')
        json = rv.get_json()
        assert rv.status_code == 403
        assert json['status'] == 'err'

    # student view online problem (GET /problem/<problem_id>)
    def test_student_view_online_problem(self, client_student):
        rv = client_student.get('/problem/4')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Problem can view.'
        assert json['data'] == {
            'status':
            0,
            'type':
            0,
            'problemName':
            'Online problem',
            'description':
            description_dict(),
            'owner':
            'admin',
            'tags': [],
            'courses': ['math'],
            'allowedLanguage':
            7,
            'testCase': [
                {
                    'caseCount': 1,
                    'memoryLimit': 1000,
                    'taskScore': 100,
                    'timeLimit': 1000,
                },
            ],
            'quota':
            -1,
            'submitCount':
            0,
            'defaultCode':
            '',
            'highScore':
            0,
        }

    # student view problem not exist (GET /problem/<problem_id>)
    def test_student_view_problem_not_exist(self, client_student):
        rv = client_student.get('/problem/0')
        json = rv.get_json()
        assert rv.status_code == 404
        assert json['status'] == 'err'

    # student change the name of a problem (PUT /problem/manage/<problem_id>)
    def test_student_edit_problem(self, client_student):
        request_json = {
            'courses': [],
            'status': 1,
            'type': 0,
            'problemName': 'Offline problem (edit)',
            'description': description_dict(),
            'tags': [],
            'testCaseInfo': {
                'language':
                1,
                'fillInTemplate':
                '',
                'tasks': [{
                    'caseCount': 1,
                    'taskScore': 100,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            },
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
            'description': description_dict(),
            'tags': [],
            'testCaseInfo': {
                'language':
                1,
                'fillInTemplate':
                '',
                'tasks': [{
                    'caseCount': 1,
                    'taskScore': 100,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            }
        }
        prob = utils.problem.create_problem()
        rv = client_teacher.put(
            f'/problem/manage/{prob.id}',
            json=request_json,
        )
        json = rv.get_json()
        assert rv.status_code == 403
        assert json['status'] == 'err'

    # admin change the name of a problem (PUT /problem/manage/<problem_id>)
    def test_admin_edit_problem_with_non_exist_course(self, client_admin):
        request_json = {
            'courses': ['PE'],
            'status': 1,
            'type': 0,
            'problemName': 'Offline problem (edit)',
            'description': description_dict(),
            'tags': [],
            'testCaseInfo': {
                'language':
                1,
                'fillInTemplate':
                '',
                'tasks': [{
                    'caseCount': 1,
                    'taskScore': 100,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            }
        }
        rv = client_admin.put('/problem/manage/1', json=request_json)
        json = rv.get_json()
        print(json)
        assert rv.status_code == 404

    def test_edit_problem_with_course_does_not_exist(self, client_admin):
        request_json = {
            'courses': ['CourseDoesNotExist'],
            'status': 1,
            'type': 0,
            'problemName': 'Problem with course does not exist',
            'description': description_dict(),
            'tags': [],
            'testCaseInfo': {
                'language':
                1,
                'fillInTemplate':
                '',
                'tasks': [{
                    'caseCount': 1,
                    'taskScore': 100,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            }
        }
        rv = client_admin.put('/problem/manage/3', json=request_json)
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'Course not found.'

    def test_edit_problem_with_name_is_too_long(self, client_admin):
        oo = 'o' * 64
        request_json = {
            'courses': [],
            'status': 1,
            'type': 0,
            'problemName': f'Problem name is t{oo} long!',
            'description': description_dict(),
            'tags': [],
            'testCaseInfo': {
                'language':
                1,
                'fillInTemplate':
                '',
                'tasks': [{
                    'caseCount': 1,
                    'taskScore': 100,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            }
        }
        rv = client_admin.put('/problem/manage/3', json=request_json)
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'Invalid or missing arguments.'

    # admin change the name of a problem (PUT /problem/manage/<problem_id>)
    def test_admin_edit_problem(self, client_admin):
        request_json = {
            'courses': [],
            'status': 1,
            'type': 0,
            'problemName': 'Offline problem (edit)',
            'description': description_dict(),
            'tags': [],
            'testCaseInfo': {
                'language':
                1,
                'fillInTemplate':
                '',
                'tasks': [{
                    'caseCount': 1,
                    'taskScore': 100,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            }
        }
        rv = client_admin.put('/problem/manage/3', json=request_json)
        json = rv.get_json()
        print(json)
        assert rv.status_code == 200
        assert json['status'] == 'ok'

    # admin get information of a problem (GET /problem/manage/<problem_id>)
    def test_admin_manage_problem(self, client_admin):
        pid = 3
        rv = client_admin.get(f'/problem/manage/{pid}')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['data'] == {
            'courses': [],
            'status': 1,
            'type': 0,
            'problemName': 'Offline problem (edit)',
            'description': description_dict(),
            'tags': [],
            'testCase': {
                'language':
                1,
                'fillInTemplate':
                '',
                'tasks': [{
                    'caseCount': 1,
                    'taskScore': 100,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            },
            'ACUser': 0,
            'submitter': 0,
            'allowedLanguage': 7,
            'canViewStdout': Problem(pid).can_view_stdout,
            'quota': -1,
            'submitCount': 0
        }

    def test_update_problem_test_case_with_non_zip_file(self, client_admin):
        rv = client_admin.put('/problem/manage/3', data=get_file('bogay/0000.in'))
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'File is not a zip file'

    def test_update_problem_test_case_with_ambiguous_test_case(self, client_admin, monkeypatch):
        from mongo.problem.problem import SimpleIO, ContextIO
        monkeypatch.setattr(SimpleIO, 'validate', lambda *_: None)
        monkeypatch.setattr(ContextIO, 'validate', lambda *_: None)
        rv = client_admin.put('/problem/manage/3', data=get_file('bogay/test_case.zip'))
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'ambiguous test case format'

    def test_update_problem_test_case_raise_does_not_exist_error(self, client_admin, monkeypatch):
        def mock_update_test_case(*_):
            raise DoesNotExist('Error from mock update_test_case.')
        from mongo.problem import Problem
        monkeypatch.setattr(Problem, 'update_test_case', mock_update_test_case)
        rv = client_admin.put('/problem/manage/3', data=get_file('bogay/test_case.zip'))
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'Error from mock update_test_case.'

    def test_update_problem_test_case_with_unknown_content_type(self, client_admin):
        rv = client_admin.put('/problem/manage/3', headers={'Content-type': 'unknown/content-type'})
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'Unknown content type'
        assert rv.get_json()['data']['contentType'] == 'unknown/content-type'

    def test_student_cannot_get_test_case(self, client_student):
        rv = client_student.get('/problem/3/testcase')
        assert rv.status_code == 403, rv.get_json()
        assert rv.get_json()['message'] == 'Not enough permission'

    def test_admin_update_problem_test_case(self, client_admin):
        # update test case
        rv, rv_json, rv_data = BaseTester.request(
            client_admin,
            'put',
            '/problem/manage/3',
            data=get_file('bogay/test_case.zip'),
        )
        assert rv.status_code == 200, rv_json
        # check content
        rv, rv_json, rv_data = BaseTester.request(
            client_admin,
            'get',
            '/problem/3/testcase',
        )
        assert rv.status_code == 200
        with ZipFile(io.BytesIO(rv.data)) as zf:
            ns = sorted(zf.namelist())
            in_ns = ns[::2]
            out_ns = ns[1::2]
            ns = zip(in_ns, out_ns)
            _io = [(
                zf.read(in_n),
                zf.read(out_n),
            ) for in_n, out_n in ns]
        assert _io == [(b'I AM A TEAPOT\n', b'I AM A TEAPOT\n')], rv_data

    def test_get_testdata_with_invalid_token(self, client):
        rv = client.get('/problem/3/testdata?token=InvalidToken8787')
        assert rv.status_code == 401, rv.get_json()
        assert rv.get_json()['message'] == 'Invalid sandbox token'

    def test_get_testdata(self, client, monkeypatch):
        from model.problem import sandbox
        monkeypatch.setattr(sandbox, 'find_by_token', lambda *_: True)
        rv = client.get('/problem/3/testdata?token=ValidToken')
        assert rv.status_code == 200
        with ZipFile(io.BytesIO(rv.data)) as zf:
            ns = sorted(zf.namelist())
            in_ns = ns[::2]
            out_ns = ns[1::2]
            ns = zip(in_ns, out_ns)
            _io = [(
                zf.read(in_n),
                zf.read(out_n),
            ) for in_n, out_n in ns]
        assert _io == [(b'I AM A TEAPOT\n', b'I AM A TEAPOT\n')]

    def test_get_chechsum_with_invalid_token(self, client):
        rv = client.get('/problem/3/checksum?token=InvalidToken8787')
        assert rv.status_code == 401, rv.get_json()
        assert rv.get_json()['message'] == 'Invalid sandbox token'

    def test_get_chechsum_with_problem_does_not_exist(self, client, monkeypatch):
        from model.problem import sandbox
        monkeypatch.setattr(sandbox, 'find_by_token', lambda *_: True)
        rv = client.get('/problem/878787/checksum?token=SandboxToken')
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'problem [878787] not found'

    def test_get_chechsum(self, client, monkeypatch):
        from model.problem import sandbox
        monkeypatch.setattr(sandbox, 'find_by_token', lambda *_: True)
        rv = client.get('/problem/3/checksum?token=SandboxToken')
        assert rv.status_code == 200, rv.get_json()
        assert rv.get_json()['data'] == 'b80aa4fad6b5dea9a5bca3237ac3ba89'

    def test_get_meta_with_invalid_token(self, client):
        rv = client.get('/problem/3/meta?token=InvalidToken8787')
        assert rv.status_code == 401, rv.get_json()
        assert rv.get_json()['message'] == 'Invalid sandbox token'

    def test_get_meta_with_problem_does_not_exist(self, client, monkeypatch):
        from model.problem import sandbox
        monkeypatch.setattr(sandbox, 'find_by_token', lambda *_: True)
        rv = client.get('/problem/878787/meta?token=SandboxToken')
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'problem [878787] not found'

    def test_get_meta(self, client, monkeypatch):
        from model.problem import sandbox
        monkeypatch.setattr(sandbox, 'find_by_token', lambda *_: True)
        rv = client.get('/problem/3/meta?token=SandboxToken')
        assert rv.status_code == 200, rv.get_json()
        assert rv.get_json()['data'] == {'tasks': [{'caseCount': 1, 'memoryLimit': 1000, 'taskScore': 100, 'timeLimit': 1000}]}

    def test_admin_update_problem_test_case_with_invalid_data(
        self,
        client_admin,
    ):
        prob = utils.problem.create_problem()
        # upload a test case with invalid data
        rv, rv_json, rv_data = BaseTester.request(
            client_admin,
            'put',
            f'/problem/manage/{prob.id}',
            data=get_file('task-exceed/test_case.zip'),
        )
        assert rv.status_code == 400

    # non-owner teacher get information of a problem (GET /problem/manage/<problem_id>)
    def test_teacher_not_owner_manage_problem(self, client_teacher):
        prob = utils.problem.create_problem()
        rv = client_teacher.get(f'/problem/manage/{prob.id}')
        json = rv.get_json()
        assert rv.status_code == 403
        assert json['status'] == 'err'

    # student get information of a problem (GET /problem/manage/<problem_id>)
    def test_student_manage_problem(self, client_student):
        prob = utils.problem.create_problem()
        rv = client_student.get(f'/problem/manage/{prob.id}')
        json = rv.get_json()
        assert rv.status_code == 403
        assert json['status'] == 'err'

    # student delete problem (DELETE /problem/manage/<problem_id>)
    def test_student_delete_problem(self, client_student):
        rv = client_student.delete('/problem/manage/1')
        json = rv.get_json()
        assert rv.status_code == 403
        assert json['status'] == 'err'
        assert json['message'] == 'Insufficient Permissions'

    # non-owner teacher delete problem (DELETE /problem/manage/<problem_id>)
    def test_teacher_not_owner_delete_problem(self, client_teacher):
        prob = utils.problem.create_problem()
        rv = client_teacher.delete(f'/problem/manage/{prob.id}')
        json = rv.get_json()
        assert rv.status_code == 403
        assert json['status'] == 'err'

    # admin delete problem (DELETE /problem/manage/<problem_id>)
    def test_admin_delete_problem(self, client_admin):
        prob = utils.problem.create_problem()
        rv = client_admin.delete(f'/problem/manage/{prob.id}')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert not Problem(prob.id)

    def test_student_cannot_copy_problem(self, forge_client):
        student = utils.user.create_user()
        course = student.courses[-1]
        problem = utils.problem.create_problem(course=course)
        client = forge_client(student.username)
        rv = client.post(
            '/problem/copy',
            json={
                'problemId': problem.problem_id,
            },
        )
        assert rv.status_code == 403

    def test_teacher_cannot_copy_problem_from_other_course(self, forge_client, make_course):
        c_data = make_course('teacher-2')
        client_teacher = forge_client('teacher-2')
        rv = client_teacher.post('/problem/copy', json={'problemId': 3, 'target': c_data.name})
        assert rv.status_code == 403, rv.get_json()
        assert rv.get_json()['message'] == 'Problem can not view.'

    def test_admin_can_copy_problem_from_other_course(self, forge_client):
        admin = utils.user.create_user(role=User.engine.Role.ADMIN)
        course = admin.courses[-1]
        original_problem = utils.problem.create_problem(course=course)
        new_course = utils.course.create_course()
        client_admin = forge_client(admin.username)
        rv, rv_json, rv_data = self.request(
            client_admin,
            'post',
            '/problem/copy',
            json={
                'problemId': original_problem.problem_id,
                'target': new_course.course_name,
            },
        )
        assert rv.status_code == 200, rv_json
        new_problem = Problem(rv_data['problemId'])
        utils.problem.cmp_copied_problem(original_problem, new_problem)

    def test_override_copied_problem_status(self, forge_client):
        admin = utils.user.create_user(role=User.engine.Role.ADMIN)
        original_problem = utils.problem.create_problem(
            status=Problem.engine.Visibility.SHOW)
        client = forge_client(admin.username)
        rv, rv_json, rv_data = self.request(
            client,
            'post',
            '/problem/copy',
            json={
                'problemId': original_problem.problem_id,
                'status': Problem.engine.Visibility.HIDDEN,
            },
        )
        assert rv.status_code == 200, rv_json
        another_problem = Problem(rv_data['problemId'])
        utils.problem.cmp_copied_problem(original_problem, another_problem)

        assert original_problem.problem_status != Problem.engine.Visibility.HIDDEN
        assert another_problem.problem_status == Problem.engine.Visibility.HIDDEN

    def test_student_cannot_copy_problem(self, forge_client):
        student = utils.user.create_user()
        course = student.courses[-1]
        problem = utils.problem.create_problem(course=course)
        client = forge_client(student.username)
        rv = client.post(
            '/problem/copy',
            json={
                'problemId': problem.problem_id,
            },
        )
        assert rv.status_code == 403

    def test_admin_can_copy_problem_from_other_course(self, forge_client):
        admin = utils.user.create_user(role=User.engine.Role.ADMIN)
        course = admin.courses[-1]
        original_problem = utils.problem.create_problem(course=course)
        new_course = utils.course.create_course()
        client_admin = forge_client(admin.username)
        rv, rv_json, rv_data = self.request(
            client_admin,
            'post',
            '/problem/copy',
            json={
                'problemId': original_problem.problem_id,
                'target': new_course.course_name,
            },
        )
        assert rv.status_code == 200, rv_json
        new_problem = Problem(rv_data['problemId'])
        utils.problem.cmp_copied_problem(original_problem, new_problem)

    def test_override_copied_problem_status(self, forge_client):
        admin = utils.user.create_user(role=User.engine.Role.ADMIN)
        original_problem = utils.problem.create_problem(
            status=Problem.engine.Visibility.SHOW)
        client = forge_client(admin.username)
        rv, rv_json, rv_data = self.request(
            client,
            'post',
            '/problem/copy',
            json={
                'problemId': original_problem.problem_id,
                'status': Problem.engine.Visibility.HIDDEN,
            },
        )
        assert rv.status_code == 200, rv_json
        another_problem = Problem(rv_data['problemId'])
        utils.problem.cmp_copied_problem(original_problem, another_problem)

        assert original_problem.problem_status != Problem.engine.Visibility.HIDDEN
        assert another_problem.problem_status == Problem.engine.Visibility.HIDDEN

    def test_publish_without_perm(self, forge_client):
        client_teacher = forge_client('teacher-2')
        rv = client_teacher.post('/problem/publish', json={'problemId': 3})
        assert rv.status_code == 403, rv.get_json()
        assert rv.get_json()['message'] == 'Not the owner.'

    def test_publish(self, client_admin):
        rv = client_admin.post('/problem/publish', json={'problemId': 3})
        assert rv.status_code == 200


from mongo import Problem


class TestMongoProblem(BaseTester):

    def test_detailed_info_of_problem_does_not_exist(self):
        problem = Problem(878787)
        assert problem.detailed_info() == {}

    def test_detailed_info_with_nested_value(self, problem_ids):
        problem = Problem(problem_ids('teacher', 1)[0])
        assert problem.detailed_info(nested__info='testCase__language') == {'nested': {'info': 2}}
    
    def test_negtive_language_is_not_allowed(self, problem_ids):
        problem = Problem(problem_ids('teacher', 1)[0])
        assert problem.allowed(-1) == False
    
    def test_high_score_with_cache(self, problem_ids, monkeypatch):
        from mongo.problem.problem import RedisCache
        monkeypatch.setattr(RedisCache, 'get', lambda *_: b'87')
        problem = Problem(problem_ids('teacher', 1)[0])
        assert problem.get_high_score(user='student') == 87

    def test_get_problem_list_with_course_does_not_exist(self, problem_ids):
        problem = Problem(problem_ids('teacher', 1)[0])
        plist = problem.get_problem_list('teacher', course='CourseDoesNotExist')
        assert plist == []
    
    def test_edit_problem_without_100_scores_in_total(self, problem_ids):
        request_json = {
            'courses': [],
            'status': 1,
            'type': 0,
            'problem_name': 'Problem title',
            'description': description_dict(),
            'tags': [],
            'test_case_info': {
                'language':
                1,
                'fillInTemplate':
                '',
                'tasks': [{
                    'caseCount': 1,
                    'taskScore': 87,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            }
        }
        pid = problem_ids('teacher', 1)[0]
        with pytest.raises(ValueError):
            Problem.edit_problem(User('teacher'), pid, **request_json)

    def test_copy_problem(self, problem_ids):
        pid = problem_ids('teacher', 1)[0]
        teacher = User('teacher-2')
        Problem.copy_problem(teacher, pid)
        new_problem = Problem.get_problem_list(teacher)[-1]
        assert Problem(pid).problem_name == new_problem.problem_name


from mongo.problem.test_case import IncludeDirectory


class TestIncludeDirectory(BaseTester):

    def test_validate_with_none_test_case(self):
        rule = IncludeDirectory(Problem(87), 'path/to/include/dir')
        with pytest.raises(BadTestCase) as err:
            rule.validate(None)
        assert str(err.value) == 'test case is None'
    
    def test_validate_with_path_does_not_exist(self):
        rule = IncludeDirectory(Problem(87), 'path/does/not/exist', False)
        with pytest.raises(BadTestCase) as err:
            zip = 'tests/problem_test_case/bogay/test_case.zip'
            rule.validate(zip)
        assert str(err.value) == 'directory path/does/not/exist does not exist'

    def test_validate_with_non_directory_path(self):
        file = '0000.in'
        rule = IncludeDirectory(Problem(87), file, False)
        with pytest.raises(BadTestCase) as err:
            zip = 'tests/problem_test_case/bogay/test_case.zip'
            rule.validate(zip)
        assert str(err.value) == f'{file} is not a directory'

    def test_validate(self):
        dir = 'dir/'
        rule = IncludeDirectory(Problem(87), dir, False)
        zip = 'tests/problem_test_case/alardutp/test_case.zip'
        assert rule.validate(zip)


from mongo.problem.test_case import SimpleIO


class TestSimpleIO(BaseTester):

    def test_validate_with_none_test_case(self):
        rule = SimpleIO(Problem(87))
        with pytest.raises(BadTestCase) as err:
            rule.validate(None)
        assert str(err.value) == 'test case is None'
    
    def test_validate_with_excludes_raise_bad_test_case_error(self):
        zip = 'tests/problem_test_case/bogay/test_case.zip'
        rule = SimpleIO(Problem(87), ['0000'])
        with pytest.raises(BadTestCase) as err:
            rule.validate(zip)
        assert str(err.value) == 'I/O data not equal to meta provided'


from mongo.problem.test_case import ContextIO


class TestContextIO(BaseTester):

    def test_validate_with_none_test_case(self):
        rule = ContextIO(Problem(87))
        with pytest.raises(BadTestCase) as err:
            rule.validate(None)
        assert str(err.value) == 'test case is None'
    
    def test_validate_with_test_case_is_not_dir(self, monkeypatch):
        zip = 'tests/problem_test_case/bogay/test_case.zip'
        rule = ContextIO(Problem(87))
        from mongo.problem.test_case import zipfile
        monkeypatch.setattr(zipfile.Path, 'exists', lambda _: True)
        monkeypatch.setattr(zipfile.Path, 'is_dir', lambda _: False)
        with pytest.raises(BadTestCase) as err:
            rule.validate(zip)
        assert str(err.value) == 'test-case is not a directory'
    
    def test_validate_with_extra_test_case_dir(self, problem_ids):
        pid = problem_ids('teacher', 1)[0]
        rule = ContextIO(Problem(pid))
        zip = 'tests/problem_test_case/alardutp/test_case.zip'
        with pytest.raises(BadTestCase) as err:
            rule.validate(zip)
        assert str(err.value) == 'extra test case directory found: extra'
