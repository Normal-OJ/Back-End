import pytest

from mongo.engine import ZipField, ValidationError


class TestZipField:

    def test_validate_with_non_zip_file(self, monkeypatch):
        from mongo.engine import FileField
        monkeypatch.setattr(FileField, 'validate', lambda *_: None)
        zf = ZipField()
        with pytest.raises(ValidationError) as err:
            zf.validate('tests/problem_test_case/bogay/0000.in')
        assert str(err.value) == 'Only accept zip file.'


import datetime
from mongo.engine import Duration


class TestDuration:

    def test_not_in(self):
        assert 'string' not in Duration()

    def test_in(self):
        d = Duration()
        assert datetime.datetime.now() in d


from mongo.engine import ProblemDescription


class TestProblemDescription:

    def test_escape(self):
        pd = ProblemDescription()
        pd.description = '<h1>description</h1>'
        pd.input = 'input'
        pd.output = 'output'
        pd.hint = '<script>hint</script>'
        pd.sample_input = ['123', '456']
        pd.sample_output = ['789', '101']
        pd.escape()
        import html
        assert pd.description == html.escape('<h1>description</h1>')
        assert pd.hint == html.escape('<script>hint</script>')
