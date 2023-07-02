from typing import List, Dict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pytest
from mongo import *
from unittest.mock import patch
from flask.testing import FlaskClient
from tests.base_tester import BaseTester, random_string
from tests.conftest import ForgeClient


@dataclass
class CourseData:
    name: str
    teacher: str
    students: Dict[str, str]
    tas: List[str]
    homework_ids: List[str] = field(default_factory=list, init=False)
    public_problem_ids: List[str] = field(default_factory=list, init=False)
    homework_problem_ids: List[str] = field(default_factory=list, init=False)

    @property
    def homework_name(self):
        return f"{self.name} {id(self)} Test HW"


@pytest.fixture
def course_data(
    client_admin: FlaskClient,
    problem_ids,
):
    BaseTester.setup_class()
    cd = CourseData(
        name="Programming_I",
        teacher="Po-Wen-Chi",
        students={
            "Yin-Da-Chen": "ala",
            "Bo-Chieh-Chuang": "bogay"
        },
        tas=["Tzu-Wei-Yu"],
    )

    # add course
    Course.add_course(cd.name, cd.teacher)

    # add students and TA
    client_admin.set_cookie(
        "test.test",
        "piann",
        User("admin").secret,
    )
    rv = client_admin.put(
        f"/course/{cd.name}",
        json={
            "TAs": cd.tas,
            "studentNicknames": cd.students
        },
    )
    client_admin.delete_cookie("test.test", "piann")
    assert rv.status_code == 200, rv.get_json()

    # add homework
    public_problem_ids = problem_ids(cd.teacher, 1, add_to_course=True)
    homework_problem_ids = problem_ids(cd.teacher, 1, add_to_course=True)

    hw = Homework.add(
        user=User(cd.teacher).obj,
        course_name=cd.name,
        markdown=f"# {cd.homework_name}\n\n{random_string()}",
        hw_name=cd.homework_name + "_1",
        start=int((datetime.now() - timedelta(days=7)).timestamp()),
        end=int((datetime.now() + timedelta(days=7)).timestamp()),
        problem_ids=homework_problem_ids,
        scoreboard_status=0,
    )

    # append hw id
    cd.homework_ids.append(str(hw.id))

    # append pids
    cd.public_problem_ids += public_problem_ids
    cd.homework_problem_ids += homework_problem_ids

    yield cd
    BaseTester.teardown_class()


class TestGetHomeworkProblem(BaseTester):

    def test_student_get_homewrok_problems(
        self,
        forge_client: ForgeClient,
        course_data: CourseData,
    ):
        client = forge_client("Bo-Chieh-Chuang")
        rv, rv_json, rv_data = self.request(
            client, "get",
            f"problem?offset=0&count=5&course={course_data.name}")

        print(rv_json)

        assert rv.status_code == 200
        assert rv_json["status"] == "ok"
        assert rv_json["message"] == "Success."
        assert len(rv_data) == 2

    @patch("mongo.problem.problem.datetime")
    def test_student_get_homework_problems_before_start(
            self, mock_datetime, forge_client: ForgeClient,
            course_data: CourseData):
        mock_datetime.now.return_value = datetime.now() - timedelta(days=14)

        client = forge_client("Bo-Chieh-Chuang")
        rv, rv_json, rv_data = self.request(
            client, "get",
            f"problem?offset=0&count=5&course={course_data.name}")

        print(rv_json)

        assert rv.status_code == 200
        assert rv_json["status"] == "ok"
        assert rv_json["message"] == "Success."

        for data in rv_data:
            assert data["problemId"] not in course_data.homework_problem_ids

    @patch("mongo.problem.problem.datetime")
    def test_student_view_offline_problem(self, mock_datetime,
                                          forge_client: ForgeClient,
                                          course_data: CourseData):
        mock_datetime.now.return_value = datetime.now() - timedelta(days=14)

        client = forge_client("Bo-Chieh-Chuang")
        rv, rv_json, rv_data = self.request(
            client, "get", f"/problem/2?course={course_data.name}")

        print(rv_json)

        assert rv.status_code == 403
        assert rv_json["status"] == "err"
        assert rv_json["message"] == "Problem is unavailable"
