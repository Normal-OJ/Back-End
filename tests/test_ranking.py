import pytest
from tests.base_tester import BaseTester


class TestRanking(BaseTester):
    '''Test ranking
    '''

    def test_get(
        self,
        forge_client,
        problem_ids,
        make_course,
    ):
        make_course('teacher', {'student': '1450'})
        pid = problem_ids('teacher', 1, True, 0)[0]

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
        '''
        user = list(u for u in json['data'] if u['user']['username'] == 'student')[0]
        assert user['ACProblem'] == 0
        assert user['ACSubmission'] == 0
        assert user['Submission'] == 1
        '''
