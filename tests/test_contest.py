import pytest
from tests.base_tester import BaseTester
from datetime import datetime, timedelta, time
from mongo import *
from mongo import engine


class CourseData():

    def __init__(self, student_nicknames, course_status, name, teacher, tas):
        self.student_nicknames = student_nicknames
        self.course_status = course_status
        self.name = name
        self.teacher = teacher
        self.tas = tas
        self.contest = []


#set course's contest data
@pytest.fixture(params=[{
    'student_nicknames': {
        'Yin-Da-Chen': 'ala',
        'Bo-Chieh-Chuang': '001'
    },
    'course_status': 1,
    'name': 'course_test',
    'teacher': 'Po-Wen-Chi',
    'tas': ['sa']
}])
def course_data(request, client_teacher):
    BaseTester.setup_class()
    cd = CourseData(**request.param)
    Course.add_course(cd.name, cd.teacher)
    #add tas and teacher
    client_teacher.put(f'/course/{cd.name}',
                       json={
                           'TAs': cd.tas,
                           'studentNicknames': cd.student_nicknames
                       })
    # add contest
    contest = Contest.add_contest(user=User(cd.teacher).obj,
                                  course_name=cd.name,
                                  contest_name='contest1',
                                  problem_ids=None,
                                  scoreboard_status=0,
                                  contest_mode=1,
                                  start=int(datetime.now().timestamp()),
                                  end=int(datetime.now().timestamp()))
    # insert contest to course
    cd.contest.append(contest.id)
    yield cd
    BaseTester.teardown_class()


class TestContest(BaseTester):

    def test_get_single_contest(self, forge_client, course_data):
        client = forge_client(course_data.teacher)
        cd = course_data
        rv, rv_json, rv_data = self.request(client, 'get',
                                            f'/contest/view/{cd.contest[0]}')

        assert rv.status_code == 200
        for key in [
                'start', 'end', 'scoreboard_status', 'contestMode',
                'courseName'
        ]:
            assert key in rv_data

    def test_get_contest_in_course(self, forge_client, course_data):
        client = forge_client(course_data.teacher)
        rv, rv_json, rv_data = self.request(
            client, 'get', f'/course/{course_data.name}/content', json={})
        assert rv.status_code == 200
        assert len(rv_data) == len(course_data.contest)

    def test_create_contest(self, forge_client, course_data):
        client = forge_client(course_data.teacher)
        cd = course_data
        rv, rv_json, rv_data = self.request(
            client,
            'post',
            f'course/{course_data.name}/content',
            json={
                'name': 'contest_test',
                'start': int(datetime.now().timestamp()),
                'end': int(datetime.now().timestamp()),
                'problemIds': None,
                'contestMode': 1,
                'scoreboardStatus': 1
            })
        assert rv.status_code == 200
        #query the inserted data from db
        ismatch = False
        rv, rv_json, rv_data = self.request(
            client, 'get', f'/course/{course_data.name}/content', json={})
        assert rv.status_code == 200
        for dict in rv_data:
            if dict['name'] == 'contest_test':
                ismatch = True
        assert ismatch == True

    def test_delete_contest(self, forge_client, course_data):
        client = forge_client(course_data.teacher)
        cd = course_data
        contest = Contest.add_contest(user=User(cd.teacher).obj,
                                      course_name=cd.name,
                                      contest_name='contest4delete',
                                      start=int(datetime.now().timestamp()),
                                      end=int(datetime.now().timestamp()),
                                      problem_ids=None,
                                      scoreboard_status=0,
                                      contest_mode=1)
        rv, rv_json, rv_data = self.request(
            client,
            'delete',
            f'/course/{course_data.name}/content',
            json={'name': 'contest4delete'})
        assert rv.status_code == 200

    def test_update_contest(self, forge_client, course_data):
        client = forge_client(course_data.teacher)
        cd = course_data
        # add contest
        contest = Contest.add_contest(user=User(cd.teacher).obj,
                                      course_name=cd.name,
                                      contest_name='contest4update',
                                      start=int(datetime.now().timestamp()),
                                      end=int(datetime.now().timestamp()),
                                      problem_ids=None,
                                      scoreboard_status=0,
                                      contest_mode=1)
        rv, rv_json, rv_data = self.request(client,
                                            'put',
                                            f'/course/{cd.name}/content',
                                            json={
                                                'name': 'contest1',
                                                'newName': 'contest_newname',
                                                'contestMode': 1,
                                                'problemIds': None
                                            })
        assert rv.status_code == 200
        client = forge_client(course_data.teacher)
        rv, rv_json, rv_data = self.request(client, 'get',
                                            f'/contest/view/{cd.contest[0]}')
        assert rv_data['name'] == 'contest_newname'
        assert rv.status_code == 200

    def test_join_contest(self, forge_client, course_data):
        cd = course_data
        client_teacher = forge_client(cd.teacher)
        rv, rv_json, rv_data = self.request(client_teacher,
                                            'put',
                                            f'/course/{cd.name}',
                                            json={
                                                'TAs': [],
                                                'studentNicknames':
                                                cd.student_nicknames
                                            })
        client = forge_client('Bo-Chieh-Chuang')
        rv = client_teacher.put(f'/course/{cd.name}')
        rv = client.get(f'/contest/join/{cd.contest[0]}')
        assert rv.status_code == 200
        #query db check student is added in contest
        rv, rv_json, rv_data = self.request(client_teacher, 'get',
                                            f'/contest/view/{cd.contest[0]}')
        assert 'Bo-Chieh-Chuang' in rv_data['participants']

    def test_leave_contest(self, forge_client, course_data):
        cd = course_data
        client_teacher = forge_client(cd.teacher)
        rv, rv_json, rv_data = self.request(client_teacher,
                                            'put',
                                            f'/course/{cd.name}',
                                            json={
                                                'TAs': [],
                                                'studentNicknames':
                                                cd.student_nicknames
                                            })
        client = forge_client('Bo-Chieh-Chuang')
        rv = client.get(f'/contest/join/{cd.contest[0]}')
        assert rv.status_code == 200
        rv, rv_json, rv_data = self.request(client, 'get', f'/contest/leave')
        assert rv.status_code == 200
        #query db check student is not in contest
        rv, rv_json, rv_data = self.request(client_teacher, 'get',
                                            f'/contest/view/{cd.contest[0]}')
        assert 'Bo-Chieh-Chuang' not in rv_data['participants']
