from tests.base_tester import BaseTester
from model.utils.request import Request
from mongo import Announcement


class MockHTTPError(tuple):

    def __new__(cls, *args):
        return super().__new__(tuple, args)


class TestUtilsRequest(BaseTester):

    def test_request_without_content_type_header(self, monkeypatch):

        class MockRequest:
            json = None

        mock_request = MockRequest()
        from model.utils import request
        monkeypatch.setattr(request, 'request', mock_request)
        monkeypatch.setattr(request, 'HTTPError', MockHTTPError)

        @Request.json()
        def route():
            pass

        message, status_code = route()
        assert message == 'Unaccepted Content-Type json'
        assert status_code == 415

    def test_request_doc_with_missing_args(self, monkeypatch):

        @Request.doc('src', 'dst', str)
        def route(dst):
            assert type(dst) == str

        from model.utils import request
        monkeypatch.setattr(request, 'HTTPError', MockHTTPError)
        message, status_code = route(typo=123)
        assert status_code == 500
        assert message == 'src not found in function argument'

    def test_request_doc_raise_validation_error(self, monkeypatch):

        @Request.doc('src', 'dst', Announcement)
        def route(dst):
            raise

        from model.utils import request
        monkeypatch.setattr(request, 'HTTPError', MockHTTPError)
        import logging

        class MockAPP:
            logger = logging.getLogger('mock_app')

        mock_current_app = MockAPP()
        monkeypatch.setattr(request, 'current_app', mock_current_app)
        message, status_code = route(src=87)
        assert status_code == 400
        assert message == 'Invalid parameter'
