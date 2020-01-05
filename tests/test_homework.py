import pytest

from tests.base_tester import BaseTester, random_string
from datetime import datetime, timedelta, time

from mongo import *


class CourseData:
    def __init__(self, name, teacher, students, tas):
        self.name = name
        self.teacher = teacher
        self.students = students
        self.tas = tas
        self.homework_ids = []

    @property
    def homework_name(self):
        return f'Test HW 4 {self.name} {id(self)}'


@pytest.fixture(params=[{
    'name': 'Programming_I',
    'teacher': 'Po-Wen-Chi',
    'students': {
        'Yin-Da-Chen': 'ala',
        'Bo-Chieh-Chuang': 'bogay'
    },
    'tas': ['Tzu-Wei-Yu']
}])
def course_data(request, client_admin, problem_ids):
    BaseTester.setup_class()

    cd = CourseData(**request.param)
    # add course
    add_course(cd.name, cd.teacher)
    # add students and TA
    client_admin.put(f'/course/{cd.name}',
                     json={
                         'TAs': cd.tas,
                         'studentNicknames': cd.students
                     })
    # add homework
    hw = Homework.add_hw(
        user=User(cd.teacher).obj,
        course_name=cd.name,
        markdown=f'# {cd.homework_name}',
        hw_name=cd.homework_name,
        start=int(datetime.now().timestamp()),
        end=int(datetime.now().timestamp()),
        problem_ids=problem_ids(cd.teacher, 3),
        scoreboard_status=0,
    )
    # append hw id
    cd.homework_ids.append(str(hw.id))

    yield cd

    BaseTester.teardown_class()


@pytest.fixture(
    params={
        'name': 'Advanced_Programming',
        'teacher': 'Tsung-Che-Chiang',
        'students': {
            'Tzu-Wei-Yu': 'Uier',
            'Bo-Chieh-Chuang': 'bogay'
        },
        'tas': ['Yin-Da-Chen']
    })
def another_course(request, course_data, client_admin):
    return course_data(request, client_admin)


class TestHomework(BaseTester):
    def test_get_single_homework(self, forge_client, course_data):
        # get teacher client
        client = forge_client(course_data.teacher)
        rv = client.get(f'/homework/{course_data.homework_ids[0]}')
        rv_json = rv.get_json()
        rv_data = rv_json['data']

        assert rv.status_code == 200
        for key in ['name', 'start', 'end', 'problemIds']:
            assert key in rv_data

    def test_get_list_of_homewrok(self, forge_client, course_data):
        c_data = course_data
        client = forge_client(c_data.teacher)

        rv = client.get(f'/course/{c_data.name}/homework')
        rv_json = rv.get_json()
        rv_data = rv_json['data']

        print(rv_json)

        assert rv.status_code == 200
        assert len(rv_data) == len(c_data.homework_ids)

    def test_create_homework(self, forge_client, course_data):
        client = forge_client(course_data.teacher)

        rv, rv_json, rv_data = self.request(
            client, 'get', f'/course/{course_data.name}/homework')
        print(rv_json)
        assert rv.status_code == 200
        before_len = len(rv_data)

        # create homework
        rv, rv_json, rv_data = self.request(
            client,
            'post',
            '/homework',
            json={
                'name': course_data.homework_name + '2',
                'courseName': course_data.name,
                'markdown': '# ' + course_data.homework_name + ' (=_=) ',
                'start': int(datetime.now().timestamp()),
                'end': int(datetime.now().timestamp() + 86400)
            })
        print(rv_json)
        assert rv.status_code == 200
        rv, rv_json, rv_data = self.request(
            client, 'get', f'/course/{course_data.name}/homework')
        after_len = len(rv_data)

        assert rv.status_code == 200
        assert after_len == before_len + 1

    def test_update_homework(self, forge_client, course_data, problem_ids):
        pids = problem_ids(course_data.teacher, 2)
        client = forge_client(course_data.teacher)
        # update
        new_data = {
            'name': 'How-to-write-oneline-python',
            'markdown': '# oneline is awesome',
            'start': int(datetime.now().timestamp()),
            'end': int(datetime.now().timestamp()) + 1440,
            'problemIds': pids,
            'scoreboardStatus': 1
        }
        rv, rv_json, rv_data = self.request(
            client,
            'put',
            f'/homework/{course_data.homework_ids[0]}',
            json=new_data)

        print(rv_json)
        assert rv.status_code == 200

        # get it again
        rv, rv_json, rv_data = self.request(
            client, 'get', f'/homework/{course_data.homework_ids[0]}')
        print(rv_json)
        assert rv.status_code == 200

        for key in ['name', 'markdown', 'start', 'end']:
            assert rv_data[key] == new_data[key]
        assert sorted(rv_data['problemIds']) == sorted(new_data['problemIds'])

    def test_delete_homework(self, forge_client, course_data):
        client = forge_client(course_data.teacher)

        rv, rv_json, rv_data = self.request(
            client, 'get', f'/homework/{course_data.homework_ids[0]}')
        print(rv_json)
        assert rv.status_code == 200

        # delete the homework
        rv, rv_json, rv_data = self.request(
            client, 'delete', f'/homework/{course_data.homework_ids[0]}')
        print(rv_json)
        assert rv.status_code == 200

        rv, rv_json, rv_data = self.request(
            client, 'get', f'/homework/{course_data.homework_ids[0]}')
        print(rv_json)
        assert rv.status_code == 404
