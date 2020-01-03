from app import app as flask_app
from mongo import *

import os
import pytest
from tests.base_tester import random_string
from tests.test_homework import CourseData
from tests.test_submission import random_problem_data


@pytest.fixture
def app():
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def forge_client(client):
    def seted_cookie(username):
        client.set_cookie('test.test', 'piann', User(username).secret)
        return client

    return seted_cookie


@pytest.fixture
def client_admin(forge_client):
    return forge_client('admin')


@pytest.fixture
def client_teacher(forge_client):
    return forge_client('teacher')


@pytest.fixture
def client_student(forge_client):
    return forge_client('student')


@pytest.fixture
def test_token():
    # Token for user: test
    return 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJ0ZXN0LnRlc3QiLCJleHAiOjE1NzkyNzEzMDksInNlY3JldCI6dHJ1ZSwiZGF0YSI6eyJ1c2VybmFtZSI6InRlc3QiLCJ1c2VySWQiOiI2NGMzN2YxNWNhNzNmMDRkNGFiMzRmNmYifX0.QUYwwR_RPVLAHZ9GxbUNyqI4w6w429kE6GCgmp5my9o'


@pytest.fixture
def test2_token():
    # Token for user: test2
    return 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJ0ZXN0LnRlc3QiLCJleHAiOjE1NzkyNzE0NjgsInNlY3JldCI6dHJ1ZSwiZGF0YSI6eyJ1c2VybmFtZSI6InRlc3QyIiwidXNlcklkIjoiOTdlYzJhNmY3ZTA2YWY3YTUwMmUzMWVkIn19.WVuSHj55b23kS_qb07ER15lRSdr20zBL-FdCRTk7pqM'


@pytest.fixture
def make_course(forge_client):
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
        add_course(c_data.name, c_data.teacher)
        # add students and TA
        client.put(
            f'/course/{c_data.name}',
            json={
                'TAs': c_data.tas,
                'studentNicknames': c_data.students
            },
        )
        client.cookie_jar.clear()
        return c_data

    return make_course


@pytest.fixture()
def problem_ids(forge_client, make_course):
    def problem_ids(username, length, add_to_course=False):
        '''
        insert dummy problems into db

        Args:
            - username: the problem owner's username
            - length: how many problem you want to create
        Return:
            a list of problem id that you create
        '''
        client = forge_client(username)
        rets = []  # created problem ids
        for _ in range(length):
            rv = client.post(
                '/problem/manage',
                json=random_problem_data(username if add_to_course else None),
            )
            assert rv.status_code == 200, rv.get_json()
            rets.append(rv.get_json()['data']['problemIds'][0])
        # don't leave cookies!
        client.cookie_jar.clear()

        return rets

    return problem_ids
