from typing import Dict, List, Protocol
from flask import Flask
from flask.testing import FlaskClient
from mongo import *
from mongo import engine
import mongomock.gridfs

import pytest
import random
import pytest_minio_mock
from datetime import datetime
from zipfile import ZipFile
from collections import defaultdict
from mongo.config import MINIO_BUCKET
from mongo.utils import MinioClient
from tests.base_tester import random_string
from tests.test_problem import get_file
from tests import utils


@pytest.fixture
def app(tmp_path, minio_mock):
    from app import app as flask_app
    app = flask_app()
    app.config['TESTING'] = True
    app.config['SERVER_NAME'] = 'test.test'
    mongomock.gridfs.enable_gridfs_integration()

    # modify submission config for testing
    # use tmp dir to save user source code
    submission_tmp_dir = (tmp_path / Submission.config().TMP_DIR).absolute()
    submission_tmp_dir.mkdir(exist_ok=True)
    Submission.config().TMP_DIR = submission_tmp_dir

    MinioClient().client.make_bucket(MINIO_BUCKET)
    return app


# TODO: share client may cause auth problem
@pytest.fixture
def client(app: Flask):
    return app.test_client()


class ForgeClient(Protocol):

    def __call__(self, username: str) -> FlaskClient:
        ...


@pytest.fixture
def forge_client(client: FlaskClient):

    def seted_cookie(username: str) -> FlaskClient:
        client.set_cookie('piann', User(username).secret, domain='test.test')
        return client

    return seted_cookie


@pytest.fixture
def client_admin(forge_client: ForgeClient):
    return forge_client('admin')


@pytest.fixture
def client_teacher(forge_client: ForgeClient):
    return forge_client('teacher')


@pytest.fixture
def client_student(forge_client: ForgeClient):
    return forge_client('student')


@pytest.fixture
def test_token():
    # Token for user: test
    return User('test').secret


@pytest.fixture
def test2_token():
    # Token for user: test2
    return User('test2').secret


@pytest.fixture
def make_course(forge_client):
    from tests.test_homework import CourseData

    def make_course(username, students={}, tas=[]):
        '''
        insert a dummy course data into DB

        Args:
            username -> str: course teacher's user name
            students -> dict[str, str]:
                course students, key is student's username and value is student's nickname
            tas -> list[str]:
                a list contains tas' username

        Return:
            generated course data
        '''
        # login with user name
        client = forge_client(username)
        # generate random dummy data
        c_data = CourseData(
            name=random_string(),
            teacher=username,
            students=students,
            tas=tas,
        )
        # add course
        assert Course.add_course(
            c_data.name,
            c_data.teacher,
        ) == True, f'course name: {c_data.name}\nteacher: {c_data.teacher}\n'
        # add students and TA
        rv = client.put(
            f'/course/{c_data.name}',
            json={
                'TAs': c_data.tas,
                'studentNicknames': c_data.students
            },
        )
        assert rv.status_code == 200, rv.get_json()

        client._cookies.clear()
        return c_data

    return make_course


@pytest.fixture()
def problem_ids():

    def problem_ids(
        username: int,
        length: int,
        add_to_course: bool = False,
        status: int = 0,
        type: int = 0,
        quota: int = -1,
    ) -> List[int]:
        '''
        insert dummy problems into db

        Args:
            - username: the problem owner's username
            - length: how many problem you want to create
        Return:
            a list of problem id that you create
        '''
        rets = []  # created problem ids
        for _ in range(length):
            course = None
            if add_to_course:
                course = engine.Course.objects(teacher=username).first()
            prob = utils.problem.create_problem(
                course=course,
                owner=username,
                status=random.randint(0, 1) if status == -1 else status,
                type=type,
                quota=quota,
                test_case_info={
                    'language':
                    2,
                    'fill_in_template':
                    '',
                    'tasks': [
                        {
                            'caseCount': 1,
                            'taskScore': 100,
                            'memoryLimit': 32768,
                            'timeLimit': 1000,
                        },
                    ],
                },
            )
            if prob.problem_type != 2:
                test_case = get_file('default/test_case.zip')['case'][0]
                prob.update_test_case(test_case)
            rets.append(prob.id)

        return rets

    return problem_ids


@pytest.fixture
def save_source(tmp_path):

    def save_source(filename, source, lang, ext=None):
        '''
        save user source codes to tmp dir
        currently only support one file.

        Args:
            filename: the source code's filename without extension
            source: source code (must be bytes-like object)
            lang: programming language, only accept {0, 1, 2}
            ext: main script extension want to use, if None, decided by lang

        Returns:
            a zip file contains source code
        '''
        # decide extension
        if not ext:
            ext = ['.c', '.cpp', '.py', '.pdf'][lang]
        # set path
        name = tmp_path / (filename + ext)
        zip_path = tmp_path / f'{name}.zip'
        # duplicated file
        if name.exists():
            raise FileExistsError(name)
        with open(name, 'wb') as f:
            f.write(source)
        with ZipFile(zip_path, 'w') as f:
            f.write(name, arcname=f'main{ext}')
        return True

    return save_source


@pytest.fixture
def get_source(tmp_path):

    def get_source(filename):
        '''
        get users zipped source by filename

        Args:
            filename: a string denote the source code's filename include extension

        Returns:
            the zip file
        '''
        path = tmp_path / f'{filename}.zip'

        if not path.exists():
            raise FileNotFoundError(path)

        return open(path, 'rb')

    return get_source


@pytest.fixture
def submit_once(app, get_source):

    def submit_once(name, pid, filename, lang, client=None):
        '''
        create one submission
        Args:
            name: user's name who want to create a submission
            pid: the problem id
            filename: source code's zip filename
            lang: language ID
        '''
        with app.app_context():
            now = datetime.now()
            try:
                submission = Submission.add(
                    problem_id=pid,
                    username=name,
                    lang=lang,
                    timestamp=now,
                    ip_addr="127.0.0.1",
                )
            except engine.DoesNotExist as e:
                assert False, str(e)
            res = submission.submit(get_source(filename))
            assert res == True
        return submission.id

    return submit_once


@pytest.fixture
def submit(submit_once):

    def submit(
        names,
        pids,
        count,
        filename='base.c',
        lang=0,
    ) -> Dict[str, List[Submission]]:
        n2p = defaultdict(list)  # name to pid
        for n, p, _ in zip(names, pids, 'x' * count):
            n2p[n].append(p)
        n2s = defaultdict(list)  # name to submission id
        for name, ps in n2p.items():
            for p in ps:
                n2s[name].append(
                    submit_once(
                        name=name,
                        pid=p,
                        filename=filename,
                        lang=lang,
                    ))

        return n2s

    return submit
