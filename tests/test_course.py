import pytest
from model import course
from mongo import User
from model import course
from tests.base_tester import BaseTester

class TestAdminCourse(BaseTester):
    '''Test courses panel used my admins
    '''
    def test_admin_create_course(self, client):
        # create admin
        ADMIN = {
            'username': 'admin',
            'password': 'verysuperstrongandlongpasswordforadmin',
            'email': 'i.am.admin@noj.tw'
        }

        admin = User.signup(**ADMIN)
        admin.obj.update(active=True, role=0)

        client.set_cookie('', 'jwt', admin.jwt)
        rv = client.post('/course/',
                         json={
                             'course': 'Software testing (I)',
                             'teacher': ADMIN['username']
                         })

        assert rv.status_code == 200

    def test_normal_user_create_course(self, client):
        NORMAL = {
            'username': 'i_am_not_admin',
            'password': 'pswd',
            'email': 'normal@noj.tw'
        }

        assert User('test') is None
