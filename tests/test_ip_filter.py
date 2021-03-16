import pytest
from mongo.ip_filter import IPFilter


@pytest.mark.parametrize('_filter', [
    '192.168.0.1',
    '8.8.8.8',
    '140.122.187.11',
])
def test_normal_filter_format(_filter):
    IPFilter(_filter)


@pytest.mark.parametrize('_filter', [
    '192.168.0.127-255',
    '121.0.32-64.77',
])
def test_range_filter(_filter):
    IPFilter(_filter)


@pytest.mark.parametrize('_filter', [
    '192.*.*.*',
    '140.121.*.*',
])
def test_wildcard_filter(_filter):
    IPFilter(_filter)


@pytest.mark.parametrize('_filter', [
    'foo.bar',
    'fe80::215:5dff:fe10:3331',
    '1234567',
])
def test_invalid_filter_format(_filter):
    with pytest.raises(ValueError, match=r'.*Invalid.*'):
        IPFilter(_filter)
