import pytest

from tests.base_tester import BaseTester
from datetime import datetime, timedelta, time

from mongo import Course, Contest


class CourseData(Course):
    def __init__(self, student_nicknames, course_status, name, teacher, tas,
                 contest_name):
        self.student_nicknames = student_nicknames
        self.status = status
        self.name = name
        self.teacher = tacher
        self.tas = tas
        self.contest_name = contest_name


#set course's contest data
@pytest.fixture(params=[{
    'student_nicknames': {
        'Bo-Chieh-Chuang': '001'
    },
    'status': 1,
    'name': 'course_test',
    'teacher': 'Tsung-Che-Chiang',
    'problem_ids': ['1'],
    'tas': ['sa']
}])
def course_data(request, client_admin):
    BaseTester.setup_class()
    course_data = CourseData(**request.param)
    add_course(course_data.name, course_data.teacher)
    #add tas and teacher
    client_admin.put(f'/course/{course_data.name}',
                     json={
                         'TAs': course_data.tas,
                         'studentNicknames': course_data.students
                     })
    # add contest
    contest = Contest.add_contest(user=User(course_data.teacher).obj,
                                  course_name=course_data.name,
                                  contest_name=course_data.contest_name,
                                  start=int(datetime.now().timestamp()),
                                  end=int(datetime.now().timestamp()),
                                  problem_ids=['test'],
                                  scoreboard_status=0,
                                  contest_mode=1)
    # insert contest to course
    course_data.contest.append(contest.id)
    yield cd
    BaseTester.teardown_class()


class TestContest(BaseTester):
    def test_get_single_contest(self, forge_client, course_data):
        client = forge_client(course_data.teacher)
        rv, rv_json, rv_data = self.request(
            client, 'get', f'/contest/view/{course_data.contest[0].id}')

        assert rv.status_code == 200
        for key in [
                'start', 'end', 'scoreboard_status', 'contestMode',
                'courseName'
        ]:
            assert key in rv_data

    def test_get_contest_in_course(self, forge_client, course_data):
        client = forge_client(course_data.teacher)
        rv, rv_json, rv_data = self.request(
            client, 'get', f'/course/{course_data.name}/content')

        assert rv.status_code == 200
        assert len(rv_data) == len(course.contest)

    def test_create_contest(self, forge_client, course_data):
        client = forge_client(course_data.teacher)
        cd = course_data
        rv, rv_json, rv_data = self.request(
            client,
            'post',
            f'course/{course_data.name}/content',
            json={
                'name': 'contest_test',
                'start': datetime.now(),
                'end': datetime.now(),
                'problem_ids': cd.problem_ids,
                'scoreboard_status': 1,
                'contest_mode': 1
            })
        assert rv.status_code == 200
        #query the inserted data from db
        ismatch = False
        rv, rv_json, rv_data = self.request(
            client, 'get', f'/course/{course_data.name}/content')
        for dict in rv_data:
            if dict['name'] == 'contest_test':
                ismatch = True
        assert ismatch == True

    def test_delete_contest(self, forge_client, course_data):
        client = forge_client(course_data.teacher)
        cd = course_data
        rv, rv_json, rv_data = self.request(client,
                                            'delete',
                                            f'/course/{cd.name}/content',
                                            json={'name': cd.contest_name})
        assert rv.status_code == 200

    def test_update_contest(self, forge_client, course_data):
        client = forge_client(course_data.teacher)
        cd = course_data
        rv, rv_json, rv_data = self.request(client,
                                            'put',
                                            f'/course/{cd.name}/content',
                                            json={{
                                                "name": cd.contest_name,
                                                "contestMode": 1,
                                                "problemIds": ["1", "2", "3"]
                                            }})
        assert rv.status_code == 200

    def test_join_contest(self, forge_client, course_data):
        client = forge_client('Tzu-Wei-Yu')
        cd = course_data
        rv, rv_json, rv_data = self.request(client,
                                            'put',
                                            f'/course/{cd.name}/content',
                                            json={{
                                                "name": cd.contest_name,
                                                "contestMode": 1,
                                                "problemIds": ["1", "2", "3"]
                                            }})
        assert rv.status_code == 200

    def test_leave_contest(self, forge_client, course_data):
        client = forge_client('Yin-Da-Chen')
        cd = course_data
        rv, rv_json, rv_data = self.request(client, 'get', f'/contest/leave')
        assert rv.status_code == 200
