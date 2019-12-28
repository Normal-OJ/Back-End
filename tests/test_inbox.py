import pytest
from tests.base_tester import BaseTester

message_id = 0


class TestInbox(BaseTester):
    '''Test inbox
    '''
    def test_send_with_invalid_username(self, client_student):
        # send inbox with all invalide user
        rv = client_student.post('/inbox',
                                 json={
                                     'receivers': [],
                                     'title': 'hi',
                                     'message': 'AAA'
                                 })
        json = rv.get_json()
        assert json['message'] == 'At least one receiver is required'
        assert rv.status_code == 400

    def test_send_with_invalid_info(self, client_student):
        # send inbox with wierd info
        rv = client_student.post('/inbox',
                                 json={
                                     'receivers': ['teacher'],
                                     'title': {},
                                     'message': 'AAA'
                                 })
        json = rv.get_json()
        assert json['message'] == 'Failed to Send a Message'
        assert rv.status_code == 400

    def test_send(self, client_student):
        # send inbox
        rv = client_student.post('/inbox',
                                 json={
                                     'receivers': ['teacher'],
                                     'title': 'hi',
                                     'message': 'AAA'
                                 })
        json = rv.get_json()
        assert json['message'] == 'Successfully Send'
        assert rv.status_code == 200

    def test_view(self, client_teacher):
        # view inbox
        rv = client_teacher.get('/inbox')
        json = rv.get_json()
        assert json['message'] == 'Received List'
        assert rv.status_code == 200
        assert json['data'][0]['message'] == 'AAA'
        assert json['data'][0]['title'] == 'hi'
        # assert json['data'][0]['sender'] == 'student'
        # assert json['data'][0]['status'] == 0

        # global message_id
        # message_id = json['data'][0]['messageId']

    def test_read_without_owner(self, client_student):
        # read a inbox message when you are not the owner
        rv = client_student.put('/inbox', json={'messageId': message_id})
        json = rv.get_json()
        assert json['message'] == 'Failed to Read the Message'
        assert rv.status_code == 403

    def test_read(self, client_teacher):
        # read a inbox message
        rv = client_teacher.put('/inbox', json={'messageId': message_id})
        json = rv.get_json()
        # assert json['message'] == 'Message Status Changed'
        # assert rv.status_code == 200

        # rv = client_teacher.get('/inbox')
        # json = rv.get_json()
        # assert json['data'][0]['status'] == 1

    def test_delete_without_owner(self, client_student):
        # delete a inbox message when you are not the owner
        rv = client_student.delete('/inbox', json={'messageId': message_id})
        json = rv.get_json()
        assert json['message'] == 'Failed to Access the Message'
        assert rv.status_code == 403

    def test_delete(self, client_teacher):
        # delete a inbox message
        rv = client_teacher.delete('/inbox', json={'messageId': message_id})
        json = rv.get_json()
        # assert json['message'] == 'Deleted'
        # assert rv.status_code == 200

        # rv = client_teacher.get('/inbox')
        # json = rv.get_json()
        # assert len(json['data']) == 0

    def test_view_sent(self, client_student):
        # view sent message
        rv = client_student.get('/inbox/sent')
        json = rv.get_json()
        assert json['message'] == 'Sent List'
        assert rv.status_code == 200
        assert json['data'][0]['message'] == 'AAA'
        assert json['data'][0]['title'] == 'hi'
    #     assert json['data'][0]['receivers'] == ['teacher']

    #     global message_id
    #     message_id = json['data'][0]['messageId']

    # def test_delete_sent_with_invalid_id(self, client_student):
    #     # delete a none-exist inbox message
    #     rv = client_student.delete('/inbox/sent',
    #                                json={'messageId': 'random_id'})
    #     json = rv.get_json()
    #     assert json['message'] == 'Message Not Found'
    #     assert rv.status_code == 404

    # def test_delete_sent_without_owner(self, client_teacher):
    #     # delete a inbox message when you are not the owner
    #     rv = client_teacher.delete('/inbox/sent',
    #                                json={'messageId': message_id})
    #     json = rv.get_json()
    #     assert json['message'] == 'Failed to Access the Message'
    #     assert rv.status_code == 403

    # def test_delete_sent(self, client_student):
    #     # delete a inbox message
    #     rv = client_student.delete('/inbox/sent',
    #                                json={'messageId': message_id})
    #     json = rv.get_json()
    #     assert json['message'] == 'Deleted'
    #     assert rv.status_code == 200

    #     rv = client_student.get('/inbox/sent')
    #     json = rv.get_json()
    #     assert len(json['data']) == 0
