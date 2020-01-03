import os
import pathlib


# submission api config
class SubmissionConfig:
    RATE_LIMIT = int(os.environ.get(
        'SUBMISSION_RATE_LIMIT',
        5,
    ))

    SOURCE_PATH = pathlib.Path(
        os.environ.get(
            'SUBMISSION_SOURCE_PATH',
            'submissions',
        ), )
    SOURCE_PATH.mkdir(exist_ok=True)

    TMP_DIR = pathlib.Path(
        os.environ.get(
            'SUBMISSION_TMP_DIR',
            '/tmp' / SOURCE_PATH,
        ), )
    TMP_DIR.mkdir(exist_ok=True)

    JUDGE_URL = os.environ.get(
        'JUDGE_URL',
        'http://sandbox:1450/submit',
    )
