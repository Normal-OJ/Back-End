import pytest


class TestAdminCourse:
    '''Test courses panel used my admins
    '''
    def test_signup_and_login(self, client,test_token):
        '''client.post('/auth/signup',
                            json={
                                'username': 'test',
                                'password': 'test',
                                'email': 'test@test.test'
                            })
        client.set_cookie('test.test', 'jwt', test_token)
        client.post(f'/auth/active',
                            json={
                                'profile': {
                                    'displayedName': 'Test',
                                    'bio': 'Hi',
                                },
                                'agreement': True
                            })'''
        rv = client.post('/auth/session',
                            json={
                                'username': 'test',
                                'password': 'test'
                            })
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Login Success'


    def test_view(self, client):
        # Get all courses
        rv = client.get('/course')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Success.'
        assert json['data'] == []


    def test_add_with_invalid_username(self, client):
        # add a course with non-existent username
        rv = client.post('/course',
                            json={
                                'course': 'math',
                                'teacher': 'testt'
                            })
        json = rv.get_json()
        assert rv.status_code == 404
        assert json['status'] == 'err'
        assert json['message'] == '"User not found."'


    def test_add(self, client):
        # add a course
        rv = client.post('/course',
                            json={
                                'course': 'math',
                                'teacher': 'test'
                            })
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['status'] == 'ok'
        assert json['message'] == 'Success.'

        rv = client.get('/course')
        json = rv.get_json()
        assert json['data'] == [{
                'course': 'math',
                'teacher': 'test'
            }]
