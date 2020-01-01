import pytest
from tests.test_submission import SubmissionTester


class TestRanking(SubmissionTester):
    '''Test ranking
    '''
    def test_get(self, forge_client, problem_ids):
        pid = problem_ids('teacher', 1)[0]
        submission = SubmissionTester.source['c11']

        # submit a problem
        client = forge_client('student')
        rv = client.post('/submission',
                         json={
                             'problemId': pid,
                             'languageType': 0
                         })
        rv_data = rv.get_json()['data']
        print(rv.get_json())

        files = {'code': (submission['zip'], 'code')}
        rv = client.put(
            f'/submission/{rv_data["submissionId"]}?token={rv_data["token"]}',
            data=files,
        )
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
