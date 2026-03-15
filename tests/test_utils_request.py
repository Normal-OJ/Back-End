from tests.base_tester import BaseTester
from model.utils.request import Request, parse_body, parse_query
from model.schemas.base import BaseSchema
from mongo import Announcement
from typing import Optional


class MockHTTPError(tuple):

    def __new__(cls, *args, **kwargs):
        return super().__new__(tuple, args)


class LoginBody(BaseSchema):
    username: str
    password: str


class SearchQuery(BaseSchema):
    q: Optional[str] = None
    limit: Optional[int] = None


class TestParseBody(BaseTester):

    def test_parse_body_valid(self, monkeypatch):

        class MockRequest:

            @staticmethod
            def get_json(silent=False):
                return {'username': 'alice', 'password': 'secret'}

        from model.utils import request as req_module
        monkeypatch.setattr(req_module, 'request', MockRequest())
        monkeypatch.setattr(req_module, 'HTTPError', MockHTTPError)

        @parse_body(LoginBody)
        def route(body):
            return body

        result = route()
        assert result.username == 'alice'
        assert result.password == 'secret'

    def test_parse_body_invalid_type(self, monkeypatch):

        class MockRequest:

            @staticmethod
            def get_json(silent=False):
                return {'username': 123, 'password': 'secret'}

        # username must be str — Pydantic v2 does NOT coerce int to str
        from model.utils import request as req_module
        monkeypatch.setattr(req_module, 'request', MockRequest())
        monkeypatch.setattr(req_module, 'HTTPError', MockHTTPError)

        @parse_body(LoginBody)
        def route(body):
            return body

        # Pydantic v2 rejects int for a str field
        message, status_code = route()
        assert status_code == 400
        assert message == 'Invalid request body'

    def test_parse_body_missing_required_field(self, monkeypatch):

        class MockRequest:

            @staticmethod
            def get_json(silent=False):
                return {'username': 'alice'}  # missing 'password'

        from model.utils import request as req_module
        monkeypatch.setattr(req_module, 'request', MockRequest())
        monkeypatch.setattr(req_module, 'HTTPError', MockHTTPError)

        @parse_body(LoginBody)
        def route(body):
            return body

        message, status_code = route()
        assert status_code == 400
        assert message == 'Invalid request body'

    def test_parse_body_no_json(self, monkeypatch):

        class MockRequest:

            @staticmethod
            def get_json(silent=False):
                return None  # no JSON body

        from model.utils import request as req_module
        monkeypatch.setattr(req_module, 'request', MockRequest())
        monkeypatch.setattr(req_module, 'HTTPError', MockHTTPError)

        @parse_body(LoginBody)
        def route(body):
            return body

        message, status_code = route()
        assert status_code == 400

    def test_parse_body_camelcase_alias(self, monkeypatch):
        from model.schemas.profile import EditProfileBody

        class MockRequest:

            @staticmethod
            def get_json(silent=False):
                return {'displayedName': 'Alice'}  # camelCase alias

        from model.utils import request as req_module
        monkeypatch.setattr(req_module, 'request', MockRequest())

        @parse_body(EditProfileBody)
        def route(body):
            return body

        result = route()
        assert result.displayed_name == 'Alice'


class TestParseQuery(BaseTester):

    def test_parse_query_valid(self, monkeypatch):

        class MockRequest:
            args = {'q': 'hello', 'limit': '10'}

        from model.utils import request as req_module
        monkeypatch.setattr(req_module, 'request', MockRequest())

        @parse_query(SearchQuery)
        def route(query):
            return query

        result = route()
        assert result.q == 'hello'
        assert result.limit == 10

    def test_parse_query_optional_missing(self, monkeypatch):

        class MockRequest:
            args = {}

        from model.utils import request as req_module
        monkeypatch.setattr(req_module, 'request', MockRequest())

        @parse_query(SearchQuery)
        def route(query):
            return query

        result = route()
        assert result.q is None
        assert result.limit is None


class TestUtilsRequestDoc(BaseTester):

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
