import pytest
import random
from mongo.ip_filter import OctetMatcher


@pytest.mark.parametrize(
    'n',
    [16, 37, 128],
)
def test_digit_match(n):
    '''
    only n should be matched
    '''
    matcher = OctetMatcher(str(n))
    assert matcher.match(n)
    assert not matcher.match((n**2) % 256 + 1)


@pytest.mark.parametrize('a, b', [
    (16, 32),
    (78, 129),
    (0, 128),
])
def test_range_match(a, b):
    '''
    any number in [a, b] should be matched
    '''
    matcher = OctetMatcher(f'{a}-{b}')
    assert matcher.match((a + b) >> 1)
    assert not matcher.match(b + 1)


def test_wildcard_match():
    '''
    any number in [0, 255] should be matched
    '''
    matcher = OctetMatcher('*')
    for i in range(256):
        assert matcher.match(i)
