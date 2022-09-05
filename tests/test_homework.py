from typing import Callable
from flask.testing import FlaskClient
import pytest
from tests.base_tester import BaseTester, random_string
from datetime import datetime
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
def course_data(
    request,
    client_admin: FlaskClient,
    problem_ids,
):
    BaseTester.setup_class()
    cd = CourseData(**request.param)
    # add course
    Course.add_course(cd.name, cd.teacher)
    # add students and TA
    client_admin.set_cookie(
        'test.test',
        'piann',
        User('admin').secret,
    )
    rv = client_admin.put(
        f'/course/{cd.name}',
        json={
            'TAs': cd.tas,
            'studentNicknames': cd.students
        },
    )
    client_admin.delete_cookie('test.test', 'piann')
    assert rv.status_code == 200, rv.get_json()
    # add homework
    hw = Homework.add(
        user=User(cd.teacher).obj,
        course_name=cd.name,
        markdown=f'# {cd.homework_name}\n\n{random_string()}',
        hw_name=cd.homework_name,
        start=int(datetime.now().timestamp()),
        end=int(datetime.now().timestamp()),
        problem_ids=problem_ids(cd.teacher, 3),
        scoreboard_status=0,
        penalty='score=score*(0.8**overtime)',
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


class TestIPFilter(BaseTester):

    @pytest.mark.parametrize(
        '_filter',
        [
            '127.0.0.1',
            '127.0.0.*',
            '192.168.10-13.*',
        ],
    )
    def test_valid_filter(
        self,
        forge_client: Callable[[str], FlaskClient],
        course_data: CourseData,
        _filter: str,
    ):
        hw = Homework.get_by_id(course_data.homework_ids[0])
        # get admin client
        client = forge_client('admin')
        # add new ip filter
        rv = client.patch(
            f'/homework/{course_data.name}/{hw.homework_name}/ip-filters',
            json={'patches': [
                {
                    'op': 'add',
                    'value': _filter,
                },
            ]},
        )
        assert rv.status_code == 200, rv.data
        hw.reload()
        assert hw.ip_filters == [_filter]

    @pytest.mark.parametrize(
        '_filter',
        [
            '1.2.3.4.5',
            'noj.tw',
            '1.2.3.4-*',
        ],
    )
    def test_invalid_filter(
        self,
        forge_client: Callable[[str], FlaskClient],
        course_data: CourseData,
        _filter: str,
    ):
        hw = Homework.get_by_id(course_data.homework_ids[0])
        # get admin client
        client = forge_client('admin')
        # add new ip filter
        rv = client.patch(
            f'/homework/{course_data.name}/{hw.homework_name}/ip-filters',
            json={'patches': [
                {
                    'op': 'add',
                    'value': _filter,
                },
            ]},
        )
        assert rv.status_code == 400, rv.data
        hw.reload()
        assert hw.ip_filters == []


class TestHomework(BaseTester):

    def test_get_single_homework(self, forge_client, course_data):
        # get teacher client
        client = forge_client(course_data.teacher)
        rv = client.get(f'/homework/{course_data.homework_ids[0]}')
        rv_json = rv.get_json()
        rv_data = rv_json['data']
        assert rv.status_code == 200, rv_json
        for key in ('name', 'start', 'end', 'problemIds'):
            assert key in rv_data

    def test_get_list_of_homewrok(self, forge_client, course_data):
        c_data = course_data
        client = forge_client(c_data.teacher)
        rv = client.get(f'/course/{c_data.name}/homework')
        rv_json = rv.get_json()
        rv_data = rv_json['data']
        assert rv.status_code == 200, rv_json
        assert len(rv_data) == len(c_data.homework_ids), rv_data

    def test_create_homework(self, forge_client, course_data):
        client = forge_client(course_data.teacher)
        rv, rv_json, rv_data = self.request(
            client, 'get', f'/course/{course_data.name}/homework')
        assert rv.status_code == 200, rv_json
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
                'end': int(datetime.now().timestamp() + 86400),
                'penalty': 'score=score*(0.8**overtime)',
            })
        print(rv_json)
        assert rv.status_code == 200
        rv, rv_json, rv_data = self.request(
            client, 'get', f'/course/{course_data.name}/homework')
        after_len = len(rv_data)

        assert rv.status_code == 200
        assert after_len == before_len + 1

    def test_update_homework(
        self,
        forge_client,
        course_data: CourseData,
        problem_ids,
    ):
        pids = problem_ids(course_data.teacher, 2)
        client = forge_client(course_data.teacher)
        # update
        new_data = {
            'name': 'How-to-write-oneline-python',
            'markdown': '# oneline is awesome',
            'start': int(datetime.now().timestamp()),
            'end': int(datetime.now().timestamp()) + 1440,
            'problemIds': pids,
            'scoreboardStatus': 1,
            'penalty': 'score=score*(0.8**overtime)',
        }
        rv, rv_json, rv_data = self.request(
            client,
            'put',
            f'/homework/{course_data.homework_ids[0]}',
            json=new_data,
        )
        assert rv.status_code == 200, rv_json
        # get it again
        rv, rv_json, rv_data = self.request(
            client,
            'get',
            f'/homework/{course_data.homework_ids[0]}',
        )
        assert rv.status_code == 200, rv_json
        for key in ('name', 'markdown', 'start', 'end'):
            assert rv_data[key] == new_data[key]
        assert {*rv_data['problemIds']} == {*new_data['problemIds']}
        # ensure that student status also updated
        hw_id = course_data.homework_ids[0]
        homework = Homework.get_by_id(hw_id)
        course = Course(course_data.name)
        print(course.obj.student_nicknames)
        status = next(iter(homework.student_status.values()))
        assert sorted(status.keys()) == sorted(map(str, pids))

    def test_update_student_status(
        self,
        forge_client,
        course_data,
        problem_ids,
    ):
        # get teacher client
        client = forge_client(course_data.teacher)
        rv = client.put(
            f'/course/{course_data.name}',
            json={
                'TAs': [],
                'studentNicknames': {
                    'Yin-Da-Chen': 'noobs'
                }
            },
        )
        assert rv.status_code == 200
        rv, rv_json, rv_data = self.request(
            client,
            'put',
            f'/course/{course_data.name}',
            json={
                'TAs': course_data.tas,
                'studentNicknames': {
                    'Bo-Chieh-Chuang': 'genius'
                }
            },
        )
        assert rv.status_code == 200, rv_json
        rv, rv_json, rv_data = self.request(
            client,
            'get',
            f'/homework/{course_data.homework_ids[0]}',
        )
        student_status = rv_data['studentStatus']
        assert 'Yin-Da-Chen' not in student_status
        assert 'Bo-Chieh-Chuang' in student_status
        default_status = Homework.default_problem_status()
        for name, single_student_status in student_status.items():
            for problem_status in single_student_status.values():
                assert problem_status == default_status, (
                    name, single_student_status)

    def test_delete_homework(self, forge_client, course_data):
        client = forge_client(course_data.teacher)
        rv, rv_json, rv_data = self.request(
            client,
            'get',
            f'/homework/{course_data.homework_ids[0]}',
        )
        assert rv.status_code == 200, rv_json
        # delete the homework
        rv, rv_json, rv_data = self.request(
            client,
            'delete',
            f'/homework/{course_data.homework_ids[0]}',
        )
        assert rv.status_code == 200, rv_json
        rv, rv_json, rv_data = self.request(
            client,
            'get',
            f'/homework/{course_data.homework_ids[0]}',
        )
        assert rv.status_code == 404, rv_json
