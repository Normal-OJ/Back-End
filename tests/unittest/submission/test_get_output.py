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


class TestSubmissionGetOutput:

    def test_get_output_successfully(self, app):
        with app.app_context():
            user = utils.user.create_user()
            problem = utils.problem.create_problem(
                test_case_info=utils.problem.create_test_case_info(
                    language=0,
                    task_len=1,
                ))
            submission = utils.submission.create_submission(
                user=user,
                problem=problem,
                # AC
                status=0,
            )
            utils.submission.add_fake_output(submission)
            output = submission.get_single_output(0, 0)
            assert output == {
                'stdout': 'out',
                'stderr': 'err',
            }

    def test_out_of_index(self, app):
        with app.app_context():
            user = utils.user.create_user()
            problem = utils.problem.create_problem()
            submission = utils.submission.create_submission(
                user=user,
                problem=problem,
            )
            with pytest.raises(FileNotFoundError) as err:
                submission.get_single_output(100, 100)
            assert str(err.value) == 'task not exist'

    def test_read_from_pending_submision(self, app):
        with app.app_context():
            user = utils.user.create_user()
            problem = utils.problem.create_problem(
                test_case_info=utils.problem.create_test_case_info(
                    language=0,
                    task_len=1,
                ))
            submission = utils.submission.create_submission(
                user=user,
                problem=problem,
                # AC
                status=0,
            )
            utils.submission.add_fake_output(submission)
            submission.rejudge()
            with pytest.raises(AttributeError) as err:
                submission.get_single_output(0, 0)
            assert str(err.value) == 'The submission is still in pending'
