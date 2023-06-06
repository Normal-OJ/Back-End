from model.announcement import Announcement as ModelAnn
from mongo import DoesNotExist, ValidationError
from tests.base_tester import BaseTester


class TestAnnouncement(BaseTester):
    '''Test courses panel used my admins
    '''

    def test_get_list_with_course_does_not_exist(self, client_student):
        rv = client_student.get('/ann/CourseDoesNotExist/ann')
        assert rv.status_code == 200, rv.get_json()
        assert rv.get_json()['data'] == []

    def test_get_invalid_announcement_list(self, client_student, monkeypatch):

        def mock_ann_list_raise_does_not_exist(*args):
            raise DoesNotExist

        monkeypatch.setattr(ModelAnn, 'ann_list',
                            mock_ann_list_raise_does_not_exist)
        rv = client_student.get('/ann/Public/ann')
        assert rv.status_code == 403, rv.get_json()
        assert rv.get_json()['message'] == 'Cannot Access a Announcement'

    def test_get_none_announcement_list(self, client_student, monkeypatch):
        monkeypatch.setattr(ModelAnn, 'ann_list', lambda *_: None)
        rv = client_student.get('/ann/Public/ann')
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'Announcement Not Found'

    def test_add_invalid(self, client_student, monkeypatch):

        def mock_new_ann_reaise_validation_error(*args, **kwargs):
            raise ValidationError

        monkeypatch.setattr(ModelAnn, 'new_ann',
                            mock_new_ann_reaise_validation_error)
        rv = client_student.post('/ann',
                                 json={
                                     'title': 'hhh',
                                     'markdown': 'im bad',
                                     'courseName': 'invalid'
                                 })
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'Failed to Create Announcement'

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

    def test_get_list_without_perm(self, client_student):
        rv = client_student.get('/ann/math/ann')
        assert rv.status_code == 200, rv.get_json()
        assert rv.get_json()['data'] == []

    def test_edit_does_not_exist(self, client_admin):
        rv = client_admin.put('/ann',
                              json={
                                  'annId': 878787878787878787878787,
                                  'title': 'lol (edit)',
                                  'markdown': 'im good',
                                  'pinned': True
                              })
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'Announcement Not Found'

    def test_edit_without_perm(self, forge_client):
        client = forge_client('admin')
        rv = client.get(f'/course/math/ann')
        id = rv.get_json()['data'][0]['annId']
        client = forge_client('student')
        rv = client.put('/ann',
                        json={
                            'annId': id,
                            'title': 'lol (edit)',
                            'markdown': 'im good',
                            'pinned': True
                        })
        assert rv.status_code == 403, rv.get_json()
        assert rv.get_json()['message'] == 'Failed to Update Announcement'

    def test_edit_with_invalid_ann_content(self, client_admin, monkeypatch):
        rv = client_admin.get(f'/course/math/ann')
        id = rv.get_json()['data'][0]['annId']
        rv = client_admin.put('/ann',
                              json={
                                  'annId': id,
                                  'title':
                                  'title tooooooo loooooong' + 'a' * 64,
                                  'markdown': 'im good',
                                  'pinned': True
                              })
        assert rv.status_code == 400, rv.get_json()
        assert rv.get_json()['message'] == 'Failed to Update Announcement'

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

    def test_delete_does_not_exist(self, client_admin):
        rv = client_admin.delete('/ann',
                                 json={
                                     'annId': 878787878787878787878787,
                                 })
        assert rv.status_code == 404, rv.get_json()
        assert rv.get_json()['message'] == 'Announcement Not Found'

    def test_delete_without_perm(self, forge_client):
        client = forge_client('admin')
        rv = client.get(f'/course/math/ann')
        id = rv.get_json()['data'][0]['annId']
        client = forge_client('student')
        rv = client.delete('/ann', json={
            'annId': id,
        })
        assert rv.status_code == 403, rv.get_json()
        assert rv.get_json()['message'] == 'Failed to Delete Announcement'

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

    def test_get_public_announcement(self, client_admin):
        rv = client_admin.get('/ann')
        assert rv.status_code == 200
