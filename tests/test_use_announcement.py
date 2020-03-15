import pytest
from tests.base_tester import BaseTester


class TestAnnouncement(BaseTester):
    '''Test courses panel used my admins
    '''
    def test_add(self, client_admin):
        # add an announcement
        rv = client_admin.post('/course',
                               json={
                                   'course': 'math',
                                   'teacher': 'admin'
                               })
        assert rv.status_code == 200

        rv = client_admin.post('/ann',
                               json={
                                   'title': 'lol',
                                   'markdown': 'im good',
                                   'courseName': 'math'
                               })
        json = rv.get_json()
        assert rv.status_code == 200

        rv = client_admin.get(f'/course/math/ann')
        json = rv.get_json()
        assert rv.status_code == 200
        assert len(json['data']) == 1
        assert json['data'][0]['title'] == 'lol'
        assert json['data'][0]['markdown'] == 'im good'
        assert json['data'][0]['pinned'] == False

    def test_add_without_teacher(self, client_student):
        # add an announcement when not a teacher
        rv = client_student.post('/ann',
                                 json={
                                     'title': 'no',
                                     'markdown': 'god',
                                     'courseName': 'math'
                                 })
        json = rv.get_json()
        assert rv.status_code == 403

    def test_edit(self, client_admin):
        # edit an announcement
        rv = client_admin.get(f'/course/math/ann')
        json = rv.get_json()
        id = json['data'][0]['annId']

        rv = client_admin.put('/ann',
                              json={
                                  'annId': id,
                                  'title': 'lol (edit)',
                                  'markdown': 'im good',
                                  'pinned': True
                              })
        json = rv.get_json()
        assert rv.status_code == 200

        rv = client_admin.get(f'/ann/math/{id}')
        json = rv.get_json()
        assert rv.status_code == 200
        assert json['data'][0]['title'] == 'lol (edit)'
        assert json['data'][0]['markdown'] == 'im good'
        assert json['data'][0]['pinned'] == True

    def test_delete(self, client_admin):
        # delete an announcement
        rv = client_admin.get(f'/course/math/ann')
        json = rv.get_json()
        id = json['data'][0]['annId']

        rv = client_admin.delete('/ann', json={'annId': id})
        assert rv.status_code == 200

        rv = client_admin.get(f'/course/math/ann')
        json = rv.get_json()
        assert rv.status_code == 200
        assert len(json['data']) == 0
