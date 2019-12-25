import pytest
from tests.base_tester import BaseTester


class TestAddProblem(BaseTester):
    REQUEST_JSON = {
        "status": 0,
        "type": 1,
        "problemName": "Test problem name",
        "description": "Test description.",
        "tags": ["TestTag01", "TestTag02"],
        "testCase": {
            "language":
            2,
            "fillInTemplate":
            "Test f__l in t__pl__e.",
            "cases": [{
                "input": "TestInput01",
                "output": "TestOutput01",
                "caseScore": 1,
                "memoryLimit": 1,
                "timeLimit": 1
            }]
        }
    }

    def test_add_with_invalid_value(cls, client_admin):
        request_json_with_invalid_json = cls.REQUEST_JSON
        request_json_with_invalid_json["status"] = 2  # Invalid value
        rv = client_admin.post('/problem/manage',
                               json=request_json_with_invalid_json)
        json = rv.get_json()
        #assert rv.status_code == 400
        assert json['status'] == 'err'
        assert json['message'] == 'Invalid or missing arguments.'

    def test_add_with_missing_argument(cls, client_admin):
        request_json_with_missing_argument = cls.REQUEST_JSON
        rv = client_admin.post('/problem/manage',
                               json=request_json_with_missing_argument)
        json = rv.get_json()
        assert rv.status_code == 400
        assert json['status'] == 'err'
        assert json['message'] == 'Invalid or missing arguments.'
