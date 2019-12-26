import pytest
from tests.base_tester import BaseTester


class TestRanking(BaseTester):
    '''Test ranking
    '''

    def test_get(self, client_student):
        # send inbox with all invalide user
        client_student.post(
            '/submission', json={
                'problemId': '8888',
                'languageType': 0
            })

        rv = client_student.get('/ranking')
        json = rv.get_json()
        assert json['message'] == 'Success.'
        assert rv.status_code == 200
        assert json['data'][0] == {
            'ACProblem': 0,
            'ACSubmission': 0,
            'Submission': 1,
            'username': 'student'
        }
