from typing import List
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


@pytest.mark.parametrize('ip', [
    '192.168.0.1',
    '127.0.0.1',
    '144.120.20.11',
])
def test_single_ip_match(ip):
    ip_filter = IPFilter(ip)
    assert ip_filter.match(ip)


@pytest.mark.parametrize(
    '_filter, ips',
    [
        (
            '140.122.187.32-128',
            (
                '140.122.187.34',
                '140.122.187.128',
                '140.122.187.64',
            ),
        ),
        (
            '140.122.187-189.32-128',
            (
                '140.122.188.34',
                '140.122.187.128',
                '140.122.189.64',
            ),
        ),
    ],
)
def test_successful_range_match(_filter, ips):
    _filter = IPFilter(_filter)
    for ip in ips:
        assert _filter.match(ip)


@pytest.mark.parametrize('_filter, ips', [
    (
        '140.122.187.32-128',
        (
            '140.122.188.34',
            '140.122.187.196',
            '140.123.187.64',
        ),
    ),
    (
        '140.122.187-189.32-128',
        (
            '140.122.188.16',
            '140.122.201.128',
            '140.122.200.12',
        ),
    ),
])
def test_failed_range_match(_filter, ips):
    _filter = IPFilter(_filter)
    for ip in ips:
        assert not _filter.match(ip)


@pytest.mark.parametrize('_filter, ips', [
    (
        '140.122.187.*',
        (
            '140.122.187.11',
            '140.122.187.37',
        ),
    ),
    (
        '140.122.187-189.*',
        (
            '140.122.187.13',
            '140.122.188.72',
            '140.122.189.99',
        ),
    ),
])
def test_wildcard_match(_filter, ips: List[str]):
    _filter = IPFilter(_filter)
    for ip in ips:
        assert _filter.match(ip)