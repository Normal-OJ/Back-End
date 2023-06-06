import pathlib
from model import *
from mongo import engine, Problem, User
from tests.base_tester import BaseTester

S_NAMES = {
    'student': 'Chika.Fujiwara',  # base.c base.py
    'student-2': 'Nico.Kurosawa',  # base.cpp base_2.py
}


class TestCopyCat(BaseTester):
    # user, course, problem, submission
    def test_copycat(self, forge_client, problem_ids, make_course, submit_once,
                     save_source, tmp_path):
        # create course
        course_name = make_course(
            username="teacher",
            students=S_NAMES,
        ).name
        # create problem
        pid = problem_ids("teacher", 1, True)[0]
        # save source code (for submit_once)
        src_dir = pathlib.Path('tests/src')
        exts = ['.c', '.cpp', '.py', '.pdf']
        for src in src_dir.iterdir():
            if any([not src.suffix in exts, not src.is_file()]):
                continue
            save_source(
                src.stem,
                src.read_bytes(),
                exts.index(src.suffix),
            )
        # submission
        name2code = {
            'student': [('base.c', 0), ('base.py', 2)],
            'student-2': [('base.cpp', 1), ('base_2.py', 2)]
        }
        for name, code in name2code.items():
            for filename, language in code:
                submit_once(
                    name=name,
                    pid=pid,
                    filename=filename,
                    lang=language,
                )
        # change all submissions to status 0 (Accepted)
        engine.Submission.objects.update(status=0)
        # 'post' to send report request /copycat course:course_name problemId: problem_id
        client = forge_client('teacher')
        rv, rv_json, rv_data = self.request(
            client,
            'post',
            '/copycat',
            json={
                'course': course_name,
                'problemId': pid,
                'studentNicknames': {
                    'student': 'student',
                    'student-2': 'student-2',
                },
            },
        )
        assert rv.status_code == 200, rv_json
        # 'get' to get the report url /copycat course:course_name problemId: problem_id
        client = forge_client('teacher')
        rv, rv_json, rv_data = self.request(
            client, 'get', f'/copycat?course={course_name}&problemId={pid}')
        assert rv.status_code == 200, rv_json
        assert isinstance(rv_data, dict), rv_data

    def test_get_report_without_arguments(self, client_teacher):
        rv = client_teacher.get('/copycat')
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json(
        )['message'] == 'missing arguments! (In HTTP GET argument format)'

    def test_get_report_with_invalid_problem_id(self, client_admin):
        rv = client_admin.get('/copycat?course=Public&problemId=bbb')
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'problemId must be integer'

    def test_get_report_without_perm(self, client_student):
        rv = client_student.get('/copycat?course=Public&problemId=123')
        assert rv.status_code == 403, rv.get_json()
        assert rv.get_json()['message'] == 'Forbidden.'

    def test_get_report_with_problem_does_not_exist(self, client_admin):
        rv = client_admin.get('/copycat?course=Public&problemId=87878787')
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'Problem not exist.'

    def test_get_report_with_course_does_not_exist(self, client_admin,
                                                   problem_ids):
        pid = problem_ids("teacher", 1, True)[0]
        rv = client_admin.get(
            f'/copycat?course=CourseDoesNotExist&problemId={pid}')
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'Course not found.'

    def test_get_report_before_request(self, client_admin, problem_ids):
        pid = problem_ids("teacher", 1, True)[0]
        rv = client_admin.get(f'/copycat?course=Public&problemId={pid}')
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json(
        )['message'] == 'No report found. Please make a post request to copycat api to generate a report'

    def test_get_report(self, client_admin, problem_ids, monkeypatch):
        from model import copycat

        def mock_get_report_by_url(_, count=[]):
            count.append(87)
            return f'this is a report url {len(count)}'

        monkeypatch.setattr(copycat, 'get_report_by_url',
                            mock_get_report_by_url)
        pid = problem_ids("teacher", 1, True)[0]
        problem = Problem(pid)
        problem.update(moss_status=2)
        rv = client_admin.get(f'/copycat?course=Public&problemId={pid}')
        assert rv.status_code == 200, rv.get_json()
        assert rv.get_json()['data'] == {
            "cpp_report": 'this is a report url 1',
            "python_report": 'this is a report url 2'
        }

    def test_detect_without_enough_request_args(self, client_teacher):
        rv = client_teacher.post('/copycat', json={})
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json(
        )['message'] == 'missing arguments! (In Json format)'

    def test_detect_with_student_does_not_exist(self, client_teacher,
                                                problem_ids):
        pid = problem_ids("teacher", 1, True)[0]
        rv = client_teacher.post('/copycat',
                                 json={
                                     'course': 'Public',
                                     'problemId': pid,
                                     'studentNicknames': {
                                         'ghost8787': 'studentDoesNotExist',
                                     },
                                 })
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'User: ghost8787 not found.'

    def test_detect_with_empty_student_list(self, client_teacher, problem_ids):
        pid = problem_ids("teacher", 1, True)[0]
        rv = client_teacher.post('/copycat',
                                 json={
                                     'course': 'Public',
                                     'problemId': pid,
                                     'studentNicknames': {},
                                 })
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'Empty student list.'

    def test_detect_without_perm(self, client_student, problem_ids):
        pid = problem_ids("teacher", 1, True)[0]
        rv = client_student.post('/copycat',
                                 json={
                                     'course': 'Public',
                                     'problemId': pid,
                                     'studentNicknames': {
                                         'student': 'student',
                                     },
                                 })
        assert rv.status_code == 403, rv.get_json()
        assert rv.get_json()['message'] == 'Forbidden.'

    def test_detect_with_problem_does_not_exist(self, client_teacher):
        course = engine.Course.objects(teacher="teacher").first()
        rv = client_teacher.post('/copycat',
                                 json={
                                     'course': course.course_name,
                                     'problemId': 87878787,
                                     'studentNicknames': {
                                         'student': 'student',
                                     },
                                 })
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'Problem not exist.'

    def test_detect_with_course_does_not_exist(self, client_admin,
                                               problem_ids):
        pid = problem_ids("teacher", 1, True)[0]
        rv = client_admin.post('/copycat',
                               json={
                                   'course': 'courseDoesNotExist',
                                   'problemId': pid,
                                   'studentNicknames': {
                                       'student': 'student',
                                   },
                               })
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'Course not found.'

    def test_detect_without_config_TESTING(self, client_teacher, problem_ids,
                                           monkeypatch, app):
        from model import copycat

        def mock_get_report_task(user, problem_id, student_dict):
            problem = Problem(problem_id)
            problem.update(
                cpp_report_url=f'cpp report url {user.username} {student_dict}',
                python_report_url=
                f'python report url {user.username} {student_dict}',
                moss_status=2,
            )

        monkeypatch.setattr(copycat, 'get_report_task', mock_get_report_task)
        monkeypatch.setitem(app.config, 'TESTING', False)
        pid = problem_ids("teacher", 1, True)[0]
        course = engine.Course.objects(teacher="teacher").first()
        student_dict = {
            'student': 'student',
        }
        rv = client_teacher.post('/copycat',
                                 json={
                                     'course': course.course_name,
                                     'problemId': pid,
                                     'studentNicknames': student_dict,
                                 })
        assert rv.status_code == 200
        while Problem(pid).moss_status != 2:
            pass
        problem = Problem(pid)
        assert problem.cpp_report_url == f'cpp report url teacher {student_dict}'

    def test_is_valid_url(self):
        from model.copycat import is_valid_url
        assert is_valid_url('https://example.com:8787/abc?def=1234&A_A=Q_Q')

    def test_get_report_task(self, monkeypatch, make_course, problem_ids,
                             save_source, submit_once):
        # create course
        course_name = make_course(
            username="teacher",
            students=S_NAMES,
        ).name
        # create problem
        pid = problem_ids("teacher", 1, True)[0]
        # save source code (for submit_once)
        src_dir = pathlib.Path('tests/src')
        exts = ['.c', '.cpp', '.py', '.pdf']
        for src in src_dir.iterdir():
            if any([not src.suffix in exts, not src.is_file()]):
                continue
            save_source(
                src.stem,
                src.read_bytes(),
                exts.index(src.suffix),
            )
        # submission
        name2code = {
            'student': [('base.c', 0), ('base.py', 2)],
            'student-2': [('base.cpp', 1), ('base_2.py', 2)]
        }
        for name, code in name2code.items():
            for filename, language in code:
                submit_once(
                    name=name,
                    pid=pid,
                    filename=filename,
                    lang=language,
                )
        # change all submissions to status 0 (Accepted)
        engine.Submission.objects.update(status=0)
        user = User('teacher')
        from model.copycat import mosspy

        def mock_moss_send(self):
            return f'https://mock.moss/{self.options["l"]}'

        monkeypatch.setattr(mosspy.Moss, 'send', mock_moss_send)

        def mock_moss_download_report(*args, **kwargs):
            pass

        monkeypatch.setattr(mosspy, 'download_report',
                            mock_moss_download_report)
        from model.copycat import get_report_task
        get_report_task(user, pid, S_NAMES)
        problem = Problem(pid)
        assert problem.moss_status == 2
        assert problem.cpp_report_url == 'https://mock.moss/cc'
        assert problem.python_report_url == 'https://mock.moss/python'

    def test_get_report_task_with_invail_url(self, monkeypatch, problem_ids):
        pid = problem_ids("teacher", 1, True)[0]
        user = User('teacher')
        from model.copycat import mosspy

        def mock_moss_send(self):
            return 'invalid://example.com/'

        monkeypatch.setattr(mosspy.Moss, 'send', mock_moss_send)
        from model.copycat import get_report_task
        get_report_task(user, pid, S_NAMES)
        problem = Problem(pid)
        assert problem.moss_status == 2
        assert problem.cpp_report_url == ''
        assert problem.python_report_url == ''

    def test_get_report_by_url(self, monkeypatch):
        from model.copycat import requests

        class mock_requests_get:

            def __init__(self, text):
                self.text = text

        monkeypatch.setattr(requests, 'get', mock_requests_get)
        from model.copycat import get_report_by_url
        url = 'https://example.com:8787/abc?def=1234&A_A=Q_Q'
        assert get_report_by_url(url) == url

    def test_get_report_by_url_with_invalid_schema(self, monkeypatch):
        from model.copycat import requests

        def mock_requests_get(_):
            raise requests.exceptions.InvalidSchema

        monkeypatch.setattr(requests, 'get', mock_requests_get)
        from model.copycat import get_report_by_url
        url = 'https://example.com:8787/abc?def=1234&A_A=Q_Q'
        assert get_report_by_url(url) == 'No report.'
