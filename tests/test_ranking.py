import pytest
from tests.base_tester import BaseTester


class TestRanking(BaseTester):
    '''Test ranking
    '''
    def test_get(self, forge_client, problem_ids):
        pid = problem_ids('teacher', 1, True)[0]

        # send inbox with all invalide user
        client = forge_client('student')
        rv = client.post('/submission',
                         json={
                             'problemId': pid,
                             'languageType': 0
                         })
        print(rv.get_json())

        rv = client.get('/ranking')
        json = rv.get_json()
        assert json['message'] == 'Success.'
        assert rv.status_code == 200
        assert json['data'][0] == {
            'ACProblem': 0,
            'ACSubmission': 0,
            'Submission': 1,
            'username': 'student'
        }
