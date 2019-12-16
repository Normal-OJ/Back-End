import pytest
import io
import os

from zipfile import ZipFile
from datetime import datetime
from pprint import pprint

from mongo import *
from tests.base_tester import BaseTester

from model.submission import assign_token, verify_token, tokens


class TestSubmissionUtils:
    @classmethod
    def setup_class(cls):
        tokens = {}

    @classmethod
    def teardown_class(cls):
        tokens = {}

    def test_token_assign(self):
        token = assign_token('8888')
        assert token is not None
        assert verify_token('8888', token) is True


class SubmissionTester(BaseTester):
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
    def prepare_problem(cls):
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
    def setup_class(cls, tmp_path):
        super().setup_class()
        cls.path = tmp_path
        cls.prepare_problem(tmp_path)

        # use tmp dir to save user source code
        from model import submission
        submission.SOURCE_PATH = tmp_path / submission.SOURCE_PATH
        submission.SOURCE_PATH = submission.SOURCE_PATH.absolute()
        os.makedirs(submission.SOURCE_PATH, exist_ok=True)


class TestGetSubmission(SubmissionTester):
    def test_get_submission_without_login(self, client):
        pass

    def test_get_other_submission(self):
        pass

    def test_get_self_submission(self):
        pass


class TestCreateSubmission(SubmissionTester):
    @pytest.mark.parametrize('submission', SubmissionTester.source.values())
    def test_normal_submission(self, client_student, submission):
        # first claim a new submission to backend server
        post_json = {'problemId': '8888', 'languageType': submission['lang']}
        # recieve response, which include the submission id and a token to validat next request
        rv = client_student.post('/submission', json=post_json)
        rv_json = rv.get_json()
        rv_data = rv_json['data']

        pprint(f'post: {rv_json}')

        assert 'token' in rv_data
        assert 'submissionId' in rv_data
        assert rv.status_code == 200

        # second, post my source code to server. after that, my submission will send to sandbox to be judged
        files = {'code': (submission['zip'], 'code')}
        rv = client_student.put(
            f'/submission/{rv_data["submissionId"]}?token={rv_data["token"]}',
            data=files)
        rv_json = rv.get_json()

        pprint(f'put: {rv_json}')

        assert rv.status_code == 200

    def test_wrong_language_type(self):
        pass

    def test_empty_source(self):
        pass

    def test_no_source_upload(self):
        pass

    def test_reach_rate_limit(self):
        pass

    def test_submit_to_non_participate_contest(self):
        pass

    def test_submit_outside_when_user_in_contest(self):
        '''
        submit a problem outside the contest when user is in contest
        '''
        pass

    def test_submit_to_not_enrolled_course(self):
        pass