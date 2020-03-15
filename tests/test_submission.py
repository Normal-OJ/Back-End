import pytest
import os
import itertools
import pathlib
from pprint import pprint

from mongo import *
from mongo import engine
from tests.base_tester import BaseTester, random_string
from tests.test_homework import CourseData

A_NAMES = [
    'teacher',
    'admin',
    'teacher-2',
]
S_NAMES = {
    'student': 'Chika.Fujiwara',
    'student-2': 'Nico.Kurosawa',
}


@pytest.fixture(autouse=True)
def submission_testcase_setup(
    save_source,
    make_course,
    tmp_path,
):
    BaseTester.setup_class()
    # save base source
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
    # create courses
    for name in A_NAMES:
        make_course(
            username=name,
            students=S_NAMES,
        )
    yield
    BaseTester.teardown_class()


class SubmissionTester:
    # all submission count
    init_submission_count = 8
    submissions = []


class TestUserGetSubmission(SubmissionTester):
    @classmethod
    @pytest.fixture(autouse=True)
    def on_create(cls, submit, problem_ids):
        # create 2 problem for each teacher or admin
        pids = [problem_ids(name, 2, True) for name in A_NAMES]
        pids = itertools.chain(*pids)
        # get online problem ids
        pids = [pid for pid in pids if Problem(pid).obj.problem_status == 0]
        # get a course name
        cls.courses = [Problem(pid).obj.courses[0].course_name for pid in pids]

        pids = itertools.cycle(pids)
        names = S_NAMES.keys()
        names = itertools.cycle(names)
        # create submissions
        cls.submissions = submit(
            names,
            pids,
            cls.init_submission_count,
        )
        # check submission count
        assert len([*itertools.chain(*cls.submissions.values())
                    ]) == cls.init_submission_count, cls.submissions
        yield
        # clear
        cls.submissions = []

    def test_normal_get_submission_list(self, forge_client):
        client = forge_client('student')
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'get',
            f'/submission?offset=0&count={self.init_submission_count}',
        )

        pprint(rv_json)

        assert rv.status_code == 200
        assert 'unicorn' in rv_data
        assert len(rv_data['submissions']) == self.init_submission_count

        excepted_field_names = {
            'submissionId',
            'problemId',
            'user',
            'status',
            'score',
            'runTime',
            'memoryUsage',
            'languageType',
            'timestamp',
        }

        for s in rv_data['submissions']:
            assert len(excepted_field_names - set(s.keys())) == 0

    @pytest.mark.parametrize('offset, count', [
        (0, 1),
        (SubmissionTester.init_submission_count // 2, 1),
    ])
    def test_get_truncated_submission_list(self, forge_client, offset, count):
        client = forge_client('student')
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'get',
            f'/submission/?offset={offset}&count={count}',
        )

        pprint(rv_json)

        assert rv.status_code == 200
        assert len(rv_data['submissions']) == 1

    def test_get_submission_list_with_maximun_offset(self, forge_client):
        client = forge_client('student')
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'get',
            f'/submission/?offset={SubmissionTester.init_submission_count}&count=1',
        )

        print(rv_json)

        assert rv.status_code == 400

    def test_get_all_submission(self, forge_client):
        client = forge_client('student')
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'get',
            '/submission/?offset=0&count=-1',
        )

        pprint(rv_json)

        assert rv.status_code == 200
        # only get online submissions
        assert len(rv_data['submissions']) == self.init_submission_count

        offset = self.init_submission_count // 2
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'get',
            f'/submission/?offset={offset}&count=-1',
        )

        pprint(rv_json)

        assert rv.status_code == 200
        assert len(rv_data['submissions']) == (self.init_submission_count -
                                               offset)

    def test_get_submission_count(self, forge_client):
        client = forge_client('student')
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'get',
            '/submission/count',
        )

        assert rv.status_code == 200, rv_json
        assert rv_data['count'] == self.init_submission_count, rv_data

    def test_get_submission_list_over_db_size(self, forge_client):
        client = forge_client('student')
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'get',
            f'/submission/?offset=0&count={self.init_submission_count ** 2}',
        )

        pprint(rv_json)

        assert rv.status_code == 200
        assert len(rv_data['submissions']) == self.init_submission_count

    def test_get_submission_without_login(self, client):
        for _id in self.submissions.values():
            rv = client.get(f'/submission/{_id}')
            pprint(rv.get_json())
            assert rv.status_code == 403, client.cookie_jar

    def test_normal_user_get_others_submission(self, forge_client):
        '''
        let student get all other's submission
        '''
        ids = []
        for name in (set(S_NAMES) - set(['student'])):
            ids.extend(self.submissions[name])

        client = forge_client('student')
        for _id in ids:
            rv, rv_json, rv_data = BaseTester.request(
                client,
                'get',
                f'/submission/{_id}',
            )
            assert rv.status_code == 200
            assert 'code' not in rv_data, Submission(_id).user.username

    def test_get_self_submission(self, client_student):
        ids = self.submissions['student']
        pprint(ids)

        for _id in ids:
            rv, rv_json, rv_data = BaseTester.request(
                client_student,
                'get',
                f'/submission/{_id}',
            )
            assert rv.status_code == 200
            # user can view self code
            assert 'code' in rv_data

        pprint(rv_data)

        # check for fields
        except_fields = {
            'problemId',
            'languageType',
            'timestamp',
            'status',
            'tasks',
            'score',
            'runTime',
            'memoryUsage',
            'code',
        }
        missing_field = except_fields - set(rv_data.keys())
        print(missing_field)
        assert len(missing_field) == 0

    @pytest.mark.parametrize('offset, count', [(None, 1), (0, None),
                                               (None, None)])
    def test_get_submission_list_with_missing_args(self, forge_client, offset,
                                                   count):
        client = forge_client('student')
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'get',
            f'/submission/?offset={offset}&count={count}',
        )
        assert rv.status_code == 400

    @pytest.mark.parametrize('offset, count', [(-1, 2), (2, -2)])
    def test_get_submission_list_with_out_ranged_negative_arg(
        self,
        forge_client,
        offset,
        count,
    ):
        client = forge_client('student')
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'get',
            f'/submission/?offset={offset}&count={count}',
        )
        assert rv.status_code == 400

    @pytest.mark.parametrize(
        'key, except_val',
        [
            ('status', -1),
            ('languageType', 0),
            # TODO: need special test for username field
            # TODO: test for submission id filter
            # TODO: test for problem id filter
        ])
    def test_get_submission_list_by_filter(
        self,
        forge_client,
        key,
        except_val,
    ):
        client = forge_client('student')
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'get',
            f'/submission/?offset=0&count=-1&{key}={except_val}',
        )

        pprint(rv_json)

        assert rv.status_code == 200
        assert len(rv_data['submissions']) != 0
        assert all(map(lambda x: x[key] == except_val,
                       rv_data['submissions'])) == True

    def test_get_submission_list_by_course_filter(
        self,
        forge_client,
    ):
        client = forge_client('student')
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'get',
            f'/submission/?offset=0&count=-1&course=aaa',
        )

        assert rv.status_code == 200
        assert len(rv_data['submissions']) == 0

        rv, rv_json, rv_data = BaseTester.request(
            client,
            'get',
            f'/submission/?offset=0&count=-1&course={self.courses[0]}',
        )

        assert rv.status_code == 200
        assert len(rv_data['submissions']) == 4


class TestTeacherGetSubmission(SubmissionTester):
    pids = []

    @classmethod
    @pytest.fixture(autouse=True)
    def on_create(cls, problem_ids, submit):
        # make submissions
        cls.pids = []
        for name in A_NAMES:
            cls.pids.extend(problem_ids(name, 3, True, -1))
        names = itertools.cycle(['admin'])
        submit(
            names,
            itertools.cycle(cls.pids),
            cls.init_submission_count,
        )

    def test_teacher_can_get_offline_submission(self, forge_client):
        client = forge_client('teacher')
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'get',
            '/submission?offset=0&count=-1',
        )
        except_count = len(engine.Submission.objects)
        assert len(rv_data['submissions']) == except_count, rv_json

    def test_teacher_can_view_students_source(self, forge_client):
        teacher_name = 'teacher'
        client = forge_client(teacher_name)
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'get',
            '/submission?offset=0&count=-1',
        )

        problems = [Problem(pid).obj for pid in self.pids]
        problems = {p.problem_id for p in problems if p.owner == teacher_name}
        submission_ids = [
            s['submissionId'] for s in rv_data['submissions']
            if s['problemId'] in problems
        ]

        for _id in submission_ids:
            rv, rv_json, rv_data = BaseTester.request(
                client,
                'get',
                f'/submission/{_id}',
            )
            assert 'code' in rv_data, rv_data


class TestCreateSubmission(SubmissionTester):
    pid = None

    @classmethod
    @pytest.fixture(autouse=True)
    def on_create(cls, problem_ids):
        cls.pid = problem_ids('teacher', 1, True)[0]
        yield
        cls.pid = None

    def post_payload(self, language=0, problem_id=None):
        return {
            'problemId': problem_id or self.pid,
            'languageType': language,
        }

    @pytest.mark.parametrize(
        'lang, ext',
        zip(
            range(3),
            ['.c', '.cpp', '.py'],
        ),
    )
    def test_normal_submission(
        self,
        forge_client,
        get_source,
        lang,
        ext,
    ):
        client = forge_client('student')

        # first claim a new submission to backend server
        # recieve response, which include the submission id
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'post',
            '/submission',
            json=self.post_payload(lang),
        )

        assert rv.status_code == 200, rv_json
        assert sorted(rv_data.keys()) == sorted(['submissionId'])

        # second, post my source code to server. after that,
        # my submission will send to sandbox to be judged
        files = {
            'code': (
                get_source(f'base{ext}'),
                'code',
            )
        }
        rv = client.put(
            f'/submission/{rv_data["submissionId"]}',
            data=files,
        )
        rv_json = rv.get_json()

        pprint(f'put: {rv_json}')

        assert rv.status_code == 200

    def test_user_db_submission_field_content(
        self,
        forge_client,
    ):
        # get submission length
        before_len = len(User('student').submissions)
        # create a submission
        client = forge_client('student')
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'post',
            '/submission',
            json=self.post_payload(),
        )

        # get user's data
        user = User('student')
        pprint(user.to_mongo())
        pprint(rv_json)

        assert user
        assert rv.status_code == 200
        assert len(user.submissions) == before_len + 1

    def test_wrong_language_type(
        self,
        forge_client,
        get_source,
    ):
        client = forge_client('student')
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'post',
            '/submission',
            json=self.post_payload(2),  # 2 for py3
        )
        files = {
            'code': (
                get_source('base.c'),
                'code',
            )
        }
        rv = client.put(
            f'/submission/{rv_data["submissionId"]}',
            data=files,
        )
        rv_json = rv.get_json()
        # file extension doesn't equal we claimed before
        assert rv.status_code == 400, rv_json

    def test_empty_source(
        self,
        forge_client,
        get_source,
    ):
        client = forge_client('student')
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'post',
            '/submission',
            json=self.post_payload(),
        )

        files = {'code': (None, 'code')}
        rv = client.put(
            f'/submission/{rv_data["submissionId"]}',
            data=files,
        )
        rv_json = rv.get_json()

        assert rv.status_code == 400, rv_json

    @pytest.mark.parametrize(
        'lang, ext',
        zip(
            range(3),
            ['.c', '.cpp', '.py'],
        ),
    )
    def test_no_source_upload(
        self,
        forge_client,
        lang,
        ext,
        get_source,
    ):
        client = forge_client('student')
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'post',
            '/submission',
            json=self.post_payload(),
        )

        pprint(f'post: {rv_json}')

        files = {'c0d3': (get_source(f'base{ext}'), 'code')}
        rv = client.put(
            f'/submission/{rv_data["submissionId"]}',
            data=files,
        )
        rv_json = rv.get_json()

        pprint(f'put: {rv_json}')

        assert rv.status_code == 400

    def test_submit_to_others(
        self,
        forge_client,
        get_source,
    ):
        client = forge_client('student')
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'post',
            '/submission',
            json=self.post_payload(),
        )
        assert rv.status_code == 200, rv_json

        client = forge_client('student-2')
        submission_id = rv_data['submissionId']
        files = {
            'code': (
                get_source('base.cpp'),
                'd1w5q6dqw',
            )
        }
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'put',
            f'/submission/{submission_id}',
            data=files,
        )

        assert rv.status_code == 403, rv_json

    def test_reach_rate_limit(self, client_student):
        # set rate limit to 5 sec
        Submission.config().update(rate_limit=5)
        post_json = self.post_payload(1)
        client_student.post(
            '/submission',
            json=post_json,
        )

        for _ in range(10):
            rv = client_student.post(
                '/submission',
                json=post_json,
            )

            assert rv.status_code == 429, rv.get_json()
        # recover rate limit
        Submission.config().update(rate_limit=0)

    def test_normally_rejudge(self, forge_client, submit_once):
        submission_id = submit_once('student', self.pid, 'base.c', 0)
        # make a fake AC submission
        Submission(submission_id).update(status=0)
        client = forge_client('admin')
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'get',
            f'/submission/{submission_id}/rejudge',
        )
        assert rv.status_code == 200, rv_json

    def test_reach_file_size_limit(
        self,
        forge_client,
        save_source,
        get_source,
    ):
        save_source('big', b'a' * (10**7) + b'<(_ _)>', 0)
        client = forge_client('student')
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'post',
            f'/submission',
            json=self.post_payload(),
        )
        submission_id = rv_data['submissionId']
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'put',
            f'/submission/{submission_id}',
            data={
                'code': {
                    get_source('big.c'),
                    'aaaaa',
                },
            },
        )
        assert rv.status_code == 400

    def test_submit_to_non_participate_contest(self, client_student):
        pass

    def test_submit_outside_when_user_in_contest(self, client_student):
        '''
        submit a problem outside the contest when user is in contest
        '''
        pass

    def test_submit_to_not_enrolled_course(self, client_student):
        pass


class TestHandwrittenSubmission(SubmissionTester):
    pid = None

    @classmethod
    @pytest.fixture(autouse=True)
    def on_create(cls, problem_ids):
        cls.pid = problem_ids('teacher', 1, True, 0, 2)[0]
        yield
        cls.pid = None

    def test_handwritten_submission(self, client_student, client_teacher):
        # first claim a new submission to backend server
        post_json = {'problemId': self.pid, 'languageType': 3}
        # recieve response, which include the submission id
        # and a token to validate next request
        rv, rv_json, rv_data = BaseTester.request(
            client_student,
            'post',
            '/submission',
            json=post_json,
        )

        pprint(f'post: {rv_json}')

        assert rv.status_code == 200, can_view(
            User('stucent'),
            Problem(pid).obj,
        )
        assert sorted(rv_data.keys()) == sorted(['submissionId'])

        self.submission_id = rv_data["submissionId"]

        # second, post my homework to server. after that,
        # my submission will be judged by my requests later
        pdf_dir = pathlib.Path('tests/handwritten/main.pdf.zip')
        files = {
            'code': (
                open(pdf_dir, 'rb'),
                'code',
            )
        }
        rv = client_student.put(
            f'/submission/{self.submission_id}',
            data=files,
        )
        rv_json = rv.get_json()

        pprint(f'put: {rv_json}')

        assert rv.status_code == 200

        # third, read the student's upload

        rv = client_student.get(
            f'/submission/{self.submission_id}/pdf/upload', )

        assert rv.status_code == 200

        # fourth, grade the submission

        rv = client_teacher.put(
            f'/submission/{self.submission_id}/grade',
            json={'score': 87},
        )

        json = rv.get_json()
        pprint(f'grade: {json}')
        assert rv.status_code == 200

        # fifth, send a wrong file to the submission

        pdf_dir = pathlib.Path('tests/src/base.c')
        files = {
            'comment': (
                open(pdf_dir, 'rb'),
                'comment',
            )
        }
        rv = client_teacher.put(
            f'/submission/{self.submission_id}/comment',
            data=files,
        )

        assert rv.status_code == 400

        # sixth, send the comment.pdf to the submission

        pdf_dir = pathlib.Path('tests/handwritten/comment.pdf')
        files = {
            'comment': (
                open(pdf_dir, 'rb'),
                'comment',
            )
        }
        rv = client_teacher.put(
            f'/submission/{self.submission_id}/comment',
            data=files,
        )

        assert rv.status_code == 200

        # seventh, get the submission info

        rv = client_student.get(f'/submission/{self.submission_id}', )

        json = rv.get_json()
        assert rv.status_code == 200
        assert json['data']['score'] == 87

        # eighth, get the submission comment

        rv = client_student.get(
            f'/submission/{self.submission_id}/pdf/comment', )

        assert rv.status_code == 200

        # submit again will only replace the old one

        rv, rv_json, rv_data = BaseTester.request(
            client_student,
            'post',
            '/submission',
            json=post_json,
        )
        self.submission_id = rv_data["submissionId"]

        pdf_dir = pathlib.Path('tests/handwritten/main.pdf.zip')
        files = {
            'code': (
                open(pdf_dir, 'rb'),
                'code',
            )
        }
        rv = client_student.put(
            f'/submission/{self.submission_id}',
            data=files,
        )
        rv_json = rv.get_json()

        assert rv.status_code == 200

        # see if the student and thw teacher can get the submission

        rv = client_student.get(f'/submission?offset=0&count=-1')

        json = rv.get_json()
        print(json['data'])
        assert len(json['data']['submissions']) == 1
        assert rv.status_code == 200

        rv = client_teacher.get(f'/submission?offset=0&count=-1')

        json = rv.get_json()
        print(json['data'])
        assert len(json['data']['submissions']) == 1
        assert rv.status_code == 200

    @pytest.mark.parametrize(
        'user_a, user_b, status_code',
        [
            # student can view self score
            ('student', 'student', 200),
            # normal user can not view other's score
            ('student-2', 'student', 403),
            # teacher can view student's score
            ('student-2', 'teacher', 200),
            # also the admin
            ('student-2', 'admin', 200),
        ],
    )
    def test_handwritten_submission_score_visibility(
        self,
        forge_client,
        submit_once,
        user_a,
        user_b,
        status_code,
    ):
        '''
        test whether a `user_b` can view the `user_a`'s handwritten submission score
        '''
        submission_id = submit_once(user_a, self.pid, 'main.pdf', 3)
        client = forge_client(user_b)
        rv, rv_json, rv_data = BaseTester.request(
            client,
            'get',
            f'/submission/{submission_id}',
        )
        assert rv.status_code == status_code, rv_json


class TestSubmissionConfig(SubmissionTester):
    def test_get_config(self, client_admin):
        rv = client_admin.get(f'/submission/config')
        json = rv.get_json()
        assert rv.status_code == 200

    def test_edit_config(self, client_admin):
        rv = client_admin.put(
            f'/submission/config',
            json={
                'rateLimit':
                10,
                'sandboxInstances': [{
                    'name': 'Test',
                    'url': 'http://sandbox:6666',
                    'token': 'AAAAA',
                }]
            },
        )
        json = rv.get_json()
        assert rv.status_code == 200, json
        rv = client_admin.get(f'/submission/config', )
        json = rv.get_json()
        assert rv.status_code == 200, json
        assert json['data'] == {
            'rateLimit':
            10,
            'sandboxInstances': [{
                'name': 'Test',
                'url': 'http://sandbox:6666',
                'token': 'AAAAA',
            }]
        }
