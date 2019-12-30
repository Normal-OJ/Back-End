import pytest
import os
import itertools
import random

from zipfile import ZipFile
from datetime import datetime
from pprint import pprint

from mongo import *
from mongo import engine
from tests.base_tester import BaseTester, random_string
from tests.test_homework import CourseData

from model.submission import assign_token, verify_token, tokens


def random_problem_data(username=None):
    s = random_string()
    return {
        'courses':
        [engine.Course.objects.filter(
            teacher=username)[0].course_name] if username else [],
        'status':
        random.randint(0, 1),
        'type':
        0,
        'description':
        '',
        'tags': ['test'],
        'problemName':
        f'prob {s}',
        'testCase': {
            'language':
            2,
            'fillInTemplate':
            '',
            'cases': [
                {
                    'input': s,
                    'output': s,
                    'caseScore': 100,
                    'memoryLimit': 32768,
                    'timeLimit': 1000,
                },
            ],
        }
    }


class TestSubmissionUtils:
    def test_token_assign(self):
        token = assign_token('8888')
        assert token is not None
        assert verify_token('8888', token) is True


class SubmissionTester(BaseTester):
    init_submission_count = 32
    submissions = []
    offline_submissions = []

    source = {
        'c11': {
            'lang': 0,
            'code': \
            '#include <stdio.h>\n'
            '\n'
            'int main()\n'
            '{\n'
            '    puts("Hello, world!");\n'
            '    return 0;\n'
            '}\n',
            'ext': '.c',
            'zip': None
        },
        'cpp11': {
            'lang': 1,
            'code': \
            '#include <iostream>\n'
            'using namespace std;\n'
            '\n'
            'int main()\n'
            '{\n'
            '    cout << "Hello, world!\\n";\n'
            '    return 0;\n'
            '}\n',
            'ext': '.cpp',
            'zip': None
        },
        'python3': {
            'lang': 2,
            'code': 'print(\'Hello, world!\')\n',
            'ext': '.py',
            'zip': None
        }
    }

    @classmethod
    def lang_to_code(cls, lang: str):
        '''
        convert language to corresponded code
        '''
        try:
            return ['c11', 'cpp11', 'python3'].index(lang)
        except ValueError:
            print(f'Unsupport language {lang}')
            return None

    @classmethod
    def prepare_submission(cls):
        for src in cls.source.values():
            with open(cls.path / f'main{src["ext"]}', 'w') as f:
                f.write(src['code'])

        for k, v in cls.source.items():
            zip_path = cls.path / f'{k}.zip'
            with ZipFile(zip_path, 'w') as f:
                f.write(cls.path / f'main{src["ext"]}',
                        arcname=f'main{src["ext"]}')
            v['zip'] = open(zip_path, 'rb')

    @classmethod
    def zipped_source(cls, source, lang, ext=None):
        '''
        get user source codes
        currently only support one file.

        Args:
            source: source code
            lang: programming language, only accept {'c11', 'cpp11', 'python3'}
            ext: main script extension want to use, if None, decided by lang

        Returns:
            a zip file contains source code
        '''
        lang = cls.lang_to_code(lang)
        if not ext:
            ext = ['.c', '.cpp', '.py'][lang]

        import hashlib

        # write source
        name = hashlib.sha256(source).hexdigest()
        with open(cls.path / name, 'w') as f:
            f.write(source)
        zip_path = cls.path / f'{name}.zip'
        with ZipFile(zip_path, 'w') as f:
            f.write(name, arcname=f'main{ext}')

        return open(zip_path, 'rb')

    @classmethod
    @pytest.fixture(autouse=True)
    def setup_class(cls, tmp_path, problem_ids, make_course):
        super().setup_class()

        # prepare problem data
        SubmissionTester.path = tmp_path
        cls.prepare_submission()

        from model import submission
        # use tmp dir to save user source code
        submission.SOURCE_PATH = tmp_path / submission.SOURCE_PATH
        submission.SOURCE_PATH = submission.SOURCE_PATH.absolute()
        submission.SOURCE_PATH.mkdir(exist_ok=True)
        # replace judge url with test route
        submission.JUDGE_URL = 'https://www.csie.ntnu.edu.tw?magic='

        # insert some submission into db
        cls.submissions = []
        cls.offline_submissions = []

        # funtionc for create submissions
        def submit(count, names, pids):
            for _, name, pid in zip('x' * count, names, pids):
                lang = 0
                now = datetime.now()
                s = Submission.add(
                    problem_id=pid,
                    username=name,
                    lang=lang,
                    timestamp=now,
                )
                status = engine.Problem.objects.get(
                    problem_id=pid).problem_status
                submission = {
                    'submissionId': s.id,
                    'problemId': pid,
                    'problemStatus': status,
                    'username': name,
                    'lang': lang,
                    'timestamp': now
                }

                if status == 0:
                    cls.submissions.append(submission)
                else:
                    cls.offline_submissions.append(submission)

        a_names = [
            'teacher',
            'admin',
            'teacher-2',
        ]
        s_names = {
            'student': 'Chika.Fujiwara',
            'student-2': 'Nico.Kurosawa',
        }

        for name in a_names:
            make_course(
                username=name,
                students=s_names,
            )

        s_names = s_names.keys()

        # name for teacher and admin
        a_names = itertools.cycle(a_names)
        # student names
        s_names = itertools.cycle(s_names)
        pids = [
            *problem_ids('admin', 5, True),
            *problem_ids('teacher', 5, True),
            *problem_ids('teacher-2', 5, True),
        ]
        pids = itertools.cycle(pids)
        submit(cls.init_submission_count, a_names, pids)

        # fliter online problem ids
        pids = [next(pids) for _ in range(15)]
        pids = itertools.cycle([
            pid for pid in pids
            if engine.Problem.objects.get(problem_id=pid).problem_status == 0
        ])
        submit(cls.init_submission_count, s_names, pids)

    @classmethod
    def teardown_method(cls):
        cls.submissions = []


class TestUserGetSubmission(SubmissionTester):
    def test_normal_get_submission_list(self, forge_client):
        client = forge_client('student')
        rv, rv_json, rv_data = self.request(
            client,
            'get',
            f'/submission/?offset=0&count={self.init_submission_count}',
        )

        pprint(rv_json)

        assert rv.status_code == 200
        assert 'unicorn' in rv_data
        assert len(rv_data['submissions']) == self.init_submission_count

        excepted_field_names = {
            'submissionId',
            'problemId',
            'username',
            'status',
            'score',
            'runTime',
            'memoryUsage',
            'languageType',
            'timestamp',
        }

        for s in rv_data['submissions']:
            assert len(excepted_field_names - set(s.keys())) == 0

    @pytest.mark.parametrize('offset, count',
                             [(0, 1),
                              (SubmissionTester.init_submission_count // 2, 1)]
                             )
    def test_get_truncated_submission_list(self, forge_client, offset, count):
        client = forge_client('student')
        rv, rv_json, rv_data = self.request(
            client,
            'get',
            f'/submission/?offset={offset}&count={count}',
        )

        pprint(rv_json)

        assert rv.status_code == 200
        assert len(rv_data['submissions']) == 1

    def test_get_submission_list_with_maximun_offset(self, forge_client):
        client = forge_client('student')
        rv, rv_json, rv_data = self.request(
            client,
            'get',
            f'/submission/?offset={SubmissionTester.init_submission_count * 2}&count=1',
        )

        print(rv_json)

        assert rv.status_code == 400

    def test_get_all_submission(self, forge_client):
        client = forge_client('student')
        rv, rv_json, rv_data = self.request(
            client,
            'get',
            '/submission/?offset=0&count=-1',
        )

        pprint(rv_json)

        assert rv.status_code == 200
        # only get online submissions
        assert len(rv_data['submissions']) == len(self.submissions)

        offset = self.init_submission_count // 2
        rv, rv_json, rv_data = self.request(
            client,
            'get',
            f'/submission/?offset={offset}&count=-1',
        )

        pprint(rv_json)

        assert rv.status_code == 200
        assert len(rv_data['submissions']) == (len(self.submissions) - offset)

    def test_get_submission_list_over_db_size(self, forge_client):
        client = forge_client('student')
        rv, rv_json, rv_data = self.request(
            client,
            'get',
            f'/submission/?offset=0&count={SubmissionTester.init_submission_count ** 2}',
        )

        pprint(rv_json)

        assert rv.status_code == 200
        assert len(rv_data['submissions']) == len(self.submissions)

    def test_get_submission_without_login(self, client):
        rv = client.get(f'/submission/{self.submissions[0]["submissionId"]}')
        pprint(rv.get_json())
        assert rv.status_code == 403

    def test_normal_user_get_others_submission(self, client_student):
        '''
        let student get all other's submission
        '''
        ids = [
            s['submissionId'] for s in self.submissions
            if s['username'] != 'student'
        ]
        pprint(ids)

        for _id in ids:
            rv, rv_json, rv_data = self.request(
                client_student,
                'get',
                f'/submission/{_id}',
            )
            assert rv.status_code == 200
            assert 'code' not in rv_data

    def test_get_self_submission(self, client_student):
        ids = [
            s['submissionId'] for s in self.submissions
            if s['username'] == 'student'
        ]
        pprint(ids)

        for _id in ids:
            rv, rv_json, rv_data = self.request(
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
            'cases',
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
        rv, rv_json, rv_data = self.request(
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
        rv, rv_json, rv_data = self.request(
            client,
            'get',
            f'/submission/?offset={offset}&count={count}',
        )
        assert rv.status_code == 400

    @pytest.mark.parametrize(
        'key, except_val',
        [('status', -2), ('languageType', 0), ('username', 'student')
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
        rv, rv_json, rv_data = self.request(
            client,
            'get',
            f'/submission/?offset=0&count=-1&{key}={except_val}',
        )

        pprint(rv_json)

        assert rv.status_code == 200
        assert len(rv_data['submissions']) != 0
        assert all(map(lambda x: x[key] == except_val,
                       rv_data['submissions'])) == True


class TestTeacherGetSubmission(SubmissionTester):
    def test_teacher_can_get_offline_submission(self, forge_client):
        client = forge_client('teacher')
        rv, rv_json, rv_data = self.request(
            client,
            'get',
            '/submission?offset=0&count=-1',
        )

        pprint(rv_json)

        user = User('teacher')
        except_count = len([
            *filter(
                lambda s: can_view(
                    user,
                    s.problem,
                ),
                engine.Submission.objects,
            )
        ])

        assert len(rv_data['submissions']) == except_count


class TestCreateSubmission(SubmissionTester):
    @pytest.mark.parametrize('submission', SubmissionTester.source.values())
    def test_normal_submission(self, client_student, submission):
        pids = [s['problemId'] for s in self.submissions]
        a_pid = None
        for pid in pids:
            if can_view(User('student'), Problem(pid).obj):
                a_pid = pid
                break
        assert pid is not None

        # first claim a new submission to backend server
        post_json = {'problemId': a_pid, 'languageType': submission['lang']}
        # recieve response, which include the submission id and a token to validat next request
        rv, rv_json, rv_data = self.request(
            client_student,
            'post',
            '/submission',
            json=post_json,
        )

        pprint(f'post: {rv_json}')

        assert rv.status_code == 200
        assert sorted(rv_data.keys()) == sorted(['token', 'submissionId'])

        # second, post my source code to server. after that, my submission will send to sandbox to be judged
        files = {'code': (submission['zip'], 'code')}
        rv = client_student.put(
            f'/submission/{rv_data["submissionId"]}?token={rv_data["token"]}',
            data=files,
        )
        rv_json = rv.get_json()

        pprint(f'put: {rv_json}')

        assert rv.status_code == 200

    def test_wrong_language_type(self, client_student):
        submission = self.source['c11']
        post_json = {
            'problemId': self.submissions[0]['problemId'],
            'languageType': 2
        }  # 2 for py3
        rv, rv_json, rv_data = self.request(
            client_student,
            'post',
            '/submission',
            json=post_json,
        )

        pprint(f'post: {rv_json}')

        files = {'code': (submission['zip'], 'code')}
        rv = client_student.put(
            f'/submission/{rv_data["submissionId"]}?token={rv_data["token"]}',
            data=files,
        )
        rv_json = rv.get_json()

        pprint(f'put: {rv_json}')

        assert rv.status_code == 200

    def test_empty_source(self, client_student):
        submission = self.source['c11']
        post_json = {
            'problemId': self.submissions[0]['problemId'],
            'languageType': submission['lang']
        }
        rv, rv_json, rv_data = self.request(
            client_student,
            'post',
            '/submission',
            json=post_json,
        )

        pprint(f'post: {rv_json}')

        files = {'code': (None, 'code')}
        rv = client_student.put(
            f'/submission/{rv_data["submissionId"]}?token={rv_data["token"]}',
            data=files,
        )
        rv_json = rv.get_json()

        pprint(f'put: {rv_json}')

        assert rv.status_code == 400

    @pytest.mark.parametrize('submission', SubmissionTester.source.values())
    def test_no_source_upload(self, client_student, submission):
        post_json = {
            'problemId': self.submissions[0]['problemId'],
            'languageType': submission['lang']
        }
        rv, rv_json, rv_data = self.request(
            client_student,
            'post',
            '/submission',
            json=post_json,
        )

        pprint(f'post: {rv_json}')

        files = {'c0d3': (submission['zip'], 'code')}
        rv = client_student.put(
            f'/submission/{rv_data["submissionId"]}?token={rv_data["token"]}',
            data=files,
        )
        rv_json = rv.get_json()

        pprint(f'put: {rv_json}')

        assert rv.status_code == 400

    def test_submit_to_others(self, forge_client):
        client = forge_client('student')
        rv, rv_json, rv_data = self.request(
            client,
            'post',
            '/submission',
            json={
                'problemId': 1,
                'languageType': 0
            },
        )

        pprint(rv_json)
        assert rv.status_code == 200

        client = forge_client('student-2')
        submission_id = rv_data['submissionId']
        token = rv_data['token']
        files = {'code': (self.source['c11']['zip'], 'd1w5q6dqw')}
        rv, rv_json, rv_data = self.request(
            client,
            'put',
            f'/submission/{submission_id}?token={token}',
            data=files,
        )

        pprint(rv_json)
        assert rv.status_code == 403

    def test_reach_rate_limit(self, client_student):
        submission = self.source['c11']
        post_json = {
            'problemId': self.submissions[0]['problemId'],
            'languageType': submission['lang']
        }
        client_student.post(
            '/submission',
            json=post_json,
        )

        for _ in range(10):
            rv = client_student.post(
                '/submission',
                json=post_json,
            )

            assert rv.status_code == 429

    def test_submit_to_non_participate_contest(self, client_student):
        pass

    def test_submit_outside_when_user_in_contest(self, client_student):
        '''
        submit a problem outside the contest when user is in contest
        '''
        pass

    def test_submit_to_not_enrolled_course(self, client_student):
        pass
