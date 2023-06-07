import pytest
import time
import io
from zipfile import ZipFile
from datetime import datetime, timedelta
from tests import utils
from mongo import Submission, User


def setup_function(_):
    utils.drop_db()


def teardown_function(_):
    utils.drop_db()


class TestSubmissionCheckCode:

    def test_without_file(self, app):
        with app.app_context():
            user = utils.user.create_user()
            problem = utils.problem.create_problem()
            submission = utils.submission.create_submission(
                user=user,
                problem=problem,
            )
            result = submission.check_code(None)
            assert result == 'no file'

    def test_with_non_zip_file(self, app):
        with app.app_context():
            user = utils.user.create_user()
            problem = utils.problem.create_problem()
            submission = utils.submission.create_submission(
                user=user,
                problem=problem,
            )
            result = submission.check_code(
                io.BytesIO(b'this is not a zip file'))
            assert result == 'not a valid zip file'

    def test_with_multiple_file_in_zip(self, app):
        with app.app_context():
            user = utils.user.create_user()
            problem = utils.problem.create_problem()
            submission = utils.submission.create_submission(
                user=user,
                problem=problem,
            )
            code = io.BytesIO()
            with ZipFile(code, 'x') as zf:
                zf.writestr('main.c', '#include <stdio.h>\n')
                zf.writestr('main.py', 'import os\n')
            code = code.getvalue()
            result = submission.check_code(io.BytesIO(code))
            assert result == 'more than one file in zip'

    def test_with_filename_is_not_main(self, app):
        with app.app_context():
            user = utils.user.create_user()
            problem = utils.problem.create_problem()
            submission = utils.submission.create_submission(
                user=user,
                problem=problem,
            )
            code = io.BytesIO()
            with ZipFile(code, 'x') as zf:
                zf.writestr('m4in.c', '#include <stdio.h>\n')
            code = code.getvalue()
            result = submission.check_code(io.BytesIO(code))
            assert result == 'only accept file with name \'main\''
